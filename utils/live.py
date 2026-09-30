"""Live forecast mode: Open-Meteo 72h forecast per asset + active cyclones from GDACS. Both free, no key."""
import datetime, requests

OM_URL = "https://api.open-meteo.com/v1/forecast"
GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"

def _level(gust, rain24):
    # thresholds follow IMD wind (62 km/h cyclonic storm, 89 km/h severe) and rainfall (64.5 heavy, 115.6 very heavy, 204.5 extreme) classes
    g = 3 if gust >= 89 else 2 if gust >= 62 else 1 if gust >= 40 else 0
    r = 3 if rain24 >= 204 else 2 if rain24 >= 115 else 1 if rain24 >= 64.5 else 0
    return max(g, r)

def fetch_forecast(points, stress=1.0, days=3):
    """points: [(lat, lon)]. Returns one dict per point: peak gust, peak time, max 24h rain, hazard level 0-3."""
    out = []
    for i in range(0, len(points), 50):
        chunk = points[i:i + 50]
        r = requests.get(OM_URL, timeout=25, params={
            "latitude": ",".join(f"{la:.3f}" for la, _ in chunk),
            "longitude": ",".join(f"{lo:.3f}" for _, lo in chunk),
            "hourly": "wind_gusts_10m,precipitation", "forecast_days": days, "timezone": "UTC"})
        r.raise_for_status()
        data = r.json()
        data = [data] if isinstance(data, dict) else data
        for d in data:
            h = d["hourly"]
            g = [(x or 0) * stress for x in h["wind_gusts_10m"]]
            p = [(x or 0) * stress for x in h["precipitation"]]
            gi = max(range(len(g)), key=g.__getitem__)
            rain24 = max(sum(p[j:j + 24]) for j in range(max(1, len(p) - 23)))
            out.append({"max_gust_kmh": round(g[gi]), "peak_time": h["time"][gi],
                        "max_rain_24h_mm": round(rain24), "level": _level(g[gi], rain24)})
    return out

def active_cyclones():
    """Currently active tropical cyclones near India (Bay of Bengal / Arabian Sea). None if GDACS unreachable."""
    today = datetime.date.today()
    try:
        r = requests.get(GDACS_URL, timeout=20, params={
            "eventlist": "TC", "fromDate": (today - datetime.timedelta(days=10)).isoformat(),
            "toDate": today.isoformat(), "alertlevel": "Green;Orange;Red"})
        r.raise_for_status()
        feats = r.json().get("features", [])
    except Exception as e:
        print("GDACS error:", e)
        return None
    res = []
    for f in feats:
        p, g = f.get("properties", {}), f.get("geometry") or {}
        if str(p.get("iscurrent", "")).lower() != "true" or g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        if 0 <= lat <= 30 and 45 <= lon <= 100:
            res.append({"name": p.get("name") or "Unnamed", "alertlevel": p.get("alertlevel"),
                        "lat": lat, "lon": lon})
    return res
