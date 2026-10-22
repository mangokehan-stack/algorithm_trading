# -*- coding: utf-8 -*-
"""扫描所有持仓删除/弹出点(del hold[ / del G.state['hold'] / hold'].pop)"""
import io

with io.open(r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py", "r", encoding="gbk", newline="") as f:
    lines = f.read().split("\r\n")
for i, l in enumerate(lines):
    s = l.strip()
    if ("del hold[" in s or "del G.state['hold']" in s
            or "hold'].pop(" in s or 'hold"].pop(' in s
            or "G.state['hold'].pop(" in s):
        print("L%-6d %s" % (i + 1, s[:100]))
