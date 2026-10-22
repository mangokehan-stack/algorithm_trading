# -*- coding: utf-8 -*-
"""V2.6.161 干跑探针: 试探用最小 G 状态把 buy_stock 推到下单段需要什么。"""
import sys, os, io, types, tempfile, traceback

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
RAW = open(P, 'rb').read().decode('gbk')
SRC = RAW.replace('\r\n', '\n')

TMP = tempfile.mkdtemp(prefix='probe161_')
os.chdir(TMP)
print('临时目录 =', TMP)

M = types.ModuleType('strat')
exec(compile(SRC, '<strat>', 'exec'), M.__dict__)
print('装载 OK, VERSION =', M.VERSION)
print('DRY_RUN =', M.DRY_RUN, ' SIM_FILL_PROB =', M.SIM_FILL_PROB)
print('G 类型 =', type(M.G).__name__)
print('G.ready =', getattr(M.G, 'ready', '<none>'), ' G.C =', getattr(M.G, 'C', '<none>'))
print('G.state keys =', sorted(M.G.state.keys()) if isinstance(M.G.state, dict) else type(M.G.state))
print('G.candidates =', M.G.candidates)
print('G.today =', M.G.today)
print('RISK_MIN_PRICE =', M.RISK_MIN_PRICE, ' MAX_POS_VALUE_ABS =', M.MAX_POS_VALUE_ABS)
print('TARGET_BUY_AMOUNT =', M.TARGET_BUY_AMOUNT, ' FIXED_BUY_VOL =', M.FIXED_BUY_VOL)
print('STRATEGY_CASH_CAP =', M.STRATEGY_CASH_CAP, ' MAX_TOTAL_VALUE_PCT =', M.MAX_TOTAL_VALUE_PCT)
print('LOT_SIZE =', M.LOT_SIZE)
print('RISK_EXCLUDE_ON =', M.RISK_EXCLUDE_ON)
print('_slippage_for(10.0) =', M._slippage_for(10.0))
print('abs_cap_left(10.03) =', M.abs_cap_left(10.03))
print('used_capital() =', M.used_capital())
print('size_equity() =', M.size_equity())

# 捕获日志
LOGS = []
_orig_log = M.log
def cap_log(*a, **k):
    try:
        LOGS.append(str(a[0]) if a else '')
    except Exception:
        pass
M.log = cap_log

# 最小状态
M.DRY_RUN = True
M.SIM_FILL_PROB = 1.0
M.G.ready = True
M.G.C = object()
M.G.accid = ''
M.G.state_broken = False
M.G.today = '20261022'
M.G.candidates = [{'stock': '601595.SH', 'name': '上海电影', 't0': 'T0',
                   'base_vol': 100000, 'zt_close': 11.0, 'offset': 1}]
M.G.state.setdefault('hold', {})
M.G.state.setdefault('trades', [])
M.G.prev_close = {'601595.SH': 10.00}

c = {'stock': '601595.SH', 'name': '上海电影', 't0': 'T0', 'base_vol': 100000,
     'zt_close': 11.0, 'offset': 1}
try:
    r = M.buy_stock(c, 10.00, 50000.0, 0.5, 10_000_000.0, want_vol=6000)
    print('buy_stock 返回 =', r)
except Exception:
    traceback.print_exc()
print('--- 捕获日志 ---')
for l in LOGS:
    print('  LOG:', l[:160])
