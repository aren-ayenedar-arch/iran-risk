# دریافت داده بازار و خبر، محاسبه احتمال و نوشتن data.json
import json, math, csv, io, os, datetime, urllib.request, urllib.parse

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode()

def stooq(sym):
    t = get("https://stooq.com/q/l/?s=%s&f=sc&h&e=csv" % urllib.parse.quote(sym))
    return float(list(csv.DictReader(io.StringIO(t)))[0]["Close"])

def gdelt_ratio():
    q = urllib.parse.quote("Iran (attack OR strike OR missile OR tanker OR Hormuz)")
    j = json.loads(get("https://api.gdeltproject.org/api/v2/doc/doc?query=%s&mode=timelinevol&timespan=30d&format=json" % q))
    v = [p["value"] for p in j["timeline"][0]["data"]]
    k = max(1, len(v) // 15)
    return (sum(v[-k:]) / k) / (sum(v) / len(v))

clamp = lambda x: max(0, min(100, x))
old = {}
if os.path.exists("data.json"):
    old = json.load(open("data.json", encoding="utf-8"))
manual = json.load(open("manual.json", encoding="utf-8"))
vals = dict(old.get("values", {}))
raw = dict(old.get("raw", {}))
status = {}

for key, fn in [("brent", lambda: stooq("cb.f")), ("vix", lambda: stooq("^vix")), ("news", gdelt_ratio)]:
    try:
        raw[key] = fn(); status[key] = "ok"
    except Exception as e:
        status[key] = "خطا: %s" % str(e)[:60]

if "brent" in raw: vals["brent"] = round(clamp((raw["brent"] - 60) / 60 * 100))
if "vix" in raw:   vals["vix"]   = round(clamp((raw["vix"] - 12) / 28 * 100))
if "news" in raw:  vals["inc"]   = round(clamp(50 + (raw["news"] - 1) * 50))
for k in ("hormuz", "force", "dip", "cal"):
    vals[k] = manual[k]
for k, d in (("brent", 70), ("vix", 40), ("inc", 70)):
    vals.setdefault(k, d)

W = {"brent": .8, "hormuz": .6, "force": .9, "inc": .9, "dip": .7, "cal": .5, "vix": .3}
H = [("w", -3.0, 1.0), ("m", -1.9, 1.2), ("q", -1.3, 1.4)]
S = lambda x: 1 / (1 + math.exp(-x))
z = sum(W[k] * (vals[k] - 50) / 50 for k in W)
probs, prev = {}, 0
for n, b, s in H:
    p = max(S(b + s * z), prev); prev = p
    probs[n] = {"p": p, "lo": min(S(b + s * (z - .6)), p), "hi": max(S(b + s * (z + .6)), p)}

now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
hist = old.get("history", [])
hist.append([now, probs["w"]["p"], probs["m"]["p"], probs["q"]["p"]])
json.dump({"updated": now, "values": vals, "raw": raw, "status": status, "probs": probs,
           "manual_note": manual.get("note", ""), "history": hist[-300:]},
          open("data.json", "w", encoding="utf-8"), ensure_ascii=False)
print("done", status)
