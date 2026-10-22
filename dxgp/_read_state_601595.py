# -*- coding: utf-8 -*-
"""读状态文件里 601595 的 fee / cost_total / order_cnt / trades 明细"""
import sys, io, json

sys.stdout.reconfigure(encoding="utf-8")

P = r"C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_state_8973786.json"
OUT = r"E:\桌面\666666\dxgp\_state_601595.txt"

d = json.load(open(P, "rb"))

f = io.open(OUT, "w", encoding="utf-8")

f.write(u"顶层键: %s\n" % sorted(d.keys()))
pos = d.get("positions") or d.get("pos") or {}
f.write(u"\n=== positions 结构 ===\n")

# 兼容 dict / list 两种结构
items = []
if isinstance(pos, dict):
    for k, v in pos.items():
        items.append((k, v))
elif isinstance(pos, list):
    for v in pos:
        items.append((v.get("code", "?"), v))

for k, v in items:
    f.write(u"\n--- key=%s ---\n" % k)
    if isinstance(v, dict):
        for kk in sorted(v.keys()):
            f.write(u"  %-18s = %r\n" % (kk, v[kk]))
    else:
        f.write(u"  %r\n" % (v,))

# 手工待办
f.write(u"\n=== 其他可疑键 ===\n")
for k in d.keys():
    if any(s in k for s in ("order", "fee", "calib", "cnt")):
        f.write(u"%s = %r\n" % (k, d[k]))

f.write(u"\n=== trades: 601595 相关 ===\n")
tr = d.get("trades") or []
f.write(u"trades 总条数 = %d\n" % len(tr))
for t in tr:
    if "601595" in str(t.get("code", "")):
        f.write(u"\n")
        for kk in sorted(t.keys()):
            f.write(u"  %-14s = %r\n" % (kk, t[kk]))

f.close()
print("done -> %s" % OUT)
print("positions=%d trades=%d" % (len(items), len(tr)))
