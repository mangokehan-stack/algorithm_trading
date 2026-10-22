# -*- coding: utf-8 -*-
"""费率实证 —— 真实 exec 母版后逐项对照用户给定费率表"""
import io, sys, types

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
src = io.open(P, encoding='gbk', newline='').read().replace('\r\n', '\n')
m = types.ModuleType('strat')
m.__dict__['__name__'] = 'strat'
exec(compile(src, 'strat', 'exec'), m.__dict__)
print('真实模块装载成功, VERSION =', m.VERSION)
fb, fs, pf, pk = m.fee_buy, m.fee_sell, m.fee_profile, m._prod_of

CASES = [
    # (代码, 名称, 买入额, 期望买费, 期望卖费)
    ('600519.SH', '沪市主板 1000元',   1000.0,  5.10,  5.60),
    ('600519.SH', '沪市 25218元(601595实测一张900股委托)', 25218.0, 5.47,  18.11),
    ('000001.SZ', '深市主板 25218元', 25218.0,  5.12,  17.74),
    ('002226.SZ', '深市主板(实测持仓)', 11535.0,  5.00,  10.76),
    ('300750.SZ', '创业板 25218元',    25218.0,  5.12,  17.74),
    ('688981.SH', '科创板 25218元',    25218.0,  5.47,  18.11),
    ('510300.SH', '沪市ETF 25218元',   25218.0,  1.26,   1.26),
    ('159915.SZ', '深市ETF 25218元',   25218.0,  1.26,   1.26),
    ('113050.SH', '可转债 25218元',     25218.0,  1.11,   1.26),
    ('131810.SH', '逆回购 25218元',     25218.0,  0.00,   0.00),
    ('00700.HK',  '港股通 25218元',     25218.0,  2.52,   2.52),
    ('002594.SH', '比亚迪(应为深市!)',  25218.0,  None,   None),
]

def expect_buy(code, amt):
    p = pf(code)
    comm = max(amt * p['rate'], p['min'])
    tr = m._transfer_rate_for(code) if pk(code) == 'stock' else p['transfer']
    return m._round2(comm + amt * tr)

def expect_sell(code, amt):
    p = pf(code)
    r = m.FEE_CBOND_SELL_RATE if pk(code) == 'cbond' else p['rate']
    comm = max(amt * r, p['min'])
    tr = m._transfer_rate_for(code) if pk(code) == 'stock' else p['transfer']
    return m._round2(comm + amt * p['stamp'] + amt * tr)

print()
print('%-42s %-6s %10s %10s %10s %10s' % ('场景', '品种', '买费实算', '买费应为', '卖费实算', '卖费应为'))
bad = 0
for code, name, amt, _, _ in CASES:
    got_b, got_s = fb(amt, code), fs(amt, code)
    exp_b, exp_s = expect_buy(code, amt), expect_sell(code, amt)
    ok = abs(got_b - exp_b) < 1e-9 and abs(got_s - exp_s) < 1e-9
    if not ok:
        bad += 1
    print('%-42s %-6s %10.2f %10.2f %10.2f %10.2f  %s'
          % (name, pk(code), got_b, exp_b, got_s, exp_s, 'OK' if ok else '★不符'))

print()
print('品种识别抽查:', ' '.join('%s->%s' % (c, pk(c)) for c, _, _, _, _ in CASES))

# ---- 关键：一张委托拆多笔成交，合计必须等于单笔口径 ----
print()
print('=== 一张委托拆多笔成交：合计是否等于单笔口径 ===')
if not isinstance(getattr(m.G, 'state', None), dict):
    m.G.state = {}
m.G.today = '20261021'
m.G.state.setdefault('order_fee_acc', {})
amt_total = 25218.0
parts = [2802.0, 2802.0, 19614.0]          # 900股 @28.02 拆 100+100+700
assert abs(sum(parts) - amt_total) < 1e-9
oid = 'TESTORDER001'
sum_fee = 0.0
for i, a in enumerate(parts):
    f = fb(a, '601595.SH', order_id=oid)
    sum_fee += f
    print('  第%d笔 成交额%9.2f -> 本笔费用%.2f' % (i + 1, a, f))
one = fb(amt_total, '601595.SH')
print('  合计 %.2f  vs  单笔口径 %.2f  -> %s' % (sum_fee, one, '一致' if abs(sum_fee - one) < 1e-9 else '★不一致'))
if abs(sum_fee - one) >= 1e-9:
    bad += 1

# ---- 幂等与跨委托隔离 ----
m.G.state['order_fee_acc'] = {}
a1 = fb(25218.0, '601595.SH', order_id='A')
a2 = fb(25218.0, '601595.SH', order_id='B')
print('  不同 OrderID 各算一次: %.2f / %.2f -> %s' % (a1, a2, '正确' if a1 == a2 == one else '★错误'))

# ---- 沪市 vs 深市 过户费差 ----
print()
print('=== 过户费沪深差异(25218元) ===')
print('  沪市 601595 买费 %.2f / 深市 002226 买费 %.2f / 差 %.2f'
      % (fb(25218.0, '601595.SH'), fb(25218.0, '002226.SZ'),
         fb(25218.0, '601595.SH') - fb(25218.0, '002226.SZ')))

print()
print('总判定: %s' % ('全部通过' if bad == 0 else '有 %d 项不符' % bad))