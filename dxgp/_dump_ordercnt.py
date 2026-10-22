# -*- coding: utf-8 -*-
"""定位 V2.6.156 新增: order_cnt 赋值、校准 n_order 取法、_order_fee_delta 空 order_id 处理"""
import sys, io

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
L = open(P, "rb").read().decode("gbk").split("\r\n")

OUT = r"E:\桌面\666666\dxgp\_code_ordercnt.txt"
f = io.open(OUT, "w", encoding="utf-8")

KEYS = ["order_cnt", "_order_fee_delta", "order_fee_acc", "n_order", "存量持仓费用口径校准"]


def dump(tag, lo, hi):
    f.write(u"\n===== %s (L%d..L%d) =====\n" % (tag, lo, hi))
    for i in range(lo - 1, min(hi, len(L))):
        f.write(u"L%d: %s\n" % (i + 1, L[i]))


hits = {}
for i, l in enumerate(L):
    for k in KEYS:
        if k in l:
            hits.setdefault(k, []).append(i + 1)

f.write(u"=== 命中位置 ===\n")
for k in KEYS:
    vs = hits.get(k, [])
    f.write(u"%-24s %2d 处  %s\n" % (k, len(vs), ",".join("L%d" % x for x in vs)))

# 输出 _order_fee_delta 定义全文
for i, l in enumerate(L):
    if l.startswith("def _order_fee_delta"):
        dump("def _order_fee_delta", i + 1, i + 40)
        break

# 输出校准段
for i, l in enumerate(L):
    if "存量持仓费用口径校准" in l and "log(" in l:
        # 往前找 60 行看实现
        dump("存量校准实现", max(1, i - 60), i + 6)
        break

f.close()
print("done -> %s" % OUT)
