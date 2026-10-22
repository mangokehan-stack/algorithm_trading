# -*- coding: utf-8 -*-
"""只抽 2026-10-21 13:40~13:56 与买入相关的行, 结果写 UTF-8 文件"""
import sys, os, re
sys.stdout.reconfigure(encoding="utf-8")

LOG = r"C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_run.log"
OUT = r"E:\桌面\666666\dxgp\_buy_601595.txt"
raw = open(LOG, "rb").read()
lines = raw.split(b"\n")

def dec(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("gbk", "replace")

DAY = "2026-10-21"
KEYS = ("601595", "买入", "成交", "分批", "委托", "passorder", "订单", "额度", "闸门",
        "拦截", "手工", "回报", "闸", "开新仓", "追高", "缩量")
res = []
for b in lines:
    s = dec(b).rstrip("\r")
    st = s.strip()
    if not st.startswith(DAY):
        continue
    hm = st[11:16]
    if not ("13:38" <= hm <= "13:57"):
        continue
    if any(k in s for k in KEYS):
        res.append(s)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("命中 %d 行 (2026-10-21 13:38~13:57)\n" % len(res))
    f.write("=" * 100 + "\n")
    for s in res:
        f.write(s + "\n")
print("written", OUT, "lines =", len(res))
