# -*- coding: utf-8 -*-
import io, json, re, os

P = u"C:/广发证券QMT量化交易系统 - 交易端/bin.x64/"
f = P + u"zt_shrink_risk_exclude_8973786.json"
print("EXIST", os.path.exists(f))
d = json.loads(io.open(f, encoding="utf-8").read())
print("keys:", list(d.keys()))
for k in d:
    if k != "stocks":
        print(" ", k, "=", str(d[k])[:400])
print("stock count", len(d.get("stocks") or {}))
tg = {}
for v in (d.get("stocks") or {}).values():
    for t in (v.get("tags") or []):
        tg[t] = tg.get(t, 0) + 1
print("tags", tg)

t = io.open(P + u"download_risk_exclude.py", encoding="utf-8").read()
L = t.split("\n")
print("--- 参数/常量 ---")
for i, l in enumerate(L):
    if re.match(r"^(WIN|LIFT|DEC|LOSS|ANN|ST|MAX|HIST|COVER|RISK)[A-Z_]*\s*=", l) or "add_argument" in l:
        print("TOOL", i + 1, l.strip()[:150])
