# -*- coding: utf-8 -*-
"""打印 13:25:00~13:29:00 完整日志（不筛关键词），确认策略期间有没有自己发过卖单"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

LOG = r"C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_run.log"
raw = open(LOG, "rb").read()
lines = []
for b in raw.split(b"\n"):
    if b.endswith(b"\r"):
        b = b[:-1]
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode("gbk", "replace")
    lines.append(s)

PAT = re.compile(r"^2026-10-21 13:2[5-9]:")
seg = [(i + 1, l) for i, l in enumerate(lines) if PAT.match(l)]
print("13:25~13:29 共 %d 行\n" % len(seg))
print("=" * 104)
for n, l in seg:
    print("L%-6d %s" % (n, l))
print("=" * 104)

# 全日志里搜策略自己发卖单的特征
print("\n【全日志】策略发卖单相关特征行（今天）：")
for i, l in enumerate(lines):
    if not l.startswith("2026-10-21"):
        continue
    if ("passorder" in l.lower() or "下单" in l or "委托" in l) and ("卖" in l or "SELL" in l or "24" in l):
        print("L%-6d %s" % (i + 1, l[:200]))
