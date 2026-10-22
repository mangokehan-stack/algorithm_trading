# -*- coding: utf-8 -*-
"""V2.6.137 干跑: 累积池恢复 -> _bars_to_dict -> _row.get('close') 全链路
A/B 对照: 旧形状(list) 必抛 AttributeError, 新形状(dict) 必通过。
"""
import datetime
import json
import os
import textwrap

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
POOL = r'C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_sent_acc_8973786.json'

lines = open(P, 'rb').read().decode('gbk').split('\r\n')


def grab(name):
    st = None
    for i, l in enumerate(lines):
        if l.startswith('def ' + name + '('):
            st = i
            break
    assert st is not None, 'not found ' + name
    ed = len(lines)
    for j in range(st + 1, len(lines)):
        if lines[j] and not lines[j][0].isspace() and not lines[j].startswith('#'):
            ed = j
            break
    body = '\n'.join(lines[st:ed])
    return textwrap.dedent(body.replace('\t', '    '))


SRC_LOAD = grab('_sent_acc_load')
SRC_B2D = grab('_bars_to_dict')

print('=== 副本文案一致性 ===')
assert "V2.6.137: 还原出的 md 值一律为" in SRC_LOAD
assert "{'close': _cc, 'preClose': _pp}" in SRC_LOAD
assert '= [_cc, _pp]' not in SRC_LOAD
print('PASS  _sent_acc_load 副本含新形状且无旧形状')
assert "def _bars_to_dict(df):" in SRC_B2D
print('PASS  _bars_to_dict 副本取得')


class _G(object):
    today = '20261020'


def build_ns(shape):
    """shape='dict'(新) / 'list'(旧)"""
    ns = {
        'os': os, 'json': json, 'datetime': datetime,
        'G': _G, '_f': lambda x: 0.0 if x in (None, '') else float(x),
        '_exc_text': lambda e: '%s: %s' % (type(e).__name__, e),
        '_GEN_STATE': {'id': 1792504554.1},
        '_SENT_ACC': {'date': '', 'gen': 0.0, 'md': {}, 'ok': 0, 'fail': 0,
                      'rounds': 0, 'pend_rounds': 0, 'ser': {}},
        '_sent_acc_path': lambda: POOL,
        '_df_to_rows': lambda df: ({}),
    }
    # 注入两份函数源码; 旧形状版本在内存里改写, 不改磁盘
    src_load = SRC_LOAD
    if shape == 'list':
        src_load = src_load.replace(
            "{'close': _cc, 'preClose': _pp}", "[_cc, _pp]")
        assert "[_cc, _pp]" in src_load
    exec(compile(src_load, '<load>', 'exec'), ns)
    exec(compile(SRC_B2D, '<b2d>', 'exec'), ns)
    return ns


def drain(ns, tag):
    """模拟消费端 13233-13289: 整池重解析, 取 close/preClose"""
    n_ok = 0
    n_bars = 0
    pct_sum = 0.0
    for _c, _raw in ns['_SENT_ACC']['md'].items():
        bars = ns['_bars_to_dict'](_raw)
        for _d, _row in bars.items():
            c = ns['_f']((_row or {}).get('close'))
            p = ns['_f']((_row or {}).get('preClose'))
            if c <= 0 or p <= 0:
                continue
            pct_sum += (c / p - 1.0)
            n_bars += 1
        n_ok += 1
    print('  [%s] 遍历 %d 只, 有效 bar %d 个, pct均值 %.6f' % (tag, n_ok, n_bars, pct_sum / max(1, n_bars)))
    return n_ok, n_bars


