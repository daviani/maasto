"""Reverse geocoding (Nominatim OSM) + altitude (Open-Elevation)."""
import requests

_UA = "maasto/0.1 (https://github.com/dav-maasto)"
_TIMEOUT = 10


def reverse(lat: float, lon: float) -> dict:
    """Retourne dict {name, country, region, raw}. {} si échec."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat, "lon": lon, "format": "json",
                "zoom": 14, "accept-language": "fr",
            },
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
    except (requests.RequestException, ValueError):
        return {}

    addr = d.get("address", {})
    name = (addr.get("hamlet") or addr.get("village") or addr.get("town")
            or addr.get("locality") or addr.get("municipality") or d.get("name"))
    return {
        "name": name or "Spot",
        "country": addr.get("country", ""),
        "region": addr.get("state", ""),
        "display": d.get("display_name", ""),
        "raw": d,
    }


def elevation(lat: float, lon: float) -> float | None:
    """Altitude en mètres. None si échec."""
    try:
        r = requests.get(
            "https://api.open-elevation.com/api/v1/lookup",
            params={"locations": f"{lat},{lon}"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return float(r.json()["results"][0]["elevation"])
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None
