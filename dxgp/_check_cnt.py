# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
t = open(P, "rb").read().decode("gbk")
L = t.split("\r\n")
print("总段数 =", len(L))
print()
for i, l in enumerate(L):
    if "笔" in l and ("卖出" in l or "买入" in l) and ("%d" in l or "%s" in l):
        print("L%d: %s" % (i + 1, l.strip()[:220]))
