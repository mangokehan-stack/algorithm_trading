# -*- coding: utf-8 -*-
"""干跑：验证 buy_stock 预填 fee 与 deal_callback 累加是否叠加
全程使用真实模块函数，不注入任何桩。
"""
import sys, io, types

sys.path.insert(0, r'E:\桌面\666666\dxgp')
src = io.open(r'E:\桌面\666666\dxgp\_a157_u8.py', encoding='utf-8', newline='').read().replace('\r\n', '\n')
M = types.ModuleType('strat')
exec(compile(src, 'strat', 'exec'), M.__dict__)

M.G.today = '20261021'
M.G.state = {'hold': {}, 'order_fee_acc': {}}

print('=' * 74)
print('场景：601595 上海电影 一张委托 900 股 @28.02，柜台拆成 100+100+700 三笔成交')
print('=' * 74)

px, vol = 28.02, 900
_amt_total = round(px * vol, 2)
print('委托金额 = %.2f 元' % _amt_total)

# ---- 1) buy_stock 发单前的预填（L9465 / L9469 原样）----
_init_fee = M.fee_buy(px * vol, '601595.SH')
h = {'fee': _init_fee, 'cost_total': M._round2(px * vol + _init_fee), 'fill_sum': 0.0, 'fill_vol': 0}
print('\n[1] buy_stock 预填:  h["fee"] = %.2f   cost_total = %.2f' % (h['fee'], h['cost_total']))

# ---- 2) 三笔成交回报，按 deal_callback L11380 的做法累加 ----
print('\n[2] 成交回报逐笔（每笔都走 fee_buy(order_id=...) 归并）')
for i, v in enumerate([100, 100, 700], 1):
    amt = M._round2(px * v)
    fee = M.fee_buy(amt, '601595.SH', order_id='OID-601595-1')
    h['fill_sum'] += px * v
    h['fill_vol'] += v
    h['fee'] = M._round2(M._f(h.get('fee', 0.0)) + fee)          # ← L11380 原样
    h['cost_total'] = M._round2(h['fill_sum'] + h['fee'])        # ← L11382 原样
    print('   第%d笔 %3d股 金额%9.2f 本笔费用=%.2f | 累计 h["fee"]=%.2f  cost_total=%.2f'
          % (i, v, amt, fee, h['fee'], h['cost_total']))

# ---- 3) 正确答案：一张委托的真实费用 ----
_true_fee = M.fee_buy(_amt_total, '601595.SH')
print('\n[3] 正解: 一张委托 900 股，券商只收 佣金5.00 + 过户%.2f = %.2f 元'
      % (_amt_total * 0.00001, _true_fee))
print('    实际记录 h["fee"] = %.2f  →  虚高 %.2f 元（%.0f%%）'
      % (h['fee'], h['fee'] - _true_fee, (h['fee'] / _true_fee - 1) * 100))
print('    实际 cost_total = %.2f，真实应为 %.2f，虚高 %.2f 元'
      % (h['cost_total'], _amt_total + _true_fee, h['cost_total'] - (_amt_total + _true_fee)))

print()
print('=' * 74)
print('V2.6.157 的新判据会不会把这个虚高值"修回去"？')
print('=' * 74)
_fs = h['fill_sum']
_fe_old = h['fee']
_fe_est = M._round2(_fs * 0.0015)
_est_tol = max(1.0, _fe_est * 0.02)
print('  fill_sum=%.2f  h["fee"]=%.2f' % (_fs, _fe_old))
print('  粗估形态应为 _fe_est=%.2f  容差=%.2f' % (_fe_est, _est_tol))
print('  |%.2f - %.2f| = %.2f  >  %.2f ?  %s' % (_fe_old, _fe_est, abs(_fe_old - _fe_est), _est_tol,
                                                 '是 → 跳过不修' if abs(_fe_old - _fe_est) > _est_tol else '否 → 会重算'))
if abs(_fe_old - _fe_est) > _est_tol:
    print('  结论：V2.6.157 判定"非0.15%%粗估形态"，原样保留 %.2f（虚高被永久固化）' % _fe_old)
else:
    print('  结论：会被重算为 %.2f' % M.fee_buy(_fs, '601595.SH', n_order=1))

print()
print('=' * 74)
print('小仓位放大效应：一手 3000 元的票')
print('=' * 74)
for amt in (3000.0, 6000.0, 12000.0):
    f1 = M.fee_buy(amt, '002142.SZ')
    v = int(amt / 10.0)
    print('  金额%8.2f元(%4d股@10元): 真实费%.2f → 若按叠加口径 %.2f，成本虚高 %.2f 元 = 每股 %.4f 元 = %.2f%%'
          % (amt, v, f1, f1 * 2, f1, f1 / v, f1 / amt * 100))
