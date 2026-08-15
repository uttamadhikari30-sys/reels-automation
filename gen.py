#!/usr/bin/env python3
"""Generate a fresh, never-repeating Hindi reel script via the Anthropic API.
Uses only the stdlib (urllib) so no SDK install is needed on the runner.
State (recent topics per brand) lives in state/used_<brand>.json and is committed
back by the workflow, so content never repeats across days."""
import json, os, urllib.request, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent
STATE = ROOT / "state"
API_URL = "https://api.anthropic.com/v1/messages"

def _recent(brand, category, n=30):
    f = STATE / f"used_{brand}.json"
    if not f.exists(): return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []
    same = [e["topic"] for e in data if e.get("category") == category]
    return same[-n:]

def record(brand, category, topic):
    STATE.mkdir(exist_ok=True)
    f = STATE / f"used_{brand}.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
    data.append({"date": datetime.date.today().isoformat(), "category": category, "topic": topic})
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

def _prompt(bcfg, category, presenter):
    name, tag = bcfg["name"], bcfg["tagline"]
    recent = "\n".join(f"- {t}" for t in _recent_cache) or "(अभी कुछ नहीं)"
    kind = bcfg["kind"]
    if kind == "facts":
        body = (f'{category} से जुड़े 3-4 आम-तौर पर 100% सही, verified, रोचक तथ्य दो। '
                'कोई मनगढ़ंत या शक वाली बात नहीं — सिर्फ़ पक्के तथ्य।')
    elif kind == "health":
        if presenter == "dadi":
            body = ('यह घरेलू नुस्खा है — गरम, अपनेपन वाली दादी माँ जैसी बोली ("बेटा…") में लिखो। '
                    'सिर्फ़ सुरक्षित आम घरेलू उपाय, कोई दवा/खुराक नहीं।')
        else:
            body = f'{category} पर एक practical, सुरक्षित सेहत टिप सरल हिंदी में दो।'
    else:
        body = f'{category} पर एक दमदार, दिल छू लेने वाली प्रेरणादायक बात हिंदी में लिखो।'
    items_rule = ('items: इस नुस्खे की 1-4 सामग्री के आम हिंदी नाम array में दो (जैसे शहद, हल्दी)।'
                  if presenter == "dadi" else 'items: खाली array [] दो।')
    return f"""तुम {name} के लिए Hindi reel writer हो — tagline "{tag}"।
Category: {category}

इस {category} के लिए एक बिलकुल नया, specific subtopic खुद चुनो (2-4 शब्द)। नीचे "हाल की reels" में दिए गए किसी subtopic जैसा मत चुनो — हर बार एकदम अलग विषय।

45-70 सेकंड की ORIGINAL Hindi reel लिखो।
- पहली line एक तेज़ hook (3 सेकंड में रोक ले)।
- {body}
- script में हर line नई पंक्ति पर, 4-6 छोटी lines।
- आख़िरी line में cta_line, और cta_word "{bcfg['cta_word']}"।
- {items_rule}

हाल की reels (इनसे अलग बात कहो):
{recent}

सिर्फ़ एक JSON object लौटाओ इन keys के साथ (values हिंदी में):
topic, title, hook, script, cta_line, cta_word, items
JSON के अलावा कुछ मत लिखो।"""

_recent_cache = []

def generate(brand, bcfg, slot):
    global _recent_cache
    scfg = bcfg["slots"][slot]
    category = scfg["category"]; presenter = scfg.get("presenter")
    _recent_cache = _recent(brand, category)
    key = os.environ["ANTHROPIC_API_KEY"]
    payload = {"model": bcfg.get("model", "claude-haiku-4-5-20251001"), "max_tokens": 1500,
               "messages": [{"role": "user", "content": _prompt(bcfg, category, presenter)}]}
    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    blocks = json.loads(raw)["content"]
    text = next(b["text"] for b in blocks if b.get("type") == "text").strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    d = json.loads(text)
    for k in ("hook", "script", "cta_line"):
        if not str(d.get(k, "")).strip():
            raise ValueError(f"API reply missing '{k}'")
    d["category"] = category
    d["presenter"] = presenter
    d["voice"] = scfg.get("voice", bcfg["voice_default"])
    d.setdefault("items", [])
    d.setdefault("cta_word", bcfg["cta_word"])
    d.setdefault("topic", d.get("title", category))
    return d

if __name__ == "__main__":
    import sys
    brand = sys.argv[1]; slot = sys.argv[2]
    cfg = json.loads((ROOT / "brands.json").read_text(encoding="utf-8"))[brand]
    d = generate(brand, cfg, slot)
    print(json.dumps(d, ensure_ascii=False, indent=2))
