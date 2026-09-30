#!/usr/bin/env python3
"""Fetch REAL data for one state/cyclone and write the 4 GeoJSON files the app reads.

  districts.geojson  <- geoBoundaries India ADM2 (open licence)
  track.geojson      <- NOAA IBTrACS v04r01, North Indian basin
  assets.geojson     <- OpenStreetMap via Overpass (substations, hospitals, bridges, shelters)
  flood_zone.geojson <- bathtub screening model on Copernicus DEM (Open-Meteo elevation API), no login needed

Usage (from project root):
  pip install -r scripts/requirements-data.txt
  python scripts/fetch_real_data.py --state odisha --cyclone fani_2019
  python scripts/fetch_real_data.py --state gujarat --cyclone biparjoy_2023 --surge 3 --only assets,flood
Options: --surge METRES (storm-tide height, take it from the IMD bulletin), --radius KM (surge decay from landfall),
         --step DEG (grid size, default 0.03), --bbox W,S,E,N (default: sample districts' bbox, padded).
Old sample files are kept in data/<state>/<cyclone>/_sample/.
The flood zone is a fast SCREENING model, not a hydrodynamic simulation. Say so in the pitch.
"""
import argparse, csv, io, json, math, os, shutil, sys, time
from pathlib import Path
import numpy as np
import requests
from shapely.geometry import shape, mapping, box, Point
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "CycloneShield-hackathon/1.0 (educational)"}
IBTRACS = "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv"
GEOB = "https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
ELEV = "https://api.open-meteo.com/v1/elevation"
STORMS = {"fani_2019": ("FANI", 2019), "yaas_2021": ("YAAS", 2021), "dana_2024": ("DANA", 2024),
          "michaung_2023": ("MICHAUNG", 2023), "hudhud_2014": ("HUDHUD", 2014), "amphan_2020": ("AMPHAN", 2020),
          "vardah_2016": ("VARDAH", 2016), "gaja_2018": ("GAJA", 2018), "biparjoy_2023": ("BIPARJOY", 2023),
          "nisarga_2020": ("NISARGA", 2020)}
CAPS = {"substation": 250, "hospital": 250, "road": 150, "shelter": 250}

def log(*a): print(*a, flush=True)

# ---------- districts ----------
def fetch_districts(bbox):
    meta = requests.get(GEOB, headers=UA, timeout=60).json()
    meta = meta[0] if isinstance(meta, list) else meta
    gj = requests.get(meta["gjDownloadURL"], headers=UA, timeout=300).json()
    area = box(*bbox); feats = []
    for f in gj["features"]:
        g = shape(f["geometry"])
        if g.representative_point().within(area) or g.centroid.within(area):
            g = g.simplify(0.004)
            feats.append({"type": "Feature", "properties": {"district": f["properties"].get("shapeName", "District")},
                          "geometry": mapping(g)})
    return {"type": "FeatureCollection", "features": feats}

# ---------- IBTrACS track ----------
def parse_ibtracs(text, name, season):
    rows = list(csv.reader(io.StringIO(text)))
    head = rows[0]; ix = {h: i for i, h in enumerate(head)}
    by_sid = {}
    for r in rows[2:]:                       # row 1 holds units
        if len(r) < len(head) or r[ix["NAME"]].strip().upper() != name or r[ix["SEASON"]].strip() != str(season):
            continue
        if "TRACK_TYPE" in ix and r[ix["TRACK_TYPE"]].strip().lower() == "spur":
            continue
        try: lat, lon = float(r[ix["LAT"]]), float(r[ix["LON"]])
        except ValueError: continue
        wind = 0.0
        for col in ("WMO_WIND", "USA_WIND", "BOM_WIND"):
            if col in ix:
                try: wind = float(r[ix[col]]); break
                except ValueError: pass
        by_sid.setdefault(r[ix["SID"]], []).append((r[ix["ISO_TIME"]], lon, lat, wind * 1.852))
    if not by_sid: raise ValueError(f"{name} {season} not found in IBTrACS NI file")
    sid = max(by_sid, key=lambda k: len(by_sid[k]))
    pts = sorted(by_sid[sid])
    return sid, [[p[1], p[2]] for p in pts], round(max(p[3] for p in pts))

