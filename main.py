import os, json, datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from shapely.geometry import shape, Point, mapping
from shapely.ops import unary_union
from utils import ai_service, live

BASE = Path(__file__).parent
app = FastAPI(title="Cyclone Shield API", version="1.1.0")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
DISPATCH_LOG: list = []
TYPES = ("substation", "hospital", "road", "shelter")

def read(p: Path):
    return json.loads(p.read_text())

def load_states() -> dict:
    """A state/cyclone is listed only if its data folder exists -> adding one = config entry + data folder."""
    out = {}
    for k, v in read(BASE / "config" / "states.json").items():
        cy = [c for c in v.get("cyclones", []) if (BASE / "data" / k / c["id"]).is_dir()]
        if cy:
            out[k] = {**v, "cyclones": cy}
    return out

def new_row(live_mode=False):
    r = {t: 0 for t in TYPES}
    r.update(total_exposed=0, total_assets=0)
    if live_mode:
        r.update(max_gust_kmh=0, max_rain_24h_mm=0)
    return r

@app.get("/")
def root():
    return RedirectResponse("/static/index.html")

@app.get("/health")
def health():
    return {"ok": True, "gemini_key": bool(os.getenv("GEMINI_API_KEY")), "model": ai_service.MODEL}

@app.get("/states")
def states():
    return load_states()

def static_exposure(state, cyclone):
    d = BASE / "data" / state / cyclone
    try:
        districts, flood, assets, track = (read(d / f) for f in
            ("districts.geojson", "flood_zone.geojson", "assets.geojson", "track.geojson"))
    except FileNotFoundError as e:
        raise HTTPException(404, f"Missing data file: {e.filename}")
    flood_geom = unary_union([shape(f["geometry"]) for f in flood["features"]])
    dist_geoms = [(f["properties"]["district"], shape(f["geometry"])) for f in districts["features"]]
    summary = {n: new_row() for n, _ in dist_geoms}
    exposed_list = []
    for a in assets["features"]:
        pt = shape(a["geometry"])
        dist = next((n for n, g in dist_geoms if g.contains(pt)), "Unassigned")
        exp = bool(flood_geom.intersects(pt))
        a["properties"].update(exposed=exp, district=dist)
        s = summary.setdefault(dist, new_row())
        s["total_assets"] += 1
        if exp:
            t = a["properties"].get("type", "other")
            if t in s: s[t] += 1
            s["total_exposed"] += 1
            exposed_list.append({"name": a["properties"]["name"], "type": t, "district": dist})
    return {"mode": "replay", "exposure_summary": summary, "exposed_assets": exposed_list, "flood_zone": flood,
            "assets": assets, "track": track, "districts": districts, "context": "",
            "data_status": "Illustrative sample data (replace with IBTrACS / GEE / OSM outputs)"}

def live_exposure(state, conf, stress):
    d = BASE / "data" / state / conf["cyclones"][0]["id"]   # asset + district layer of the state
    districts, assets = read(d / "districts.geojson"), read(d / "assets.geojson")
    dist_geoms = [(f["properties"]["district"], shape(f["geometry"])) for f in districts["features"]]
    feats = assets["features"]
    pts = [(f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]) for f in feats]
    try:
        fc = live.fetch_forecast(pts, stress)
    except Exception as e:
        raise HTTPException(502, f"Live forecast unavailable ({e}). Check internet access.")
    summary = {n: new_row(True) for n, _ in dist_geoms}
    exposed_list, footprints = [], []
    for f, w in zip(feats, fc):
        pt = shape(f["geometry"])
        dist = next((n for n, g in dist_geoms if g.contains(pt)), "Unassigned")
        exp = w["level"] >= 2
        f["properties"].update(exposed=exp, district=dist, hazard_level=w["level"], max_gust_kmh=w["max_gust_kmh"],
                               max_rain_24h_mm=w["max_rain_24h_mm"], peak_time=w["peak_time"])
        s = summary.setdefault(dist, new_row(True))
        s["total_assets"] += 1
        s["max_gust_kmh"] = max(s["max_gust_kmh"], w["max_gust_kmh"])
        s["max_rain_24h_mm"] = max(s["max_rain_24h_mm"], w["max_rain_24h_mm"])
        if exp:
            t = f["properties"].get("type", "other")
            if t in s: s[t] += 1
            s["total_exposed"] += 1
            exposed_list.append({"name": f["properties"]["name"], "type": t, "district": dist,
                                 "peak_gust_kmh": w["max_gust_kmh"], "rain_24h_mm": w["max_rain_24h_mm"]})
        if w["level"] >= 1:
            footprints.append({"type": "Feature", "properties": {"level": w["level"]}, "geometry": mapping(pt.buffer(0.12))})
    active = live.active_cyclones()
    names = "unavailable" if active is None else (", ".join(f"{c['name']} ({c['alertlevel']})" for c in active) or "none reported")
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    ctx = (f"LIVE 72-hour forecast (Open-Meteo) generated {now} UTC. Exposed = forecast peak gust >= 62 km/h or 24h rain >= 115 mm "
           f"at the asset. Active cyclones near India (GDACS): {names}." + (f" WHAT-IF stress test x{stress}." if stress != 1 else ""))
    return {"mode": "live", "exposure_summary": summary, "exposed_assets": exposed_list,
            "flood_zone": {"type": "FeatureCollection", "features": footprints}, "assets": assets,
            "track": {"type": "FeatureCollection", "features": []}, "districts": districts, "context": ctx,
            "active_cyclones": active, "generated_at": now, "stress": stress,
            "data_status": "Live weather forecast over sample asset layer (replace assets with OSM data)"}

