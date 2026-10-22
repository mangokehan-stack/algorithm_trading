# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
t = open(P, "rb").read().decode("gbk")

anchors = [
    "def fee_buy(amount, code=''):",
    "    return _round2(max(amount * _p['rate'], _p['min']) + amount * _tr)",
    "def fee_sell(amount, code=''):",
    "    return _round2(max(amount * _r, _p['min']) + amount * _p['stamp'] + amount * _tr)",
    "def ledger_buy(s, h, price, vol, reason, npos_before, was_new=True, pos_before=0):",
    "    fee = fee_buy(amt, s)",
    "def ledger_sell(s, h, price, vol, reason, npos_before):",
    "    fee = fee_sell(amt, s)",
    "            fee = fee_buy(amt, code)",
    "            _fe_new = fee_buy(_round2(_fs), _code)",
    "        if side == 'BUY':",
    "            alert_open(ledger_buy(code, h, price, volume,",
    "            rec = ledger_sell(code, info, price, volume,",
]
for a in anchors:
    print("%-4d  %s" % (t.count(a), a[:95]))

print()
print("=== ledger_buy 全部调用点 ===")
import re
for m in re.finditer(r"ledger_buy\(", t):
    ln = t[:m.start()].count("\r\n") + 1
    seg = t[m.start():m.start() + 120].replace("\r\n", "\\n")
    print("L%d: %s" % (ln, seg[:110]))

print()
print("=== ledger_sell 全部调用点 ===")
for m in re.finditer(r"ledger_sell\(", t):
    ln = t[:m.start()].count("\r\n") + 1
    seg = t[m.start():m.start() + 120].replace("\r\n", "\\n")
    print("L%d: %s" % (ln, seg[:110]))
