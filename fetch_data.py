# دریافت داده بازار و خبر، محاسبه احتمال و نوشتن data.json
import json, math, csv, io, os, datetime, urllib.request, urllib.parse

import time

def get(url, tries=1):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
            return urllib.request.urlopen(req, timeout=30).read().decode()
        except Exception as e:
            last = e
            time.sleep(15)
    raise last

def yahoo(sym):
    j = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=5d" % urllib.parse.quote(sym)))
    return float(j["chart"]["result"][0]["meta"]["regularMarketPrice"])

def stooq(sym):
    q = urllib.parse.quote(sym)
    try:
        t = get("https://stooq.com/q/l/?s=%s&f=sd2t2ohlcv&h&e=csv" % q)
        return float(list(csv.DictReader(io.StringIO(t)))[0]["Close"])
    except Exception:
        t = get("https://stooq.com/q/d/l/?s=%s&i=d" % q)
        return float(list(csv.DictReader(io.StringIO(t)))[-1]["Close"])

def first_ok(*fns):
    err = None
    for f in fns:
        try:
            return f()
        except Exception as e:
            err = e
    raise err

def gdelt_ratio():
    q = urllib.parse.quote("Iran (attack OR strike OR missile OR tanker OR Hormuz)")
    j = json.loads(get("https://api.gdeltproject.org/api/v2/doc/doc?query=%s&mode=timelinevol&timespan=30d&format=json" % q, tries=3))
    v = [p["value"] for p in j["timeline"][0]["data"]]
    k = max(1, len(v) // 15)
    return (sum(v[-k:]) / k) / (sum(v) / len(v))

clamp = lambda x: max(0, min(100, x))
old = {}
if os.path.exists("data.json"):
    old = json.load(open("data.json", encoding="utf-8"))
manual = json.load(open("manual.json", encoding="utf-8"))
vals = {}
raw = dict(old.get("raw", {}))
status = {}

for key, fn in [("brent", lambda: first_ok(lambda: yahoo("BZ=F"), lambda: stooq("cb.f"))), ("vix", lambda: first_ok(lambda: yahoo("^VIX"), lambda: stooq("^vix"))), ("news", gdelt_ratio)]:
    try:
        raw[key] = fn(); status[key] = "ok"
    except Exception as e:
        status[key] = "خطا: %s" % str(e)[:60]

if "brent" in raw: vals["brent"] = round(clamp((raw["brent"] - 60) / 60 * 100))
if "vix" in raw:   vals["vix"]   = round(clamp((raw["vix"] - 12) / 28 * 100))
if "news" in raw:  vals["inc"]   = round(clamp(50 + (raw["news"] - 1) * 50))
for k in ("hormuz", "force", "dip", "cal"):
    vals[k] = manual[k]
for k, d in (("brent", 66), ("vix", 30), ("inc", 65)):
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
