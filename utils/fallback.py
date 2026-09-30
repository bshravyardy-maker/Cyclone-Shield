"""Fallbacks built from the ACTUAL exposure data (never hardcoded to one state)."""

def build_fallback_advisory(summary: dict) -> dict:
    ranked = sorted(summary.items(), key=lambda kv: -kv[1].get("total_exposed", 0))
    top = ranked[0][0] if ranked else "coastal districts"
    if not ranked or ranked[0][1].get("total_exposed", 0) == 0:
        return {"risk_ranking": [{"district": d, "risk_score": 1, "priority": "Low", "reason": "No critical assets exposed"} for d, _ in ranked],
                "authorities": {"municipal": "No significant cyclone hazard forecast. Continue routine monitoring of IMD bulletins.",
                                "power": "No pre-emptive action needed. Keep standard readiness.",
                                "health": "No special action needed. Maintain normal stock levels."},
                "cap_alert": {"event": "No significant hazard forecast", "severity": "Minor", "urgency": "Future",
                              "area": "Monitored coastal districts", "instruction": "No action needed. Follow IMD updates."}}
    def prio(n): return "Critical" if n > 3 else "High" if n > 1 else "Moderate" if n else "Low"
    return {
        "risk_ranking": [{"district": d, "risk_score": min(10, 1 + c.get("total_exposed", 0) * 2),
                          "priority": prio(c.get("total_exposed", 0)),
                          "reason": f"{c.get('total_exposed', 0)} critical assets in projected flood zone"}
                         for d, c in ranked],
        "authorities": {
            "municipal": f"Evacuate low-lying coastal areas in {top} and open cyclone shelters now.",
            "power": f"Plan pre-emptive shutdown of exposed substations in {top}; pre-position repair crews.",
            "health": f"Move patients from exposed hospitals in {top}; pre-position generators, medicines and staff."},
        "cap_alert": {"event": "Cyclone Storm Surge Warning", "severity": "Extreme", "urgency": "Immediate",
                      "area": top, "instruction": "Move to the nearest cyclone shelter now. Stay away from the coast."},
    }

FALLBACK_PHOTO = {"classification": "Flooded road / infrastructure damage (demo fallback)", "severity": "High",
                  "confidence": 0.8, "recommended_action": "Dispatch rapid assessment team and divert traffic."}
