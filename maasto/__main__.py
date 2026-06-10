"""maasto CLI : python -m maasto <coords> [options]."""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from . import bera, camptocamp, coords as coords_mod, geocoding
from . import report, satellite, weather

ROOT = Path(__file__).parent.parent
CSS_PATH = ROOT / "assets" / "nord.css"
RESULTS = ROOT / "results"


def _slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower())
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s or "spot"


def main(argv=None):
    p = argparse.ArgumentParser(prog="maasto",
        description="Check conditions neige/rando pour un point GPS.")
    p.add_argument("coords", help='Coords. Décimal "45.165,6.170" ou DMS "45°09\'54\\"N 6°10\'12\\"E"')
    p.add_argument("--altitude", type=int, help="Altitude forcée (par défaut : Open-Elevation)")
    p.add_argument("--days", type=int, default=14, help="Fenêtre temporelle en jours (défaut 14)")
    p.add_argument("--no-sat", action="store_true", help="Skip imagerie satellite")
    p.add_argument("--no-camptocamp", action="store_true")
    p.add_argument("--no-bera", action="store_true")
    p.add_argument("--levels", type=str,
                   help="Altitudes virgule-séparées, défaut auto à partir de l'altitude du point")
    args = p.parse_args(argv)

    pt = coords_mod.parse(args.coords)
    print(f"→ Point : {pt}")

    print("→ Identification (Nominatim) + altitude (Open-Elevation)...")
    spot = geocoding.reverse(pt.lat, pt.lon)
    elev = args.altitude or geocoding.elevation(pt.lat, pt.lon)
    if elev:
        print(f"  ✓ {spot.get('name', '?')} — {elev} m")

    if args.levels:
        levels = [int(x) for x in args.levels.split(",") if x.strip()]
    elif elev:
        base = int(elev)
        levels = sorted({max(800, base - 600), base, min(4500, base + 600), min(4500, base + 1200)})
    else:
        levels = [1500, 2200, 2800, 3300]
    print(f"→ Météo Open-Meteo aux altitudes : {levels} m")
    weather_data = weather.fetch(pt.lat, pt.lon, levels, past_days=args.days)
    print(f"  ✓ Cellule modèle à {weather_data['cell']['elevation']} m")

    out_root = RESULTS / f"{_slugify(spot.get('name', 'spot'))}_{datetime.now().strftime('%Y%m%d-%H%M')}"
    raw_dir = out_root / "raw"
    img_dir = out_root / "images"
    raw_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "weather.json").write_text(json.dumps(weather_data, indent=2, default=str))

    scenes, sat_images = [], []
    if not args.no_sat:
        print("→ Recherche Sentinel-2...")
        try:
            scenes = satellite.search(pt.lat, pt.lon, days_back=max(15, args.days))
            recent_group, older_group = satellite.best_pair(scenes)
            for label, candidates in [("recent", recent_group), ("older", older_group)]:
                for sc in candidates:
                    if not sc.get("tci_url"):
                        continue
                    out = img_dir / f"sat_{label}_{sc['date']}.png"
                    try:
                        print(f"  → Crop {label} {sc['date']} "
                              f"({sc['cloud_cover']:.1f}% nuages, {sc['id']})")
                        satellite.crop(sc, pt.lat, pt.lon, out)
                        sat_images.append({
                            "date": sc["date"], "cloud": sc["cloud_cover"],
                            "path": f"images/{out.name}",
                        })
                        break
                    except Exception as e:
                        print(f"    ↪ skip ({e})")
                        continue
        except Exception as e:
            print(f"  ⚠️  satellite : {e}")

    outings = []
    if not args.no_camptocamp:
        print("→ Camptocamp sorties récentes...")
        outings = camptocamp.recent_outings(pt.lat, pt.lon)
        print(f"  ✓ {len(outings)} sorties")
        (raw_dir / "camptocamp.json").write_text(json.dumps(outings, indent=2))

    bera_data = {"available": False, "source": "—"}
    if not args.no_bera:
        print("→ Bulletin avalanche...")
        bera_data = bera.fetch(pt.lat, pt.lon)
        (raw_dir / "bera.json").write_text(json.dumps(bera_data, indent=2))

    print("→ Génération rapport HTML...")
    out = report.render(
        out_root, coords=pt, spot=spot, elevation_m=elev,
        weather_data=weather_data, scenes=scenes, sat_images=sat_images,
        outings=outings, bera_data=bera_data,
        css_path=CSS_PATH,
    )
    print(f"\n✓ Rapport : {out}")
    print(f"  open {out}")


if __name__ == "__main__":
    main()
