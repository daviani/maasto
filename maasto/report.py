"""Génération rapport HTML stylé Nord."""
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import camptocamp as c2c_mod
from . import weather as wmod

_NORD = {"axis": "#4c566a", "grid": "#3b4252", "line": "#88c0d0",
         "label": "#d8dee9", "fresh": "#a3be8c"}


def _snow_chart_svg(levels_summary: list[dict], series: dict[int, list[dict]]) -> str:
    """SVG inline de l'évolution snow_depth multi-altitudes."""
    if not series:
        return ""
    width, height = 800, 280
    pad = {"top": 20, "right": 20, "bottom": 35, "left": 50}
    inner_w = width - pad["left"] - pad["right"]
    inner_h = height - pad["top"] - pad["bottom"]

    all_dates = sorted({p["date"] for s in series.values() for p in s})
    if not all_dates:
        return ""
    max_depth = max((p["depth_m"] for s in series.values() for p in s), default=2.0)
    max_depth = max(max_depth * 1.1, 0.5)

    def x(i): return pad["left"] + (i / max(1, len(all_dates) - 1)) * inner_w
    def y(d): return pad["top"] + (1 - d / max_depth) * inner_h

    parts = [f'<svg class="snowchart" xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="0 0 {width} {height}" width="100%" '
             f'preserveAspectRatio="xMidYMid meet">']

    # Grid horizontal
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        yp = pad["top"] + frac * inner_h
        depth = (1 - frac) * max_depth
        parts.append(f'<line x1="{pad["left"]}" y1="{yp}" x2="{pad["left"]+inner_w}" '
                     f'y2="{yp}" stroke="{_NORD["grid"]}" stroke-width="0.5"/>')
        parts.append(f'<text x="{pad["left"]-8}" y="{yp+4}" fill="{_NORD["axis"]}" '
                     f'font-size="10" text-anchor="end">{depth:.1f}m</text>')

    # Lignes par altitude (dégradé teintes Nord)
    palette = ["#88c0d0", "#81a1c1", "#5e81ac", "#a3be8c", "#b48ead"]
    sorted_alts = sorted(series.keys())
    for idx, alt in enumerate(sorted_alts):
        color = palette[idx % len(palette)]
        pts = series[alt]
        path_d = []
        for p in pts:
            i = all_dates.index(p["date"])
            cmd = "M" if not path_d else "L"
            path_d.append(f"{cmd} {x(i):.1f} {y(p['depth_m']):.1f}")
        if path_d:
            parts.append(f'<path d="{" ".join(path_d)}" stroke="{color}" '
                         f'fill="none" stroke-width="2"/>')
            parts.append(f'<text x="{pad["left"]+inner_w+5}" y="{y(pts[-1]["depth_m"])+4}" '
                         f'fill="{color}" font-size="10">{alt}m</text>')

    # Axe X (dates espacées)
    step = max(1, len(all_dates) // 7)
    for i, d in enumerate(all_dates):
        if i % step == 0 or i == len(all_dates) - 1:
            xp = x(i)
            parts.append(f'<text x="{xp}" y="{height-pad["bottom"]+18}" '
                         f'fill="{_NORD["axis"]}" font-size="10" '
                         f'text-anchor="middle">{d[5:]}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def render(out_dir: Path, *, coords, spot, elevation_m, weather_data,
           scenes, sat_images, outings, bera_data, css_path) -> Path:
    """Génère report.html dans out_dir."""
    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent.parent / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("report.html.j2")

    levels_summary = []
    series = {}
    for alt, level_data in weather_data["levels"].items():
        daily = wmod.daily_summary(level_data)
        sd = wmod.snow_depth_noon(level_data)
        if not daily or not sd:
            continue
        levels_summary.append({
            "altitude": alt,
            "first": sd[0]["depth_m"],
            "last": sd[-1]["depth_m"],
            "delta": sd[-1]["depth_m"] - sd[0]["depth_m"],
            "tmax": max(d["tmax"] for d in daily),
            "tmin": min(d["tmin"] for d in daily),
            "precip": sum(d["precip"] for d in daily),
        })
        series[alt] = sd

    cell_daily = wmod.daily_summary(weather_data["cell"]["data"])
    first_date = cell_daily[0]["date"] if cell_daily else "—"
    last_date = cell_daily[-1]["date"] if cell_daily else "—"

    # Signal terrain Camptocamp : on prend le snow_depth le plus bas observé
    # (i.e. l'altitude basse) pour détecter une discordance modèle/terrain.
    modeled_low = min((lvl["last"] for lvl in levels_summary), default=0.0)
    c2c_signal = c2c_mod.signal(outings, modeled_low)

    sun = weather_data["sun"]
    sun_today = None
    if sun["sunrise"]:
        sr = sun["sunrise"][-1] if sun["sunrise"] else ""
        ss = sun["sunset"][-1] if sun["sunset"] else ""
        sun_today = {"sunrise": sr[-5:] if sr else "?", "sunset": ss[-5:] if ss else "?"}

    freezing_today = None
    if weather_data["freezing_level"]:
        freezing_today = weather_data["freezing_level"][-1]["altitude"]

    css = Path(css_path).read_text()
    html = tpl.render(
        coords=coords, spot=spot, elevation_m=elevation_m,
        weather=weather_data,
        levels_summary=levels_summary,
        snow_chart_svg=_snow_chart_svg(levels_summary, series),
        cell_daily=cell_daily,
        first_date=first_date, last_date=last_date,
        satellite_images=sat_images,
        all_scenes=scenes,
        outings=outings,
        c2c_signal=c2c_signal,
        bera=bera_data,
        sun_today=sun_today,
        freezing_today=freezing_today,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        css=css,
    )

    out_path = out_dir / "report.html"
    out_path.write_text(html)
    return out_path
