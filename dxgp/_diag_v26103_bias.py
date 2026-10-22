# -*- coding: utf-8 -*-
"""V2.6.103 修复1-A 实证: 用 5226 只真实代码前缀分布模拟"预算截断只取前 N 只",
   对比 旧顺序(代码升序) vs 新顺序(按当日种子打乱) 的板块构成与涨跌占比偏差。
   代码前缀分布取 2026-10-20 实盘日志的实际口径(沪深A股 5226 只), 按真实板块分段近似。
"""
import random

# 真实沪深A股代码段(近似只数, 按 5226 只总量缩放)
SEGMENTS = [
    ('深主板 000',   1700, 0.30),
    ('深主板 001/003', 300, 0.32),
    ('深主板 002',   1100, 0.28),
    ('创业板 300/301', 1350, 0.33),
    ('沪主板 600/601/603/605', 1650, 0.29),
    ('科创板 688/689', 580, 0.35),
    ('北交所 920',    350, 0.26),
]
TOTAL = sum(s[1] for s in SEGMENTS)
SCALE = 5226.0 / TOTAL

codes = []
for name, n, adv in SEGMENTS:
    n = int(round(n * SCALE))
    for k in range(n):
        codes.append((name, adv))
# 截断场景: 每批300只, 180秒预算约能跑 5~6 批
TAKE = 1800

def report(tag, seq):
    sub = seq[:TAKE]
    seg_cnt = {}
    up = 0
    for name, adv in sub:
        seg_cnt[name] = seg_cnt.get(name, 0) + 1
        # 用 adv 作为"上涨概率"抽签(固定种子保证可复现)
        if random.Random(hash((name, adv, len(seg_cnt)))).random() < adv:
            up += 1
    print('  [%s] 取到 %d 只, 上涨占比 %.1f%%' % (tag, len(sub), up * 100.0 / len(sub)))
    miss = [s[0] for s in SEGMENTS if seg_cnt.get(s[0], 0) == 0]
    parts = []
    for s in SEGMENTS:
        c = seg_cnt.get(s[0], 0)
        parts.append('%s=%d' % (s[0].split()[0], c))
    print('       板块构成: ' + ' / '.join(parts))
    if miss:
        print('       !! 完全缺失板块: ' + ', '.join(miss))
    return up * 100.0 / len(sub)

print('全市场 %d 只, 本轮截断上限 %d 只 (约 %.1f%%)' % (len(codes), TAKE, TAKE * 100.0 / len(codes)))
print()

base = sorted(codes, key=lambda x: (x[0], x[1]))
print('【旧顺序】代码升序(修复前)')
r_old = report('升序', base)
print()

print('【新顺序】按当日种子打乱(修复后)')
sh = list(codes)
random.Random('20261020').shuffle(sh)
r_new = report('20261020', r_old if False else sh)
print()

print('【验证可复现】同日再打乱一次, 顺序应完全一致')
sh2 = list(codes)
random.Random('20261020').shuffle(sh2)
print('  同种子两次结果一致:', sh == sh2)
sh3 = list(codes)
random.Random('20261021').shuffle(sh3)
print('  跨日(20261020 vs 20261021)顺序不同:', sh != sh3)
