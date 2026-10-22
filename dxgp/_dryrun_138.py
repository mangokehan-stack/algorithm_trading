# -*- coding: utf-8 -*-
"""V2.6.138 干跑: ① 抛点格式 ② 整池解析按只兜底(A/B: 去掉守卫必抛, 加守卫不抛)

全部用母版原文抽出来的代码段(不做手写副本), 并断言副本文案与母版一致。
"""
import re
import sys
import traceback

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
lines = open(P, 'rb').read().decode('gbk').split('\r\n')


def block_between(start_anchor, end_anchor, include_end=True):
    """按锚点取行(锚点必须唯一), 保留原缩进与顺序"""
    i0 = [i for i, l in enumerate(lines) if l == start_anchor]
    assert len(i0) == 1, '起点锚点不唯一: %r -> %d' % (start_anchor, len(i0))
    i0 = i0[0]
    i1 = None
    for j in range(i0, len(lines)):
        if lines[j] == end_anchor:
            i1 = j
            break
    assert i1 is not None, '终点锚点未找到: %r' % end_anchor
    return '\n'.join(lines[i0:i1 + (1 if include_end else 0)])


# ---------------------------------------------------------------- ① 抛点
A_START = '    except Exception as _e:'
A_END = '        return None'
# 该 except 块在文件里只有一处以「return None」收尾且紧跟 _sent_wlog 的异常行
i_exc = [i for i, l in enumerate(lines)
         if l == A_START and any("'exc': True}" in x for x in lines[i:i + 40])]
assert len(i_exc) == 1, '异常块定位失败: %d' % len(i_exc)
i0 = i_exc[0]
i1 = i0
while lines[i1] != A_END:
    i1 += 1
EXC_BLOCK = '\n'.join(lines[i0:i1 + 1])
assert '抛点: ' in EXC_BLOCK, '母版异常块里没有抛点'
assert "'exc': True}" in EXC_BLOCK, '母版异常块里没有 exc 标记'

print('=== 副本文案一致性 ===')
assert "本轮取数异常作废(覆盖率读数无效); 池内实际%d只" in '\n'.join(lines)
assert "累积%d只/全市场%d只/失败" not in '\n'.join(
    l for l in lines if not l.lstrip().startswith('#'))
print('PASS  母版含新告警文案, 旧「全市场」错标已消失')

_LOGS = []


def _wlog(msg):
    _LOGS.append(msg)


def build_exc_ns():
    ns = {
        'traceback': traceback, 'sys': sys, 'os': __import__('os'),
        '_exc_text': lambda e: '%s: %s' % (type(e).__name__, e),
        '_sent_wlog': _wlog,
        'SENT_STATE': {},
        '_SENT_ACC': {'md': dict.fromkeys(['600000.SH'] * 1 + ['000001.SZ'] * 2699)},
    }
    src = 'def _probe():\n    try:\n        _boom()\n' + EXC_BLOCK + '\n'

    def _boom():
        def _deeper():
            raise AttributeError("'list' object has no attribute 'get'")
        _deeper()
    ns['_boom'] = _boom
    exec(compile(src, '<exc>', 'exec'), ns)
    return ns


print()
print('=== [A] 异常日志补抛点 ===')
nsA = build_exc_ns()
ret = nsA['_probe']()
assert ret is None, '异常分支应 return None'
assert len(_LOGS) == 1, '应只打一条日志: %d' % len(_LOGS)
_msg = _LOGS[0]
print('  日志 =', _msg)
assert _msg.startswith('情绪取数异常(内置通道), 数据跳过(中性): '), '旧前缀被破坏'
assert ' | 抛点: ' in _msg, '缺抛点'
_after = _msg.split(' | 抛点: ', 1)[1]
print('  抛点 =', _after)
assert re.match(r'^.+:\d+\(\w+\)( <- .+:\d+\(\w+\)){0,2}$', _after), '抛点格式不符'
assert '(_deeper)' in _after, '最内帧应是 _deeper'
assert '(_boom)' in _after, '第二帧应是 _boom'
assert "'list' object has no attribute 'get'" in _msg
_cov = nsA['SENT_STATE'].get('cover') or {}
assert _cov.get('exc') is True, 'cover 未打 exc 标记'
assert _cov.get('samples') and _after in _cov.get('samples')[0], 'samples 未带抛点'
print('  PASS 抛点三帧 + exc 标记 + samples 同步')

print()
print('=== [A2] traceback 取不到时不影响主流程 ===')


def build_exc_ns_bad():
    ns = build_exc_ns()
    ns['traceback'] = None      # 人为让它抛 AttributeError
    return ns


nsA2 = build_exc_ns_bad()
_LOGS[:] = []
ret = nsA2['_probe']()
assert ret is None
assert len(_LOGS) == 1
assert ' | 抛点: ' not in _LOGS[0], '取不到时不该打抛点: %s' % _LOGS[0]
assert nsA2['SENT_STATE']['cover'].get('exc') is True
print('  PASS 抛点为空但异常文本/cover 照常  ->', _LOGS[0][:90])

