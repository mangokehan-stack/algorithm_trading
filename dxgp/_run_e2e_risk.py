# -*- coding: utf-8 -*-
"""端到端验证：排雷清单命中 -> 选股剔除 + 发单前复核双重拦截（不买入）。"""
import io
import json
import os
import sys

src = io.open('_run_e2e.py', 'r', encoding='utf-8', newline='').read()
head = src.split("# ---------------------------------------------------------------- Day 1")[0]
g = {'__name__': '__main__'}
exec(compile(head, '_run_e2e_head.py', 'exec'), g)

ns = g['ns']
SB = g['SB']
rounds = g['rounds']
chk = g['chk']
state = g['state']

# ---- 写入排雷清单：把唯一候选 002142.SZ 标为"立案" ----
rp = ns['risk_exclude_path']()
with open(rp, 'w', encoding='utf-8') as f:
    json.dump({'schema': 1, 'asof': '20261019', 'window_days': 45,
               'stocks': {'002142.SZ': {'tags': ['ann'],
                                        'reasons': ['立案(2026-10-10 关于收到立案告知书的公告)']}}},
              f, ensure_ascii=False)
print('排雷清单已写入沙箱: %s' % os.path.basename(rp))

d1 = rounds(6, 'Day1')
st = state()
hold = st.get('hold') or {}
trades = st.get('trades') or []

chk('排雷 清单已装载', '已装载提前排雷清单1只' in d1,
    [l for l in d1.split('\n') if '排雷' in l][:3])
_rex = ns['excluded']('002142.SZ')
chk('排雷 选股层命中剔除', _rex.startswith('排雷命中'), 'excluded()=%r' % _rex)
chk('排雷 原因可读', '立案' in _rex, _rex)
chk('排雷 未产生买入记录', len(trades) == 0, 'trades=%r' % [t.get('dir') for t in trades][:4])
chk('排雷 持仓为空', '002142.SZ' not in hold, 'hold=%r' % list(hold)[:3])
chk('排雷 无 Traceback', 'Traceback' not in d1, d1[-400:] if 'Traceback' in d1 else '')
chk('排雷 无盘中轮询异常', '盘中轮询异常' not in d1, '')

print('\n' + '=' * 70)
npass, nfail = len(g['PASS']), len(g['FAIL'])
print('RESULT: %d passed, %d failed' % (npass, nfail))
print('沙箱: %s' % SB)
if g['FAIL']:
    print('FAILED:', g['FAIL'])
    sys.exit(1)
