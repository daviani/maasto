"""Sentinel-2 STAC via Element84 + crop COG."""
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import rasterio
import requests
from PIL import Image
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

_TIMEOUT = 30
_STAC = "https://earth-search.aws.element84.com/v1/search"


def search(lat: float, lon: float, days_back: int = 14, max_cloud: float = 30,
           buffer_deg: float = 0.06) -> list[dict]:
    """Liste les acquisitions Sentinel-2 récentes triées par date desc."""
    bbox = [lon - buffer_deg, lat - buffer_deg,
            lon + buffer_deg, lat + buffer_deg]
    end = datetime.utcnow()
    start = end - timedelta(days=days_back)

    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{start.strftime('%Y-%m-%dT00:00:00Z')}/{end.strftime('%Y-%m-%dT23:59:59Z')}",
        "limit": 30,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }
    r = requests.post(_STAC, json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    feats = r.json().get("features", [])

    out = []
    for f in feats:
        p = f["properties"]
        cloud = p.get("eo:cloud_cover", 100)
        out.append({
            "id": f["id"],
            "datetime": p["datetime"],
            "date": p["datetime"][:10],
            "cloud_cover": cloud,
            "tci_url": f.get("assets", {}).get("visual", {}).get("href"),
            "thumbnail": f.get("assets", {}).get("thumbnail", {}).get("href"),
            "usable": cloud <= max_cloud,
        })
    return out


def best_pair(scenes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Retourne (candidats_récents, candidats_anciens) classés par cloud_cover.
    Plusieurs candidats par groupe pour pouvoir tomber sur la bonne tuile
    si la première échoue au crop."""
    usable = [s for s in scenes if s["usable"]]
    if not usable:
        return [], []
    by_date = {}
    for s in usable:
        by_date.setdefault(s["date"], []).append(s)
    dates_desc = sorted(by_date.keys(), reverse=True)
    recent = sorted(by_date[dates_desc[0]], key=lambda s: s["cloud_cover"])
    if len(dates_desc) == 1:
        return recent, []
    older = sorted(by_date[dates_desc[-1]], key=lambda s: s["cloud_cover"])
    return recent, older


def crop(scene: dict, lat: float, lon: float, output_path: Path,
         bbox_size_km: float = 8.0) -> Path:
    """Crop une scène Sentinel-2 autour du point. Sauve en PNG."""
    if not scene.get("tci_url"):
        raise ValueError(f"Pas de TCI pour {scene['id']}")

    half_lat = (bbox_size_km / 2) / 111.0
    half_lon = (bbox_size_km / 2) / (111.0 * abs(np.cos(np.radians(lat))))
    bbox = (lon - half_lon, lat - half_lat, lon + half_lon, lat + half_lat)

    with rasterio.open(f"/vsicurl/{scene['tci_url']}") as src:
        bounds_utm = transform_bounds("EPSG:4326", src.crs, *bbox)
        win = from_bounds(*bounds_utm, transform=src.transform)
        full = Window(0, 0, src.width, src.height)
        win = win.intersection(full).round_offsets().round_lengths()
        if win.width < 10 or win.height < 10:
            raise ValueError(f"Crop window hors tuile ou trop petite : {win}")
        data = src.read(window=win)

    if data.size == 0 or data.shape[1] == 0 or data.shape[2] == 0:
        raise ValueError("Crop vide après lecture")
    if not data.any():
        raise ValueError("Crop = pixels noirs (hors footprint utile)")

    img = np.transpose(data, (1, 2, 0))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as fh:
        Image.fromarray(img).save(fh, format="PNG")
    return output_path
