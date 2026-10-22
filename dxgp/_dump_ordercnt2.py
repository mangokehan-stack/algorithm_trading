# -*- coding: utf-8 -*-
"""查 order_cnt 赋值上下文 + 成交回报 order_id 取值 + fee_buy 的 n_order 实现"""
import sys, io

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
L = open(P, "rb").read().decode("gbk").split("\r\n")
OUT = r"E:\桌面\666666\dxgp\_code_ordercnt2.txt"
f = io.open(OUT, "w", encoding="utf-8")


def dump(tag, lo, hi):
    f.write(u"\n===== %s (L%d..L%d) =====\n" % (tag, lo, hi))
    for i in range(lo - 1, min(hi, len(L))):
        f.write(u"L%d: %s\n" % (i + 1, L[i]))


# fee_buy / fee_sell 的 n_order 用法
for i, l in enumerate(L):
    if l.startswith("def fee_buy"):
        dump("def fee_buy", i + 1, i + 24)
        break
for i, l in enumerate(L):
    if l.startswith("def fee_sell"):
        dump("def fee_sell", i + 1, i + 24)
        break

# order_cnt 赋值处
dump("order_cnt 赋值上下文", 11315, 11375)

f.close()
print("done -> %s" % OUT)
