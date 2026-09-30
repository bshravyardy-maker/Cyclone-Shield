"""Writes config/states.json (6 states, 10 cyclones) and ILLUSTRATIVE sample data for cyclones not yet generated.
Geography is approximate; swap in real IBTrACS / GEE / OSM data using the same file names."""
import json, os, random
R = os.path.join(os.path.dirname(__file__), "..")
def S(name, lang, lname, sdma, center, zoom, cyc): return dict(name=name, language_code=lang, language_name=lname,
    sdma_contact=sdma, center=center, zoom=zoom, cyclones=[dict(id=i, name=n) for i, n in cyc])
STATES = {
 "odisha": S("Odisha", "or", "Odia", "OSDMA (placeholder)", [20.2, 86.2], 8, [("fani_2019", "Cyclone Fani (2019)"), ("yaas_2021", "Cyclone Yaas (2021)"), ("dana_2024", "Cyclone Dana (2024)")]),
 "andhra_pradesh": S("Andhra Pradesh", "te", "Telugu", "APSDMA (placeholder)", [16.5, 81.8], 7, [("michaung_2023", "Cyclone Michaung (2023)"), ("hudhud_2014", "Cyclone Hudhud (2014)")]),
 "west_bengal": S("West Bengal", "bn", "Bengali", "WB Disaster Mgmt Dept (placeholder)", [22.0, 88.4], 8, [("amphan_2020", "Cyclone Amphan (2020)")]),
 "tamil_nadu": S("Tamil Nadu", "ta", "Tamil", "TNSDMA (placeholder)", [11.8, 79.8], 7, [("vardah_2016", "Cyclone Vardah (2016)"), ("gaja_2018", "Cyclone Gaja (2018)")]),
 "gujarat": S("Gujarat", "gu", "Gujarati", "GSDMA (placeholder)", [22.9, 69.6], 7, [("biparjoy_2023", "Cyclone Biparjoy (2023)")]),
 "maharashtra": S("Maharashtra", "mr", "Marathi", "MSDMA (placeholder)", [18.4, 73.1], 8, [("nisarga_2020", "Cyclone Nisarga (2020)")]),
}
# districts: name -> (west, south, east, north, sea side); track: [lon, lat] points
NEW = {
 "odisha/yaas_2021": dict(wind=130, track=[[87.5,19.0],[87.3,20.0],[87.0,21.3],[86.5,22.5],[85.8,23.6]], d={
    "Balasore": (86.6,21.2,87.4,21.9,"e"), "Bhadrak": (86.2,20.7,87.0,21.2,"e"),
    "Kendrapara": (86.2,20.3,87.0,20.7,"e"), "Jagatsinghpur": (86.0,19.95,86.9,20.3,"e")}),
 "odisha/dana_2024": dict(wind=120, track=[[87.8,19.0],[87.2,20.2],[86.9,20.75],[86.4,21.6],[85.9,22.6]], d={
    "Balasore": (86.6,21.2,87.4,21.9,"e"), "Bhadrak": (86.2,20.7,87.0,21.2,"e"),
    "Kendrapara": (86.2,20.3,87.0,20.7,"e"), "Jagatsinghpur": (86.0,19.95,86.9,20.3,"e")}),
 "andhra_pradesh/hudhud_2014": dict(wind=185, track=[[84.0,13.0],[83.6,15.5],[83.3,17.7],[83.0,19.0],[82.5,20.5]], d={
    "Visakhapatnam": (83.0,17.4,83.6,17.95,"e"), "Vizianagaram": (83.2,17.95,83.9,18.5,"e"),
    "Srikakulam": (83.6,18.5,84.5,19.0,"e"), "East Godavari": (81.9,16.6,82.6,17.4,"e")}),
 "tamil_nadu/vardah_2016": dict(wind=130, track=[[84.0,12.5],[82.5,12.9],[81.2,13.0],[80.27,13.08],[79.0,12.8]], d={
    "Chennai": (80.15,13.0,80.32,13.2,"e"), "Tiruvallur": (79.8,13.2,80.3,13.7,"e"),
    "Chengalpattu": (79.8,12.4,80.3,13.0,"e"), "Villupuram": (79.4,11.7,80.0,12.4,"e")}),
 "tamil_nadu/gaja_2018": dict(wind=120, track=[[83.0,11.0],[82.0,10.9],[80.6,10.45],[79.85,10.45],[78.5,10.2]], d={
    "Cuddalore": (79.4,11.3,79.95,11.9,"e"), "Nagapattinam": (79.5,10.7,80.0,11.3,"e"),
    "Thanjavur": (78.9,10.3,79.5,10.9,"e"), "Pudukkottai": (78.9,9.8,79.5,10.3,"e")}),
 "gujarat/biparjoy_2023": dict(wind=140, track=[[67.0,20.0],[67.2,21.5],[67.6,22.6],[68.7,23.25],[70.0,24.3]], d={
    "Kutch": (68.4,23.0,70.0,23.9,"s"), "Devbhumi Dwarka": (68.6,22.0,69.5,22.9,"w"),
    "Jamnagar": (69.6,22.2,70.5,22.9,"n"), "Morbi": (70.5,22.7,71.1,23.3,"n")}),
 "maharashtra/nisarga_2020": dict(wind=110, track=[[70.8,15.5],[71.5,16.8],[72.2,17.9],[72.9,18.6],[73.9,19.5]], d={
    "Raigad": (72.9,18.1,73.4,18.8,"w"), "Ratnagiri": (73.0,16.9,73.6,17.9,"w"),
    "Palghar": (72.7,19.3,73.2,19.95,"w"), "Mumbai Suburban": (72.78,18.9,73.0,19.3,"w")}),
}
KINDS = [("Grid Substation", "substation"), ("District Hospital", "hospital"), ("Coastal Road Link", "road"),
         ("Cyclone Shelter", "shelter"), ("Backup Substation", "substation"), ("Community Health Centre", "hospital"),
         ("Bridge", "road"), ("Relief Shelter", "shelter")]
