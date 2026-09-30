"""Generates ILLUSTRATIVE sample GeoJSON per state/cyclone into /data.
Replace with real data (IBTrACS track, GEE/SRTM flood zone, OSM assets) using the same file names."""
import json, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "data")

def box(w, s, e, n): return [[[w, s], [e, s], [e, n], [w, n], [w, s]]]
def fc(feats): return {"type": "FeatureCollection", "features": feats}
def poly(props, b): return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": box(*b)}}
def pt(name, t, lon, lat): return {"type": "Feature", "properties": {"name": name, "type": t}, "geometry": {"type": "Point", "coordinates": [lon, lat]}}

D = {
 "odisha/fani_2019": dict(
  districts={"Puri": (85.5, 19.6, 86.2, 20.0), "Khordha": (85.2, 20.0, 85.9, 20.5),
             "Cuttack": (85.9, 20.0, 86.6, 20.6), "Ganjam": (84.6, 19.2, 85.5, 19.9)},
  flood=[(85.55, 19.6, 86.2, 19.9), (85.6, 20.0, 85.9, 20.15), (85.1, 19.3, 85.5, 19.6)],
  track=[[85.6, 17.0], [85.9, 18.5], [85.85, 19.79], [85.9, 20.4], [86.5, 21.2]], wind=215,
  assets=[("Puri Coastal Substation", "substation", 85.83, 19.81), ("Puri District Hospital", "hospital", 85.85, 19.80),
          ("Marine Drive Bridge", "road", 85.75, 19.72), ("Puri Cyclone Shelter A", "shelter", 85.80, 19.78),
          ("Konark Road Shelter", "shelter", 85.95, 19.75), ("Puri Inland Hospital", "hospital", 85.90, 19.95),
          ("Puri North Substation", "substation", 85.70, 19.95), ("Khordha Lowland Substation", "substation", 85.75, 20.10),
          ("NH-316 Causeway", "road", 85.70, 20.05), ("Bhubaneswar Medical Hub", "hospital", 85.83, 20.27),
          ("Khordha Shelter B", "shelter", 85.40, 20.20), ("Cuttack Central Hospital", "hospital", 86.20, 20.40),
          ("Cuttack Grid Substation", "substation", 86.10, 20.30), ("Ganjam Coast Shelter", "shelter", 85.30, 19.45),
          ("Ganjam Grid Station", "substation", 85.00, 19.50), ("Berhampur Hospital", "hospital", 84.90, 19.30)]),
 "andhra_pradesh/michaung_2023": dict(
  districts={"Nellore": (79.6, 13.9, 80.4, 14.8), "Prakasam": (79.6, 14.8, 80.4, 15.7),
             "Bapatla": (80.1, 15.7, 80.8, 16.2), "Krishna": (80.8, 15.8, 81.5, 16.5)},
  flood=[(80.0, 14.0, 80.4, 14.6), (80.0, 15.0, 80.4, 15.6), (80.3, 15.7, 80.8, 16.0), (80.9, 15.9, 81.3, 16.2)],
  track=[[82.0, 12.5], [81.0, 13.6], [80.3, 14.9], [80.45, 15.9], [80.7, 16.6]], wind=110,
  assets=[("Nellore Port Substation", "substation", 80.10, 14.30), ("Nellore Coastal Hospital", "hospital", 80.20, 14.45),
          ("Krishnapatnam Road Link", "road", 80.15, 14.25), ("Nellore Shelter 1", "shelter", 80.25, 14.10),
          ("Nellore City Hospital", "hospital", 79.98, 14.44), ("Prakasam Coast Substation", "substation", 80.20, 15.30),
          ("Ongole Shelter", "shelter", 80.05, 15.50), ("Ongole GH", "hospital", 79.75, 15.50),
          ("Bapatla Beach Road", "road", 80.50, 15.85), ("Bapatla Cyclone Shelter", "shelter", 80.45, 15.90),
          ("Bapatla Area Hospital", "hospital", 80.47, 15.75), ("Guntur Link Substation", "substation", 80.20, 16.10),
          ("Machilipatnam Substation", "substation", 81.10, 16.00), ("Krishna District Hospital", "hospital", 81.15, 16.35),
          ("Krishna Delta Shelter", "shelter", 81.00, 16.05), ("Vijayawada Road Node", "road", 81.00, 16.30)]),
 "west_bengal/amphan_2020": dict(
  districts={"South 24 Parganas": (88.0, 21.5, 89.0, 22.4), "North 24 Parganas": (88.4, 22.4, 89.1, 23.2),
             "Purba Medinipur": (87.4, 21.6, 88.0, 22.2), "Kolkata": (88.2, 22.4, 88.4, 22.65)},
  flood=[(88.1, 21.6, 88.9, 22.1), (87.6, 21.6, 88.0, 21.9), (88.28, 22.42, 88.36, 22.5), (88.7, 22.4, 89.0, 22.6)],
  track=[[88.0, 19.5], [88.1, 20.8], [88.15, 21.65], [88.4, 22.6], [88.7, 23.6]], wind=155,
  assets=[("Sagar Island Substation", "substation", 88.10, 21.70), ("Sagar Hospital", "hospital", 88.05, 21.80),
          ("Gosaba Embankment Road", "road", 88.70, 22.00), ("Sundarbans Shelter 1", "shelter", 88.60, 21.90),
          ("Diamond Harbour Hospital", "hospital", 88.20, 22.20), ("Kakdwip Substation", "substation", 88.20, 21.85),
          ("Canning Grid Substation", "substation", 88.65, 22.31), ("Digha Coastal Shelter", "shelter", 87.75, 21.70),
          ("Contai Hospital", "hospital", 87.75, 21.80), ("Haldia Road Link", "road", 87.90, 22.05),
          ("Tamluk Hospital", "hospital", 87.60, 22.05), ("Kolkata Port Substation", "substation", 88.32, 22.45),
          ("Kolkata Riverside Shelter", "shelter", 88.30, 22.48), ("SSKM Hospital", "hospital", 88.35, 22.54),
          ("Basirhat Hospital", "hospital", 88.85, 22.65), ("Sandeshkhali Shelter", "shelter", 88.85, 22.50),
          ("Barasat Substation", "substation", 88.50, 22.72)]),
}
for path, d in D.items():
    out = os.path.join(ROOT, path); os.makedirs(out, exist_ok=True)
    def w(n, o): json.dump(o, open(os.path.join(out, n), "w"), indent=1)
    w("districts.geojson", fc([poly({"district": k}, v) for k, v in d["districts"].items()]))
    w("flood_zone.geojson", fc([poly({"risk_level": "High", "note": "illustrative screening zone"}, b) for b in d["flood"]]))
    w("assets.geojson", fc([pt(*a) for a in d["assets"]]))
    w("track.geojson", fc([{"type": "Feature", "properties": {"max_wind_kmh": d["wind"]},
                            "geometry": {"type": "LineString", "coordinates": d["track"]}}]))
print("sample data written")
