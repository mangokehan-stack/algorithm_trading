# -*- coding: utf-8 -*-
"""GBK 中文关键文案核查(Grep 工具对 GBK 文件中文匹配不可靠, 用 Python 解码后查)"""
import io

PATH = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
with io.open(PATH, "r", encoding="gbk", newline="") as f:
    text = f.read()
lines = text.split("\r\n")

KEYS = ["人工", "移交", "释放", "额度", "资金额度", "股票额度",
        "同时释放", "止损", "止盈", "铁律"]
for k in KEYS:
    hits = [(i + 1, l.strip()[:80]) for i, l in enumerate(lines) if k in l]
    print("== %s : %d hits" % (k, len(hits)))
    for (lno, s) in hits[:12]:
        print("   L%-6d %s" % (lno, s))
