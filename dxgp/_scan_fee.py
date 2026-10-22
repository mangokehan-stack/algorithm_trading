# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
L = open(P, "rb").read().decode("gbk").split("\r\n")

print("=== 含 fee_buy / fee_sell 的行 ===")
for i, l in enumerate(L):
    if "fee_buy(" in l or "fee_sell(" in l or "def fee_buy" in l or "def fee_sell" in l:
        print("L%d: %s" % (i + 1, l.strip()[:190]))

print()
print("=== 含 ledger_buy / ledger_sell 的行 ===")
for i, l in enumerate(L):
    if "ledger_buy(" in l or "ledger_sell(" in l:
        print("L%d: %s" % (i + 1, l.strip()[:190]))
