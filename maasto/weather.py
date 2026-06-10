"""Météo neige Open-Meteo : multi-altitudes, soleil, isotherme 0°C."""
import requests

_TIMEOUT = 15
_BASE = "https://api.open-meteo.com/v1/forecast"


def _is_swiss(lat: float, lon: float) -> bool:
    """Détection grossière zone Suisse pour timezone + modèle."""
    return 45.7 <= lat <= 47.9 and 5.9 <= lon <= 10.5


def fetch(lat: float, lon: float, altitudes: list[int],
          past_days: int = 14, forecast_days: int = 1) -> dict:
    """
    Récupère météo + neige aux altitudes demandées + une cellule native.
    Retourne dict avec :
      - cell : altitude réelle de la cellule modèle + données
      - levels : {altitude: data}
      - sun : {sunrise, sunset, ...}
      - freezing_level : altitude isotherme 0°C par jour
    """
    tz = "Europe/Zurich" if _is_swiss(lat, lon) else "Europe/Paris"
    common = {
        "latitude": lat, "longitude": lon,
        "past_days": past_days, "forecast_days": forecast_days,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "rain_sum,snowfall_sum,sunrise,sunset",
        "hourly": "snow_depth,freezing_level_height",
        "timezone": tz,
    }
    # requests will URL-encode `/` correctly; don't double-encode

    cell = _get(common)

    levels = {}
    for alt in altitudes:
        params = {**common, "elevation": alt}
        levels[alt] = _get(params)

    sun = {
        "sunrise": cell["daily"].get("sunrise", []),
        "sunset": cell["daily"].get("sunset", []),
    }
    freezing = cell.get("hourly", {}).get("freezing_level_height", [])
    times = cell.get("hourly", {}).get("time", [])
    freezing_daily = []
    if freezing and times:
        seen = {}
        for t, fl in zip(times, freezing):
            day = t[:10]
            if fl is not None and day not in seen:
                seen[day] = fl
        freezing_daily = [{"date": d, "altitude": v} for d, v in seen.items()]

    return {
        "cell": {
            "elevation": cell.get("elevation"),
            "lat_eff": cell.get("latitude"),
            "lon_eff": cell.get("longitude"),
            "data": cell,
        },
        "levels": levels,
        "sun": sun,
        "freezing_level": freezing_daily,
        "timezone": tz,
    }


def _get(params: dict) -> dict:
    r = requests.get(_BASE, params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def daily_summary(level_data: dict) -> list[dict]:
    """Synthèse quotidienne pour un niveau d'altitude."""
    daily = level_data["daily"]
    out = []
    for i, t in enumerate(daily["time"]):
        out.append({
            "date": t,
            "tmin": daily["temperature_2m_min"][i],
            "tmax": daily["temperature_2m_max"][i],
            "precip": daily["precipitation_sum"][i] or 0,
            "rain": daily["rain_sum"][i] or 0,
            "snow_cm": daily["snowfall_sum"][i] or 0,
        })
    return out


def snow_depth_noon(level_data: dict) -> list[dict]:
    """Snow depth à 12h chaque jour."""
    sd = level_data.get("hourly", {}).get("snow_depth", [])
    times = level_data.get("hourly", {}).get("time", [])
    out = []
    for t, v in zip(times, sd):
        if t.endswith("T12:00") and v is not None:
            out.append({"date": t[:10], "depth_m": v})
    return out
