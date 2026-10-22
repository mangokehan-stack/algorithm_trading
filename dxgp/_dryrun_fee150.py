# -*- coding: utf-8 -*-
"""V2.6.150 干跑: ① timer_poll docstring 生效  ② 过户费改动方向正确"""
import ast
import datetime
import math
import re
import sys

P = sys.argv[1] if len(sys.argv) > 1 else r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
SRC = open(P, 'rb').read().decode('gbk').replace('\r\n', '\n')
TREE = ast.parse(SRC)
LINES = SRC.split('\n')

# ---------- ① docstring ----------
tp = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'timer_poll'][0]
ds = ast.get_docstring(tp)
print('timer_poll docstring 长度 = %s' % (len(ds) if ds else 0))
print('  首句: %s' % (ds.split('\n')[0][:60] if ds else '<空>'))
assert ds and ds.startswith('策略状态(每30秒)'), 'docstring 未生效'

# ---------- ② 费用 ----------
WANT_FUNC = ['_round2', '_prod_of', 'fee_profile', '_transfer_rate_for', 'fee_buy', 'fee_sell']
WANT_VAR = ['FEE_ON', 'FEE_PROFILE', 'FEE_TRANSFER_RATE', 'FEE_COMMISSION_RATE',
            'FEE_COMMISSION_MIN', 'FEE_STAMP_RATE', 'FEE_CBOND_SELL_RATE']
ns = {'math': math, 're': re, 'datetime': datetime}
done = set()
for n in TREE.body:
    nm = None
    if isinstance(n, ast.FunctionDef):
        nm = n.name
    elif isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
        nm = n.targets[0].id
    if nm not in WANT_FUNC and nm not in WANT_VAR:
        continue
    seg = '\n'.join(LINES[n.lineno - 1:n.end_lineno])
    try:
        exec(compile(seg, '<fee>', 'exec'), ns)
        done.add(nm)
    except Exception as e:
        print('  exec 失败 %-20s %s' % (nm, e))
missing = [x for x in WANT_FUNC + WANT_VAR if x not in done]
print('费用依赖装载: %d/%d, 缺 %s' % (len(done), len(WANT_FUNC + WANT_VAR), missing))
assert not missing, missing
print('FEE_TRANSFER_RATE = %r' % ns['FEE_TRANSFER_RATE'])

fb, fs = ns['fee_buy'], ns['fee_sell']
amt = 12000.0
for code, tag in [('600519.SH', '沪市'), ('000001.SZ', '深市')]:
    b = fb(amt, code)
    s = fs(amt, code)
    print('  %s %s 金额%.0f: 买费=%.2f 卖费=%.2f 双边合计=%.2f' % (tag, code, amt, b, s, b + s))

sh_tr = fb(amt, '600519.SH') - fb(amt, '000001.SZ')
print('沪市比深市买入多算 = %.4f 元 (预期 12000*1e-05 = 0.12)' % sh_tr)
assert abs(sh_tr - amt * 1e-05) < 1e-9, '沪市过户费未按 1e-05 计入'

# 卖出侧: 沪市应比深市多 0.12
sh_ts = fs(amt, '600519.SH') - fs(amt, '000001.SZ')
print('沪市比深市卖出多算 = %.4f 元 (预期 0.12)' % sh_ts)
assert abs(sh_ts - amt * 1e-05) < 1e-9, '卖出侧过户费未计入'

# 深市口径必须与改动前一致(过户费仍是 0)
assert abs(fs(amt, '000001.SZ') - (max(amt * 0.0000841, 5.0) + amt * 0.0005)) < 0.011, '深市口径被误改'
print('深市口径未变(仍不含过户费)')

print('\n=== 全部 PASS ===')