print()
print('=== [A] 旧形状(list) —— 应当抛 AttributeError ===')
nsA = build_ns('list')
nA, whyA = nsA['_sent_acc_load']()
print('  load ->', nA, whyA[:100])
assert nA == 2700, '恢复只数 %d != 2700' % nA
_c0 = sorted(nsA['_SENT_ACC']['md'].keys())[0]
_v0 = nsA['_SENT_ACC']['md'][_c0]
print('  样本 %s 值类型 = %s' % (_c0, type(list(_v0.values())[0]).__name__))
try:
    drain(nsA, 'A/旧')
    print('  !! 没抛异常, A/B 无判别力')
    raise SystemExit(1)
except AttributeError as e:
    print('  PASS 预期异常已复现:', e)

print()
print('=== [B] 新形状(dict) —— 应当全通 ===')
nsB = build_ns('dict')
nB, whyB = nsB['_sent_acc_load']()
print('  load ->', nB, whyB[:120])
assert nB == 2700
assert '(跨代恢复: 盘内gen=%.1f, 本代gen=%.1f)' % (1792503584.7, 1792504554.1) in whyB, '未打跨代注明'
print('  PASS 跨代注明正确')
_c1 = sorted(nsB['_SENT_ACC']['md'].keys())[0]
_v1 = nsB['_SENT_ACC']['md'][_c1]
assert isinstance(_v1, dict) and _v1, '样本形状错: %s' % type(_v1).__name__
_k1 = sorted(_v1.keys())[0]
assert isinstance(_v1[_k1], dict), '日期值类型错: %s' % type(_v1[_k1]).__name__
assert set(_v1[_k1].keys()) == {'close', 'preClose'}, '日期值键错: %s' % _v1[_k1]
_dist = {}
for _vv in nsB['_SENT_ACC']['md'].values():
    _dist[len(_vv)] = _dist.get(len(_vv), 0) + 1
print('  样本 %s 天数=%d(池内最大73, 停牌票少), 日值键=%s  OK'
      % (_c1, len(_v1), sorted(_v1[_k1].keys())))
print('  天数分布(前6):', sorted(_dist.items(), key=lambda x: -x[1])[:6])
nB2, nbarB = drain(nsB, 'B/新')
assert nB2 == 2700
assert nbarB > 100000, '有效 bar 太少: %d' % nbarB
print('  PASS 全链路无异常, 有效 bar %d 个' % nbarB)

print()
print('=== [C] 落盘回写闭环(模拟 _sent_acc_dump 的 _bars_to_dict 分支) ===')
n_w = 0
bad = 0
for _c, _rw in nsB['_SENT_ACC']['md'].items():
    _one = {}
    for _d, _row in nsB['_bars_to_dict'](_rw).items():
        _cc = nsB['_f']((_row or {}).get('close'))
        _pp = nsB['_f']((_row or {}).get('preClose'))
        if _cc > 0 and _pp > 0:
            _one[_d] = [round(_cc, 4), round(_pp, 4)]
    if _one:
        n_w += 1
    else:
        bad += 1
print('  可回写 %d 只 / 空 %d 只' % (n_w, bad))
assert n_w == 2700 and bad == 0, '回写闭环失败'
print('  PASS 2700 只全部可回写, 与源池一致')

print()
print('=== [D] 源池与新池数值守恒(A/B 数值一致) ===')
src = json.load(open(POOL, 'r', encoding='utf-8'))
_dates = src['dates']
_n = len(_dates)
_diff = 0
for _c, _arr in list(src['md'].items())[:200]:
    _one = nsB['_SENT_ACC']['md'][_c]
    for _j in range(_n):
        _c4, _p4 = _arr[_j * 2], _arr[_j * 2 + 1]
        if _c4 <= 0 or _p4 <= 0:
            continue
        _got = _one.get(str(_dates[_j]))
        if _got is None or abs(_got['close'] - _c4) > 1e-9 or abs(_got['preClose'] - _p4) > 1e-9:
            _diff += 1
print('  抽查 200 只 x %d 天, 数值不符 %d 处' % (_n, _diff))
assert _diff == 0
print('  PASS 数值完全守恒')

print()
print('==== ALL PASS ====')