@app.get("/exposure")
def exposure(state: str = Query(...), cyclone: str = Query(...), stress: float = 1.0):
    states_ = load_states()
    if state not in states_:
        raise HTTPException(404, "Unknown state")
    conf = states_[state]
    if cyclone == "live":
        return live_exposure(state, conf, max(0.5, min(stress, 3.0)))
    if cyclone not in {c["id"] for c in conf["cyclones"]}:
        raise HTTPException(404, "Unknown cyclone")
    return static_exposure(state, cyclone)

class AdvisoryRequest(BaseModel):
    state: str
    exposure_summary: dict
    exposed_assets: list = []
    context: str = ""

@app.post("/advisory")
def advisory(req: AdvisoryRequest):
    states_ = load_states()
    if req.state not in states_:
        raise HTTPException(404, "State not found")
    lang = states_[req.state]["language_code"]
    adv, engine = ai_service.generate_risk_advisory(req.exposure_summary, req.exposed_assets, req.context)
    auths, cap = adv.get("authorities", {}), adv.get("cap_alert", {})
    keys = list(auths.keys())
    local, t_engine = ai_service.translate_batch([auths[k] for k in keys] + [cap.get("instruction", "")], lang)
    adv["authorities_translated"] = {k: {"english": auths[k], "local": local[i]} for i, k in enumerate(keys)}
    adv["cap_instruction_local"] = local[-1]
    adv["language_code"], adv["language_name"] = lang, states_[req.state]["language_name"]
    adv["translation_ok"] = t_engine != "unavailable"
    adv["engines"] = {"advisory": engine, "translation": t_engine, "audio_supported": lang in ai_service.TTS_LANG}
    return adv

class TTSRequest(BaseModel):
    text: str
    language_code: str

@app.post("/tts")
def tts(req: TTSRequest):
    audio = ai_service.synthesize_speech(req.text, req.language_code)
    return Response(content=audio, media_type="audio/mpeg") if audio else Response(status_code=204)

@app.post("/analyze-photo")
async def analyze_photo(file: UploadFile = File(...)):
    result, engine = ai_service.analyze_photo(await file.read(), file.content_type)
    result["engine"] = engine
    return result

class DispatchRequest(BaseModel):
    state: str
    cap_alert: dict
    message: str
    language: str = "en"

@app.post("/dispatch")
def dispatch(req: DispatchRequest):
    entry = {"id": len(DISPATCH_LOG) + 1, "time": datetime.datetime.utcnow().isoformat() + "Z", "state": req.state,
             "language": req.language, "cap": req.cap_alert, "message": req.message,
             "channel": "SMS/WhatsApp (simulated)", "status": "queued"}
    DISPATCH_LOG.append(entry)
    return entry

@app.get("/dispatch-log")
def dispatch_log():
    return DISPATCH_LOG[::-1]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
