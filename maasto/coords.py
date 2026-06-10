"""Parsing coordonnées : décimal et DMS."""
import re
from dataclasses import dataclass


@dataclass
class LatLon:
    lat: float
    lon: float

    def __str__(self) -> str:
        return f"{self.lat:.6f},{self.lon:.6f}"


_DMS = re.compile(
    r"""(?P<deg>\d+)\s*[°d]\s*
        (?:(?P<min>\d+)\s*['′m]\s*)?
        (?:(?P<sec>[\d.]+)\s*["″s]?\s*)?
        (?P<hem>[NSEW])""",
    re.VERBOSE,
)


def _dms_to_dec(deg: float, minutes: float, seconds: float, hem: str) -> float:
    val = deg + minutes / 60 + seconds / 3600
    if hem in ("S", "W"):
        val = -val
    return val


def parse(text: str) -> LatLon:
    """Parse une chaîne de coords. Décimal ou DMS, séparateur virgule/espace."""
    text = text.strip()

    matches = list(_DMS.finditer(text))
    if len(matches) >= 2:
        parts = []
        for m in matches[:2]:
            d = float(m.group("deg"))
            mn = float(m.group("min") or 0)
            s = float(m.group("sec") or 0)
            parts.append(_dms_to_dec(d, mn, s, m.group("hem")))
        lat_or_lon = [p for p in parts if -90 <= p <= 90]
        if not lat_or_lon:
            raise ValueError(f"Pas de latitude détectable dans {text!r}")
        lat = lat_or_lon[0]
        lon = next(p for p in parts if p is not lat)
        return LatLon(lat=lat, lon=lon)

    cleaned = text.replace(";", ",").replace(" ", ",")
    parts = [p for p in cleaned.split(",") if p]
    if len(parts) != 2:
        raise ValueError(f"Coords non parsables : {text!r}")
    return LatLon(lat=float(parts[0]), lon=float(parts[1]))
