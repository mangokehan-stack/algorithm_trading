# -*- coding: utf-8 -*-
"""把当前 GBK 交付件重新转成 UTF-8 阅读镜像，并抽取关键行（只读，不改交付件）。"""
import io
import os
import re

BASE = r"E:/桌面/666666/nbbank"
SRC = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
OUTDIR = os.path.join(BASE, "audit_v1280")
if not os.path.isdir(OUTDIR):
    os.makedirs(OUTDIR)
DST = os.path.join(OUTDIR, "main_utf8.py")

blob = open(SRC, "rb").read()
txt = blob.decode("gbk")
io.open(DST, "w", encoding="utf-8", newline="").write(txt)
lines = txt.split("\n")
print("SRC bytes=%d  lines=%d  ->  mirror=%s" % (len(blob), len(lines), DST))
print()

PATS = [
    r'STRATEGY_VERSION\s*=',
    r'STRATEGY_BUILD\s*=',
    r'_MODE_RECHECK_LAST',
    r'def _mode_pending_recheck',
    r'单实例|实例锁|_INSTANCE|instance',
    r'节假日|holiday|trade_dates|交易日表',
    r'"manual_takeover"',
    r'^SYMBOLS',
    r'def _is_strategy_stock',
    r'block_euphoric_only',
    r'def _r1_net_profit_gate',
    r'def manual_sell',
    r'^def handlebar|^def init|^def stop',
]
for p in PATS:
    print("### /%s/" % p)
    n = 0
    for i, ln in enumerate(lines, 1):
        if re.search(p, ln):
            print("  %6d| %s" % (i, ln.rstrip()[:150]))
            n += 1
            if n >= 14:
                print("  ... (截断)")
                break
    print()