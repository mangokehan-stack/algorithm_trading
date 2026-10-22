# -*- coding: utf-8 -*-
"""读状态文件里持仓的真实字段, 并探测校准段所依赖的辅助函数复杂度"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ST = r"C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_state_8973786.json"
out = []
if os.path.exists(ST):
    d = json.load(io.open(ST, "r", encoding="utf-8"))
    hold = d.get("hold") or {}
    out.append("状态文件存在, hold 共 %d 只" % len(hold))
    for code, h in hold.items():
        out.append("  %s | fill_vol=%r fill_sum=%r fee=%r cost_total=%r order_cnt=%r buy_price=%r"
                   % (code, h.get("fill_vol"), h.get("fill_sum"), h.get("fee"),
                      h.get("cost_total"), h.get("order_cnt"), h.get("buy_price")))
    # trades 里该票的买入记录
    for code in hold:
        tr = [x for x in (d.get("trades") or [])
              if x.get("code") == code and str(x.get("dir", "")).startswith("买入")]
        out.append("  %s 买入成交记录 %d 条:" % (code, len(tr)))
        for x in tr:
            out.append("     vol=%r price=%r amount=%r fee=%r time=%r order_id=%r"
                       % (x.get("vol"), x.get("price"), x.get("amount"), x.get("fee"),
                          x.get("time") or x.get("ts"), x.get("order_id")))
else:
    out.append("状态文件不存在: %s" % ST)

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
L = open(P, "rb").read().decode("gbk").split("\r\n")
for fn in ("def is_own_position", "def pos_vol", "def _f(", "def _round2"):
    for i, l in enumerate(L):
        if l.startswith(fn):
            out.append("")
            out.append("=== %s  L%d ===" % (fn, i + 1))
            for j in range(i, min(i + 14, len(L))):
                out.append("L%d: %s" % (j + 1, L[j]))
                if L[j].strip().startswith("return") or (L[j].strip() and not L[j].startswith(" ") and j > i):
                    break
            break

io.open(r"E:\桌面\666666\dxgp\_state_157.txt", "w", encoding="utf-8").write("\n".join(out))
print("written")
