# -*- coding: utf-8 -*-
"""V2.6.148 干跑: 从母版切出三段新代码, 用真实现跑一遍(不做副本同步)"""
import os
import sys
import textwrap
import traceback

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
L = open(P, 'rb').read().decode('gbk').split('\r\n')
ok = []


def chk(n, c, ex=''):
    ok.append((n, bool(c)))
    print('%s %s %s' % ('PASS' if c else 'FAIL', n, ex))


def cut(start, end):
    i = next(k for k, s in enumerate(L) if s.strip() == start)
    j = next(k for k in range(i, len(L)) if L[k].strip() == end)
    return textwrap.dedent('\n'.join(L[i:j + 1]))


# ============ A. 整池重解析形状守卫 ============
A = cut("if _d3 < _start:", "_p3 = _f((_row3 or {}).get('preClose'))")
A = A.split('if _c3 <= 0 or _p3 <= 0:')[0].rstrip()
A = A.replace('_row3', 'row').replace('_nbad3', 'nbad[0]').replace('_sent_wlog', 'wlog')
A = A.replace('_s3', 'sid').replace('_f(', 'fl(').replace('_d3', 'd')
A_src = ('def _t(_bars3, _start):\n'
         '    nbad = _CNT\n'
         '    out = []\n'
         '    for d, row in _bars3.items():\n'
         + '\n'.join('        ' + x if x.strip() else x for x in A.split('\n'))
         + '\n        out.append((_c3, _p3))\n'
         '    return out, nbad[0]\n')


def run_guard(rows):
    logs = []
    ns = {'fl': lambda x: (float(x) if x is not None else 0.0),
          'wlog': logs.append, 'sid': '600000.SH', '_CNT': [0]}
    exec(compile(A_src, '<guard>', 'exec'), ns)
    o, nb = ns['_t'](dict(rows), '20260101')
    return o, nb, logs


o, nb, lg = run_guard({'20261020': {'close': 10.0, 'preClose': 9.0}})
chk('A1 dict 形状正常解析', o == [(10.0, 9.0)] and nb == 0, 'out=%s nbad=%d' % (o, nb))

o, nb, lg = run_guard({'20261020': [10.0, 9.0]})
chk('A2 list 形状按 [close,preClose] 兜底', o == [(10.0, 9.0)] and nb == 0,
    'out=%s nbad=%d' % (o, nb))

o, nb, lg = run_guard({'20261020': 'junk'})
chk('A3 不可解释样本只跳过并计数', o == [] and nb == 1, 'out=%s nbad=%d' % (o, nb))
chk('A4 跳过日志带代码与类型', bool(lg) and '600000.SH' in lg[0] and 'str' in lg[0],
    lg[0][:70] if lg else 'no log')

o, nb, lg = run_guard({'20261020': {'close': 1.0, 'preClose': 1.0}, '20261021': [2.0, 1.0],
                       '20261022': None, '20261023': {'close': 3.0, 'preClose': 1.0}})
chk('A5 混合池 3 正常 + 1 跳过', len(o) == 3 and nb == 1, 'ok=%d nbad=%d' % (len(o), nb))

# ============ B. 抛点格式 ============
B = cut("_tbs = traceback.extract_tb(sys.exc_info()[2])", "for _tb in _tbs[-3:]])")
ns = {'traceback': traceback, 'sys': sys, 'os': os}


def _lvl3():
    raise AttributeError("'list' object has no attribute 'get'")


def _lvl2():
    _lvl3()


def _lvl1():
    _lvl2()


_at = ''
try:
    _lvl1()
except Exception:
    exec(compile('def _mk():\n'
                 + '\n'.join('    ' + x if x.strip() else x for x in B.split('\n'))
                 + '\n    return _at\n', '<at>', 'exec'), ns)
    _at = ns['_mk']()
chk('B1 抛点含 文件:行号(函数)', ':' in _at and '(' in _at and '_lvl' in _at,
    _at.strip()[:110])
chk('B2 至多三帧', _at.count(' <- ') <= 2, 'frames=%d' % (_at.count(' <- ') + 1))

# ============ C. 覆盖率告警分支 ============
i = next(k for k, s in enumerate(L) if "if _cov.get('exc'):" in s)
j = i
while "int(_cov.get('rounds') or 0)))" not in L[j]:
    j += 1
C = textwrap.dedent('\n'.join(L[i:j + 1]))


def run_cov(cov, pool):
    got = []
    ns = {'_cov': cov, '_SENT_ACC': {'md': pool},
          '_sent_use_last_good': lambda m: got.append(m),
          '_ratio': 0.0, '_min_cov': 0.9}
    src = ('def _t():\n'
           '    if _ratio is not None and _ratio < _min_cov:\n'
           + '\n'.join('        ' + x if x.strip() else x for x in C.split('\n'))
           + '\n')
    exec(compile(src, '<cov>', 'exec'), ns)
    ns['_t']()
    return got


g = run_cov({'req': 0, 'ok': 0, 'fail': 0, 'samples': ['list object has no attribute get'],
             'exc': True}, {'600000.SH': {}, '600001.SH': {}})
chk('C1 异常轮: 读数无效 + 池内实际只数',
    bool(g) and '本轮取数异常作废' in g[0] and '池内实际2只' in g[0] and '全市场' not in g[0],
    g[0] if g else 'no log')

g = run_cov({'req': 5226, 'ok': 300, 'fail': 0, 'retry': 0, 'rounds': 3,
             'round_ok': 300, 'acc_ok': 2700, 'acc_ratio': 0.52}, {})
chk('C2 正常轮: 「本轮请求」而非「全市场」',
    bool(g) and '本轮请求5226只' in g[0] and '全市场' not in g[0],
    g[0][:100] if g else 'no log')

fails = [n for n, c in ok if not c]
print('\n%d/%d PASS' % (len(ok) - len(fails), len(ok)))
if fails:
    print('FAILED:', fails)
