"""Bulletins avalanche : SLF (Suisse, JSON) + Météo-France BERA (FR, fragile)."""
import re

import requests

_TIMEOUT = 15
_UA = "maasto/0.1"

_FR_MASSIFS = {
    "haute-tarentaise": (45.6, 6.9), "beaufortain": (45.7, 6.6),
    "haute-maurienne": (45.3, 6.9), "vanoise": (45.4, 6.8),
    "mont-blanc": (45.85, 6.85), "aravis": (45.9, 6.45),
    "bauges": (45.65, 6.2), "chartreuse": (45.35, 5.85),
    "belledonne": (45.2, 6.05), "grandes-rousses": (45.15, 6.15),
    "oisans": (45.0, 6.2), "ecrins": (44.9, 6.3),
    "haut-var-haut-verdon": (44.2, 6.6), "queyras": (44.7, 6.85),
    "cerces": (45.1, 6.55), "thabor": (45.15, 6.55),
    "mercantour": (44.15, 7.2), "ubaye": (44.4, 6.7),
    "champsaur": (44.7, 6.2), "devoluy": (44.7, 5.9),
    "vercors": (45.05, 5.5), "pelvoux": (44.85, 6.5),
}


def nearest_fr_massif(lat: float, lon: float) -> str:
    """Massif Météo-France BERA le plus proche."""
    return min(_FR_MASSIFS, key=lambda m: (
        (lat - _FR_MASSIFS[m][0]) ** 2 + (lon - _FR_MASSIFS[m][1]) ** 2
    ))


def fetch_fr(lat: float, lon: float) -> dict:
    """BERA Météo-France : best effort, retourne URL + niveau si parsable."""
    massif = nearest_fr_massif(lat, lon)
    url = f"https://meteofrance.com/meteo-montagne/{massif}/risque-avalanche"
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
        if r.status_code != 200:
            return {"massif": massif, "url": url, "level": None, "available": False}
        # Parse approximatif niveau de risque
        m = re.search(r'"riskLevel"\s*:\s*"?(\d)"?', r.text)
        level = int(m.group(1)) if m else None
        return {
            "massif": massif, "url": url,
            "level": level, "level_label": _LEVEL_LABEL.get(level),
            "available": True,
        }
    except requests.RequestException:
        return {"massif": massif, "url": url, "level": None, "available": False}


def fetch_ch(lat: float, lon: float) -> dict:
    """SLF Suisse : API JSON publique."""
    try:
        r = requests.get(
            "https://aws.slf.ch/api/bulletin/caaml/en/CAAMLv6_2017",
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return {"available": True, "url": "https://www.slf.ch", "raw_size": len(r.text)}
    except requests.RequestException:
        return {"available": False, "url": "https://www.slf.ch"}


_LEVEL_LABEL = {
    1: "Faible", 2: "Limité", 3: "Marqué", 4: "Fort", 5: "Très fort",
}


def fetch(lat: float, lon: float) -> dict:
    """Dispatch FR/CH selon coords."""
    in_ch = 45.7 <= lat <= 47.9 and 5.9 <= lon <= 10.5
    if in_ch:
        return {"source": "SLF", **fetch_ch(lat, lon)}
    return {"source": "Météo-France", **fetch_fr(lat, lon)}