def fetch_track(name, season):
    log("  downloading IBTrACS NI file (~30 MB)...")
    text = requests.get(IBTRACS, headers=UA, timeout=300).text
    sid, coords, wind = parse_ibtracs(text, name, season)
    return {"type": "FeatureCollection", "features": [{"type": "Feature",
        "properties": {"sid": sid, "name": name, "season": season, "max_wind_kmh": wind, "source": "IBTrACS v04r01"},
        "geometry": {"type": "LineString", "coordinates": coords}}]}

# ---------- OSM assets ----------
def overpass_query(b):
    w, s, e, n = b; bb = f"({s},{w},{n},{e})"
    return f"""[out:json][timeout:180];
(
 nwr["power"="substation"]{bb};
 nwr["amenity"="hospital"]{bb};
 nwr["healthcare"="hospital"]{bb};
 nwr["amenity"="shelter"]["name"~"cyclone|flood|relief|multipurpose|MPCS",i]{bb};
 nwr["name"~"cyclone shelter|multi.?purpose cyclone",i]{bb};
 nwr["emergency"="assembly_point"]{bb};
 way["bridge"="yes"]["highway"~"^(motorway|trunk|primary|secondary)$"]{bb};
);
out center tags;"""

def classify(t):
    if t.get("power") == "substation": return "substation"
    if t.get("amenity") == "hospital" or t.get("healthcare") == "hospital": return "hospital"
    if t.get("bridge") == "yes": return "road"
    return "shelter"