# ---------------------------------------------------------------- ② 按只兜底
G_START = "                if _d3 < _start:"
G_END = "                _p3 = _f((_row3 or {}).get('preClose'))"
rng = [i for i, l in enumerate(lines) if l == G_START]
assert len(rng) == 1, '守卫起点不唯一: %d' % len(rng)
g0 = rng[0]
g1 = g0
while lines[g1] != G_END:
    g1 += 1
GUARD_BLOCK = '\n'.join(lines[g0:g1 + 1])
assert "_row3 = {'close': _row3[0], 'preClose': _row3[1]}" in GUARD_BLOCK
# 旧版 = 只留首两行(日期窗判断) + 末两行(取值), 中间守卫全部去掉。
#   不能按 "strip()=='continue'" 过滤 —— 首行的 continue 也是 continue, 会被一起删掉,
#   于是 if 无体 -> IndentationError(干跑自身报错, 与母版无关)。
_gl = GUARD_BLOCK.split('\n')
assert _gl[0].strip() == 'if _d3 < _start:'
assert _gl[1].strip() == 'continue'
assert _gl[-2].strip().startswith('_c3 = _f')
assert _gl[-1].strip().startswith('_p3 = _f')
OLD_BLOCK = '\n'.join([_gl[0], _gl[1], _gl[-2], _gl[-1]])
assert 'isinstance(_row3, dict)' not in OLD_BLOCK, '旧版构造失败:\n%s' % OLD_BLOCK
assert '_c3 = _f' in OLD_BLOCK
print('  旧版副本构造 OK(4 行, 无守卫)')


def build_parse_ns(block):
    src = ('def _parse(_rows, _start, _f, _wlog):\n'
           '    _sent_wlog = _wlog      # 母版里的日志函数, 干跑用注入的收集器\n'
           '    _nbad3 = 0\n'
           '    _res = []\n'
           '    for _s3, (_d3, _row3) in _rows:\n'
           + block + '\n'
           '                _res.append((_d3, _c3, _p3))\n'
           '    return _res, _nbad3\n')
    ns = {'_f': _f138, '_wlog': _wlog}
    exec(compile(src, '<parse>', 'exec'), ns)
    return ns


def _f138(x):
    if x in (None, ''):
        return 0.0
    return float(x)


CASES = [
    ('dict 正常', ({'close': 10.0, 'preClose': 9.0},), (10.0, 9.0), False),
    ('list 兼容', ([10.0, 9.0],), (10.0, 9.0), False),
    ('tuple 兼容', ((10.0, 9.0),), (10.0, 9.0), False),
    ('单元素 list 跳过', ([10.0],), None, True),
    ('字符串 跳过', ('junk',), None, True),
    ('None 跳过', (None,), None, True),
]

print()
print('=== [B] 新守卫: 六种形状逐只兜底 ===')
nsN = build_parse_ns(GUARD_BLOCK)
for _name, _v, _want, _skip in CASES:
    _rows = [('600000.SH', ('20261020', _v[0]))]
    _logs = []
    _res, _nb = nsN['_parse'](_rows, '20260101', _f138, _logs.append)
    if _skip:
        assert _res == [] and _nb == 1, '%s 应跳过并计 1: res=%s nb=%d' % (_name, _res, _nb)
        print('  PASS %-16s -> 跳过(计1), 日志%d条' % (_name, len(_logs)))
    else:
        assert _res and abs(_res[0][1] - _want[0]) < 1e-9 and abs(_res[0][2] - _want[1]) < 1e-9, \
            '%s 取值错: %s' % (_name, _res)
        assert _nb == 0, '%s 不该计跳过' % _name
        print('  PASS %-16s -> close=%.2f preClose=%.2f' % (_name, _res[0][1], _res[0][2]))

print()
print('=== [B2] 混合池: 1 只坏 + 3 只好, 其余照算 ===')
_mix = [('600000.SH', ('20261020', {'close': 1.0, 'preClose': 1.0})),
        ('600001.SH', ('20261020', 'junk')),
        ('600002.SH', ('20261020', [2.0, 1.0])),
        ('600003.SH', ('20261020', {'close': 3.0, 'preClose': 1.0}))]
_res, _nb = nsN['_parse'](_mix, '20260101', _f138, lambda m: None)
print('  通过 %d 只 / 跳过 %d 只' % (len(_res), _nb))
assert len(_res) == 3 and _nb == 1, '混合池处置错'
print('  PASS 坏样本只损失自己, 其余 3 只照常进统计')

print()
print('=== [B3] A/B 判别力: 去掉守卫后同一输入必抛 ===')
nsO = build_parse_ns(OLD_BLOCK)
try:
    nsO['_parse']([('600000.SH', ('20261020', [10.0, 9.0]))], '20260101', _f138, lambda m: None)
    print('  !! 旧版没抛, A/B 无判别力')
    raise SystemExit(1)
except AttributeError as e:
    print('  PASS 旧版复现线上异常:', e)

print()
print('==== ALL PASS ====')
