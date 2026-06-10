"""API publique Camptocamp.org : sorties récentes + signal terrain.

Note : Camptocamp attend la bbox en EPSG:3857 (Web Mercator), pas WGS84.
"""
import math
from collections import Counter
from datetime import datetime, timedelta

import requests

# Activités qui indiquent de la neige praticable
_SNOW_ACTS = {"skitouring", "snowshoeing", "snow_ice_mixed", "ice_climbing"}
# Activités sans neige
_DRY_ACTS = {"hiking", "rock_climbing", "mountain_biking"}

_TIMEOUT = 15
_BASE = "https://api.camptocamp.org"


def _wgs84_to_3857(lon: float, lat: float) -> tuple[float, float]:
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    return x, y * 20037508.34 / 180


def recent_outings(lat: float, lon: float, radius_km: float = 15,
                   days_back: int = 30, limit: int = 20) -> list[dict]:
    """Sorties postées dans une bbox autour du point sur les N derniers jours."""
    half = radius_km / 111.0
    xmin, ymin = _wgs84_to_3857(lon - half, lat - half)
    xmax, ymax = _wgs84_to_3857(lon + half, lat + half)

    since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    params = {
        "bbox": f"{xmin:.0f},{ymin:.0f},{xmax:.0f},{ymax:.0f}",
        "limit": limit,
        "date_start": since,
    }
    try:
        r = requests.get(f"{_BASE}/outings", params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        d = r.json()
    except requests.RequestException:
        return []

    out = []
    for o in d.get("documents", []):
        loc = next((loc for loc in o.get("locales", []) if loc.get("lang") == "fr"),
                   o.get("locales", [{}])[0] if o.get("locales") else {})
        out.append({
            "id": o.get("document_id"),
            "title": loc.get("title", "Sortie"),
            "date_start": o.get("date_start"),
            "date_end": o.get("date_end"),
            "activities": o.get("activities", []),
            "elevation_max": o.get("elevation_max"),
            "url": f"https://www.camptocamp.org/outings/{o.get('document_id')}",
        })
    return out


def signal(outings: list[dict], modeled_snow_below: float) -> dict:
    """Synthèse 'terrain' à partir des sorties C2C.

    Args:
        outings: liste de sorties (sortie de recent_outings)
        modeled_snow_below: snow_depth modèle le plus bas observé (m), pour
                            détecter une discordance avec le terrain.
    """
    if not outings:
        return {"total": 0, "available": False}

    acts = Counter()
    for o in outings:
        for a in o.get("activities", []):
            acts[a] += 1

    snow_acts = sum(acts[a] for a in _SNOW_ACTS if a in acts)
    dry_acts = sum(acts[a] for a in _DRY_ACTS if a in acts)
    total_acts = max(snow_acts + dry_acts, 1)
    snow_ratio = snow_acts / total_acts

    snow_alts = [o.get("elevation_max") for o in outings
                 if o.get("elevation_max") and
                 any(a in _SNOW_ACTS for a in o.get("activities", []))]
    all_alts = sorted(o.get("elevation_max") for o in outings if o.get("elevation_max"))
    median_alt = all_alts[len(all_alts) // 2] if all_alts else None
    min_snow_alt = min(snow_alts) if snow_alts else None

    # Discordance : modèle dit déneigé (< 20 cm) mais > 50% activités neige
    discordance = (modeled_snow_below < 0.20 and snow_ratio > 0.5
                   and min_snow_alt is not None)

    if discordance:
        verdict = (f"⚠️ Discordance modèle/terrain — {snow_ratio:.0%} des sorties "
                   f"en activité neige, dont des sorties qui démarrent à "
                   f"{min_snow_alt} m. Privilégier le terrain : la limite neige "
                   f"est probablement bien plus basse que ce que le modèle indique.")
        level = "danger"
    elif snow_ratio > 0.5:
        verdict = (f"{snow_ratio:.0%} des sorties en activité neige, "
                   f"alt min observée : {min_snow_alt} m. Manteau encore présent.")
        level = "warn"
    elif snow_ratio < 0.2 and dry_acts > 0:
        verdict = (f"{(1 - snow_ratio):.0%} des sorties en rando/escalade — "
                   f"zone passée en mode estival.")
        level = "ok"
    else:
        verdict = f"Activités mixtes ({snow_acts} neige / {dry_acts} sec)."
        level = "warn"

    dates = sorted(o.get("date_start") for o in outings if o.get("date_start"))

    return {
        "total": len(outings),
        "available": True,
        "date_min": dates[0] if dates else None,
        "date_max": dates[-1] if dates else None,
        "activities": dict(acts),
        "snow_count": snow_acts,
        "dry_count": dry_acts,
        "snow_ratio": snow_ratio,
        "min_snow_alt": min_snow_alt,
        "median_alt": median_alt,
        "discordance": discordance,
        "verdict": verdict,
        "level": level,
    }
