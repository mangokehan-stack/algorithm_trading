# -*- coding: utf-8 -*-
"""抽出 2026-10-21 13:55:30 ~ 14:24:00 之间与 601595 买入/费用相关的日志行"""
import sys, io, re

sys.stdout.reconfigure(encoding="utf-8")

LOG = r"C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_run.log"
OUT = r"E:\桌面\666666\dxgp\_buy_601595b.txt"

raw = open(LOG, "rb").read()

# 按行判编码: 前段 GBK, 后段 UTF-8
lines = []
for b in raw.split(b"\n"):
    if not b.strip():
        continue
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode("gbk", "replace")
    lines.append(s.rstrip("\r"))

# 只保留 2026-10-21 当天
day = [l for l in lines if "2026-10-21" in l]

# 时段切片: 取 13:55 ~ 14:24 的
def in_win(l):
    m = re.search(r"2026-10-21 (\d{2}):(\d{2}):(\d{2})", l)
    if not m:
        return False
    t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return 13 * 3600 + 55 * 60 <= t <= 14 * 3600 + 24 * 60

win = [l for l in day if in_win(l)]

KEYS = [
    "601595", "委托", "成交回报", "本笔费用", "order", "OrderID", "委托号",
    "累计费用", "盈亏账本", "费用口径", "加仓", "分批", "买入", "卖出",
    "实发单", "费率", "fee", "净利", "解套",
]
hits = [l for l in win if any(k in l for k in KEYS)]

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(u"当天总行数=%d  窗口内=%d  命中=%d\n" % (len(day), len(win), len(hits)))
    f.write(u"=" * 100 + u"\n")
    for l in hits:
        f.write(l + u"\n")

print("done: %s" % OUT)
print("day=%d win=%d hits=%d" % (len(day), len(win), len(hits)))
