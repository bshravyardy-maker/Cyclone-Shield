import os, json, hashlib
from .fallback import build_fallback_advisory, FALLBACK_PHOTO

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_client = None
_cache: dict = {}

# Cloud TTS locale codes. Odia ("or") is intentionally absent -> UI shows text only.
TTS_LANG = {"bn": "bn-IN", "te": "te-IN", "ta": "ta-IN", "hi": "hi-IN", "gu": "gu-IN", "mr": "mr-IN", "en": "en-IN"}

def _gemini():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            return None
        from google import genai
        _client = genai.Client(api_key=key)
    return _client

def _json_call(contents):
    from google.genai import types
    r = _gemini().models.generate_content(
        model=MODEL, contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
    return json.loads(r.text)

def generate_risk_advisory(summary: dict, exposed_assets: list, context: str = "") -> tuple[dict, str]:
    key = hashlib.md5(json.dumps([summary, exposed_assets, context], sort_keys=True).encode()).hexdigest()
    if key in _cache:
        return _cache[key], "gemini-cached"
    if _gemini() is None:
        return build_fallback_advisory(summary), "fallback (no GEMINI_API_KEY)"
    prompt = f"""You are a disaster-management analyst supporting India's State Disaster Management Authorities.
Given projected cyclone flood-zone exposure per district, produce an anticipatory (pre-landfall) advisory.
Return ONLY JSON with this exact shape:
{{"risk_ranking":[{{"district":str,"risk_score":int 1-10,"priority":"Critical|High|Moderate|Low","reason":str}}],
 "authorities":{{"municipal":str,"power":str,"health":str}},
 "cap_alert":{{"event":str,"severity":"Extreme|Severe|Moderate|Minor","urgency":"Immediate|Expected|Future","area":str,"instruction":str}}}}
Rules: rank every district; each authority advice max 2 short sentences, specific to named assets/districts;
instruction must be short, simple, and suitable for an SMS to citizens.
If no assets are exposed, say so plainly (severity Minor) and do NOT invent a threat.
Situation: {context or 'Historical cyclone replay (illustrative)'}
Exposure counts per district: {json.dumps(summary)}
Exposed assets: {json.dumps(exposed_assets)}"""
    try:
        out = _json_call(prompt)
        assert "authorities" in out and "cap_alert" in out and "risk_ranking" in out
        _cache[key] = out
        return out, f"gemini ({MODEL})"
    except Exception as e:
        print("Gemini advisory error:", e)
        return build_fallback_advisory(summary), "fallback (Gemini error)"

def translate_batch(texts: list[str], lang: str) -> tuple[list[str], str]:
    """Cloud Translation API first, Gemini as backup, else original text."""
    if lang == "en" or not texts:
        return texts, "none"
    try:
        from google.cloud import translate_v2 as translate
        res = translate.Client().translate(texts, target_language=lang, format_="text")
        return [r["translatedText"] for r in res], "Cloud Translation API"
    except Exception as e:
        print("Translation API error:", e)
    try:
        if _gemini() is not None:
            out = _json_call(f"Translate each string to the language with ISO code '{lang}'. Keep meaning precise "
                             f"(emergency instructions). Return ONLY a JSON array of strings, same order: {json.dumps(texts)}")
            if isinstance(out, list) and len(out) == len(texts):
                return [str(x) for x in out], f"Gemini ({MODEL})"
    except Exception as e:
        print("Gemini translate error:", e)
    return texts, "unavailable"

def synthesize_speech(text: str, lang: str):
    code = TTS_LANG.get(lang)
    if not code:
        return None
    try:
        from google.cloud import texttospeech
        client = texttospeech.TextToSpeechClient()
        voice = texttospeech.VoiceSelectionParams(language_code=code, ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
        cfg = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        return client.synthesize_speech(input=texttospeech.SynthesisInput(text=text[:4500]),
                                        voice=voice, audio_config=cfg).audio_content
    except Exception as e:
        print("TTS error:", e)
        return None

def analyze_photo(image_bytes: bytes, mime: str) -> tuple[dict, str]:
    if _gemini() is None:
        return FALLBACK_PHOTO, "fallback (no GEMINI_API_KEY)"
    try:
        from google.genai import types
        out = _json_call([
            types.Part.from_bytes(data=image_bytes, mime_type=mime or "image/jpeg"),
            "You assess post-cyclone field photos for Indian disaster authorities. Return ONLY JSON: "
            '{"classification": str (e.g. flooded road, damaged shelter, downed power line, uprooted trees, safe), '
            '"severity": "Low|Moderate|High", "confidence": float 0-1, "recommended_action": str (one sentence)}'])
        return out, f"gemini ({MODEL})"
    except Exception as e:
        print("Gemini vision error:", e)
        return FALLBACK_PHOTO, "fallback (Gemini error)"
