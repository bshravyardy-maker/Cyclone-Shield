#!/usr/bin/env python3
"""OPTIONAL: build flood_zone.geojson with Google Earth Engine (SRTM + JRC surface water), instead of the Open-Meteo bathtub.
One-time setup:  pip install earthengine-api ; earthengine authenticate ; (a Google Cloud project with Earth Engine enabled)
Usage:  python scripts/flood_zone_gee.py --project YOUR_GCP_PROJECT --state odisha --cyclone fani_2019 --landfall 85.83,19.78 --surge 2.5
Method: land below the surge height that is hydrologically connected to the sea (cumulative-cost spread from permanent water),
limited to a radius around landfall. A screening model, not a hydrodynamic simulation.
"""
import argparse, json
from pathlib import Path
import ee

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--state", required=True); ap.add_argument("--cyclone", required=True)
ap.add_argument("--landfall", required=True, help="LON,LAT"); ap.add_argument("--surge", type=float, default=2.5)
ap.add_argument("--radius-km", type=float, default=150); ap.add_argument("--inland-km", type=float, default=40)
a = ap.parse_args()
ee.Initialize(project=a.project)
lon, lat = [float(x) for x in a.landfall.split(",")]
region = ee.Geometry.Point([lon, lat]).buffer(a.radius_km * 1000)
dem = ee.Image("USGS/SRTMGL1_003")                                        # 30 m elevation (masked over open sea)
sea = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gt(50).selfMask()   # permanent water = seed
candidate = dem.lte(a.surge).selfMask()                                   # land low enough to be flooded
cost = ee.Image.constant(1).updateMask(candidate.unmask(0).Or(sea.unmask(0)))
reach = cost.cumulativeCost(source=sea.unmask(0), maxDistance=a.inland_km * 1000)
flood = reach.gte(0).updateMask(dem.mask()).selfMask().clip(region)      # reachable land only
vec = flood.reduceToVectors(geometry=region, scale=90, geometryType="polygon", eightConnected=True,
                            maxPixels=int(1e10), bestEffort=True)
fc = vec.map(lambda f: f.simplify(120).set({"risk_level": "High", "surge_m": a.surge, "method": "Earth Engine SRTM bathtub"}))
out = fc.getInfo()
p = Path(__file__).resolve().parent.parent / "data" / a.state / a.cyclone / "flood_zone.geojson"
p.write_text(json.dumps(out)); print("wrote", p, "-", len(out["features"]), "polygons")