def parse_overpass(data, region=None):
    seen, per = set(), {k: [] for k in CAPS}
    for el in data.get("elements", []):
        t = el.get("tags", {})
        lat = el.get("lat", (el.get("center") or {}).get("lat")); lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if lat is None or lon is None: continue
        if region is not None and not region.contains(Point(lon, lat)): continue
        kind = classify(t)
        nm = t.get("name") or t.get("name:en") or t.get("ref")
        key = (kind, round(lat, 4), round(lon, 4))
        if key in seen: continue
        seen.add(key)
        per[kind].append((nm is None, {"type": "Feature",
            "properties": {"name": nm or f"{kind.title()} (OSM {el['type']}/{el['id']})", "type": kind, "osm_id": f"{el['type']}/{el['id']}"},
            "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]}}))
    feats = []
    for kind, lst in per.items():
        lst.sort(key=lambda x: x[0])           # named features first
        feats += [f for _, f in lst[:CAPS[kind]]]
    return {"type": "FeatureCollection", "features": feats}

def fetch_assets(bbox, region):
    q = overpass_query(bbox); last = None
    for url in OVERPASS * 2:
        try:
            r = requests.post(url, data={"data": q}, headers=UA, timeout=240)
            r.raise_for_status(); return parse_overpass(r.json(), region)
        except Exception as e:
            last = e; log("  Overpass retry:", e); time.sleep(8)
    raise RuntimeError(f"Overpass failed: {last}")

# ---------- flood zone (bathtub screening) ----------
def elevations(lats, lons):
    out = []
    for i in range(0, len(lats), 100):
        la = ",".join(f"{x:.4f}" for x in lats[i:i + 100]); lo = ",".join(f"{x:.4f}" for x in lons[i:i + 100])
        for attempt in range(4):
            r = requests.get(ELEV, params={"latitude": la, "longitude": lo}, headers=UA, timeout=60)
            if r.status_code == 429: time.sleep(10 * (attempt + 1)); continue
            r.raise_for_status(); break
        out += [np.nan if v is None else float(v) for v in r.json()["elevation"]]
        time.sleep(0.4)
    return np.array(out)

def haversine_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180; a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))

def find_landfall(coords, elev_fn=elevations):
    idx = list(range(0, len(coords), max(1, len(coords) // 90)))[:100]
    el = elev_fn([coords[i][1] for i in idx], [coords[i][0] for i in idx])
    for k in range(1, len(idx)):
        if el[k] > 1 and (np.isnan(el[k - 1]) or el[k - 1] <= 1):
            return coords[idx[k]]
    return coords[len(coords) // 2]

def bathtub_flood(bbox, landfall, surge_m, step=0.03, radius_km=150, elev_fn=elevations):
    from scipy import ndimage
    w, s, e, n = bbox
    lons = np.arange(w + step / 2, e, step); lats = np.arange(s + step / 2, n, step)
    LON, LAT = np.meshgrid(lons, lats)
    if LON.size > 9000: raise SystemExit(f"Grid too large ({LON.size} points). Use a bigger --step.")
    log(f"  sampling elevation at {LON.size} grid points...")
    elev = elev_fn(LAT.ravel(), LON.ravel()).reshape(LON.shape)
    sea = np.isnan(elev) | (elev <= 0)
    d = haversine_km(LAT, LON, landfall[1], landfall[0])
    h_eff = surge_m * np.clip(1 - d / radius_km, 0, 1)
    flooded = sea | (elev <= h_eff)
    lab, _ = ndimage.label(flooded, structure=np.ones((3, 3)))
    sea_labels = np.unique(lab[sea & (lab > 0)])
    keep = np.isin(lab, sea_labels) & ~sea & flooded
    if not keep.any(): return {"type": "FeatureCollection", "features": []}
    h = step / 2
    cells = [box(x - h, y - h, x + h, y + h) for x, y in zip(LON[keep], LAT[keep])]
    geom = unary_union(cells).simplify(step * 0.2)
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    props = {"risk_level": "High", "surge_m": surge_m, "method": "Bathtub screening, Copernicus DEM via Open-Meteo elevation API"}
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": props, "geometry": mapping(p)}
            for p in polys if p.area > step * step * 0.5]}

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True); ap.add_argument("--cyclone", required=True)
    ap.add_argument("--surge", type=float, default=2.5, help="storm-tide height in metres (screening assumption)")
    ap.add_argument("--radius", type=float, default=150); ap.add_argument("--step", type=float, default=0.03)
    ap.add_argument("--bbox"); ap.add_argument("--only", default="districts,track,assets,flood")
    a = ap.parse_args()
    if a.cyclone not in STORMS: sys.exit(f"Unknown cyclone. Known: {', '.join(STORMS)}")
    d = ROOT / "data" / a.state / a.cyclone; d.mkdir(parents=True, exist_ok=True)
    if a.bbox: bbox = [float(x) for x in a.bbox.split(",")]
    else:
        gj = json.loads((d / "districts.geojson").read_text())
        bbox = list(unary_union([shape(f["geometry"]) for f in gj["features"]]).bounds)
        bbox = [bbox[0] - .15, bbox[1] - .15, bbox[2] + .15, bbox[3] + .15]
    log("bbox W,S,E,N:", [round(x, 3) for x in bbox])
    back = d / "_sample"
    if not back.exists():
        back.mkdir()
        for f in d.glob("*.geojson"): shutil.copy(f, back / f.name)
    steps = a.only.split(","); W = lambda n, o: (d / n).write_text(json.dumps(o))
    if "districts" in steps:
        log("1/4 districts (geoBoundaries)"); dj = fetch_districts(bbox); W("districts.geojson", dj)
        log("  ", len(dj["features"]), "districts:", ", ".join(f["properties"]["district"] for f in dj["features"]))
    dj = json.loads((d / "districts.geojson").read_text())
    region = unary_union([shape(f["geometry"]) for f in dj["features"]]).buffer(0.01)
    if "track" in steps:
        log("2/4 track (IBTrACS)"); tj = fetch_track(*STORMS[a.cyclone]); W("track.geojson", tj)
        log("  ", len(tj["features"][0]["geometry"]["coordinates"]), "points, max wind", tj["features"][0]["properties"]["max_wind_kmh"], "km/h")
    if "assets" in steps:
        log("3/4 assets (OpenStreetMap)"); aj = fetch_assets(bbox, region); W("assets.geojson", aj)
        cnt = {}
        for f in aj["features"]: cnt[f["properties"]["type"]] = cnt.get(f["properties"]["type"], 0) + 1
        log("  ", cnt)
    if "flood" in steps:
        log("4/4 flood zone (bathtub screening)")
        coords = json.loads((d / "track.geojson").read_text())["features"][0]["geometry"]["coordinates"]
        lf = find_landfall(coords); log("   landfall approx (lon,lat):", [round(x, 2) for x in lf], "surge", a.surge, "m")
        fj = bathtub_flood(bbox, lf, a.surge, a.step, a.radius); W("flood_zone.geojson", fj)
        log("  ", len(fj["features"]), "flood polygons")
    log("Done. Restart the app and pick this cyclone.")

if __name__ == "__main__":
    main()