def box(w, s, e, n): return [[[w, s], [e, s], [e, n], [w, n], [w, s]]]
def fc(f): return {"type": "FeatureCollection", "features": f}
def poly(p, b): return {"type": "Feature", "properties": p, "geometry": {"type": "Polygon", "coordinates": box(*b)}}
def surge_box(w, s, e, n, side, depth):
    dx, dy = (e - w) * depth, (n - s) * depth
    return {"e": (e - dx, s, e, n), "w": (w, s, w + dx, n), "s": (w, s, e, s + dy), "n": (w, n - dy, e, n)}[side]

with open(os.path.join(R, "config", "states.json"), "w") as f:
    json.dump(STATES, f, indent=1)
for path, c in NEW.items():
    out = os.path.join(R, "data", path)
    if os.path.isdir(out): continue
    os.makedirs(out); rnd = random.Random(path)
    floods, assets = [], []
    for dn, (w, s, e, n, side) in c["d"].items():
        floods.append(poly({"risk_level": "High", "district": dn, "note": "illustrative screening zone"}, surge_box(w, s, e, n, side, rnd.uniform(.45, .6))))
        for i in range(7):
            lbl, t = KINDS[i]
            assets.append({"type": "Feature", "properties": {"name": f"{dn} {lbl}", "type": t},
                           "geometry": {"type": "Point", "coordinates": [round(rnd.uniform(w + .02, e - .02), 4), round(rnd.uniform(s + .02, n - .02), 4)]}})
    def wr(n_, o): json.dump(o, open(os.path.join(out, n_), "w"), indent=1)
    wr("districts.geojson", fc([poly({"district": k}, v[:4]) for k, v in c["d"].items()]))
    wr("flood_zone.geojson", fc(floods)); wr("assets.geojson", fc(assets))
    wr("track.geojson", fc([{"type": "Feature", "properties": {"max_wind_kmh": c["wind"]}, "geometry": {"type": "LineString", "coordinates": c["track"]}}]))
    print("wrote", path)
