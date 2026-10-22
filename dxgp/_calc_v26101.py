# -*- coding: utf-8 -*-
"""V2.6.101 ① 阈值演算: 用母版真实参数算几个场景, 确认"不误伤 + 该拦的拦住"
   EXPAND_SELL_RATIO=2.00, SELL_TOL=0.95, EARLY_SELL_VOL_MULT=1.5, VOL_PROJ_MODE='linear'
   加仓侧: _il_line = 2.00*0.95*(1.5 if elap<60 else 1.0); 触发线 = _il_line*0.85
"""
import math

R = 2.00
TOL = 0.95
EARLY_MULT = 1.5
EARLY_END = 60
BLOCK = 30
BASE = 1000000.0   # 基准量 100 万股

def k_of(elap):
    if elap <= 0 or elap >= 240:
        return 1.0
    return elap / 240.0     # VOL_PROJ_MODE='linear'

cases = [
    ('缩量低吸中(典型)',   10,   40000.0),
    ('温和放量',           35,  250000.0),
    ('早盘急速放量',       35,  400000.0),
    ('盘中量能 1.6 倍',    90,  600000.0),
    ('盘中量能 1.65 倍',   90,  620000.0),
    ('已到止盈线 1.9 倍', 150, 1180000.0),
    ('午后继续放大',      150, 1500000.0),
    ('尾盘天量',          210, 2100000.0),
]

print('%-18s %6s %12s %7s %10s %8s %8s  %s' % ('场景', '开盘分', '累计量(万)', 'k', '预估全日量', '倍数', '触发线', '加仓侧结论'))
for name, elap, vol in cases:
    k = k_of(elap)
    est = vol * 1.0 / k
    line = R * TOL * (EARLY_MULT if elap < EARLY_END else 1.0)
    trig = line * 0.85
    ratio = est / BASE
    if elap < BLOCK:
        concl = '照常加仓(开盘<30分, 卖出侧本身不触发)'
    elif ratio >= trig:
        concl = '暂缓: 离卖出太近'
    else:
        concl = '照常加仓(距触发线还差 %.0f%%)' % ((1 - ratio / trig) * 100)
    print('%-18s %6d %12.1f %7.3f %10.0f %8.2f %8.3f  %s'
          % (name, elap, vol / 10000.0, k, est / 10000.0, ratio, trig, concl))

print()
print('放量止盈硬线 = 2.00 x 0.95 = %.2f 倍; 早盘(<60分) = %.2f 倍' % (R * TOL, R * TOL * EARLY_MULT))
print('加仓暂缓线   = 硬线 x 0.85 = %.3f 倍; 早盘 = %.4f 倍' % (R * TOL * 0.85, R * TOL * EARLY_MULT * 0.85))
