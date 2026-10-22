# -*- coding: utf-8 -*-
"""Functional tests for V2.6.82 Bug C (PYRAMID_BATCHES) / Bug D (print_summary) fixes."""
import ast
import os
import sys
import tempfile
import traceback

P = 'zt_shrink_strategy_gbk.py'
SRC = open(P, 'rb').read().decode('gbk', errors='strict')

PASS = 0
FAIL = 0


def ok(name, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('  PASS  %s' % name)
    else:
        FAIL += 1
        print('  FAIL  %s   %s' % (name, extra))


print('=' * 70)
print('PART 0: module exec + namespace')
print('=' * 70)
tmp = tempfile.mkdtemp(prefix='test_bugcd_')
ns = {'__file__': os.path.join(tmp, P), '__name__': 'zt_mod'}
exec(compile(SRC, P, 'exec'), ns)
ok('0.1 module exec clean', True)
ok('0.2 print_summary defined', callable(ns.get('print_summary')))
ok('0.3 pyramid_add defined', callable(ns.get('pyramid_add')))
ok('0.4 PYRAMID_BATCHES no longer needed/absent', 'PYRAMID_BATCHES' not in ns)

print()
print('=' * 70)
print('PART A: print_summary behaviour')
print('=' * 70)


class MockG(object):
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def call_summary(g_obj, log_raises=False, flush_raises=False):
    """Call the real print_summary from module ns with patched G/log/_flush_log."""
    logs = []
    flushes = []

    def _log(*a):
        if log_raises:
            raise RuntimeError('log boom')
        logs.append(' '.join(str(x) for x in a))

    def _flush(force=False):
        flushes.append(force)
        if flush_raises:
            raise RuntimeError('flush boom')

    saved = (ns.get('G'), ns.get('log'), ns.get('_flush_log'), ns.get('traceback'))
    ns['G'] = g_obj
    ns['log'] = _log
    ns['_flush_log'] = _flush
    ns['traceback'] = type('T', (), {'print_exc': staticmethod(lambda: None)})()
    try:
        ns['print_summary']()
    finally:
        ns['G'], ns['log'], ns['_flush_log'], ns['traceback'] = saved
    return logs, flushes


logs, flushes = call_summary(MockG(buy_cnt=3, sell_cnt=2, state={'hold': {'a': {}, 'b': {}}}))
ok('A1.1 two log lines', len(logs) == 2, logs)
ok('A1.2 header line', '本次运行结束汇总' in logs[0], logs[:1])
ok('A1.3 buy/sell counts', '买入3笔' in logs[1] and '卖出2笔' in logs[1], logs[1:])
ok('A1.4 hold count', '持仓2只' in logs[1], logs[1:])
ok('A1.5 force flush', flushes == [True], flushes)

logs, flushes = call_summary(MockG(buy_cnt=0, sell_cnt=0, state=None))
ok('A2.1 state=None no raise + hold 0', len(logs) == 2 and '持仓0只' in logs[1], logs)
ok('A2.2 force flush still called', flushes == [True], flushes)

logs, flushes = call_summary(MockG(buy_cnt=7, sell_cnt=1, state={'hold': {}}))
ok('A3.1 empty hold', '持仓0只' in logs[1], logs)

# missing counters entirely -> default 0
logs, flushes = call_summary(MockG(state={}))
ok('A4.1 missing counters default 0', '买入0笔' in logs[1] and '卖出0笔' in logs[1], logs)

# log raises -> must not propagate, flush still runs (separate try)
try:
    logs, flushes = call_summary(MockG(buy_cnt=1, sell_cnt=1, state={}), log_raises=True)
    ok('A5.1 log raising swallowed', True)
    ok('A5.2 flush still runs when log raises', flushes == [True], flushes)
except Exception as e:
    ok('A5.1 log raising swallowed', False, repr(e))
    ok('A5.2 flush still runs when log raises', False, 'exception escaped')

# flush raises -> must not propagate
try:
    logs, flushes = call_summary(MockG(buy_cnt=1, sell_cnt=1, state={}), flush_raises=True)
    ok('A6.1 flush raising swallowed', True)
except Exception as e:
    ok('A6.1 flush raising swallowed', False, repr(e))

print()
print('=' * 70)
print('PART B: pyramid_add consistency check (no NameError, no false alarm)')
print('=' * 70)
tree = ast.parse(SRC)
fn_node = None
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == 'pyramid_add':
        fn_node = node
        break
assert fn_node is not None, 'pyramid_add not found'
fn_src = ast.get_source_segment(SRC, fn_node)


def run_pyramid(h, vol, batch_total):
    logs = []

    def _log(*a):
        logs.append(' '.join(str(x) for x in a))

    class Dummy(object):
        def __init__(self, *a, **kw):
            pass

        def __call__(self, *a, **kw):
            raise AssertionError('unexpected dep call')

    env = {
        'log': _log,
        'disp': lambda s: s,
        'emergency_block': lambda scope: '测试拦截(提前返回, 只验校验块)',
        'traceback': traceback,
    }
    exec(compile(fn_src, '<pyramid_add>', 'exec'), env)
    try:
        rv = env['pyramid_add']('002142.SZ', h, 10.0, vol, 1, batch_total, '测试加仓', None)
        return rv, logs, None
    except Exception as e:
        return None, logs, e


rv, logs, err = run_pyramid({'plan_batches': [100, 200, 300]}, 100, 3)
ok('B1.1 batch_total==plan len: no warning', err is None and not any('参数一致性告警' in x for x in logs), logs)
ok('B1.2 early return 0.0 by mock block', rv == 0.0, rv)

rv, logs, err = run_pyramid({'plan_batches': [100, 200, 300]}, 100, 2)
ok('B2.1 mismatch: warning emitted', err is None and any('参数一致性告警' in x for x in logs), logs)
ok('B2.2 warning has both numbers', any('传入2批' in x and '本票计划3批' in x for x in logs), logs)

rv, logs, err = run_pyramid({}, 100, 3)
ok('B3.1 no plan_batches: no warning', err is None and not any('参数一致性告警' in x for x in logs), logs)

rv, logs, err = run_pyramid({'plan_batches': []}, 100, 3)
ok('B3.2 empty plan_batches: no warning', err is None and not any('参数一致性告警' in x for x in logs), logs)

rv, logs, err = run_pyramid({'plan_batches': [100, 200, 300]}, 50, 3)
ok('B4.1 vol<100 returns 0.0, no log', err is None and rv == 0.0 and logs == [], (rv, logs))

rv, logs, err = run_pyramid({'plan_batches': [100, 200, 300]}, 100, 3)
ok('B5.1 NO NameError any more', err is None, repr(err))
if err:
    print('   >>> exception:', err)

print()
print('=' * 70)
print('PART C: static regression')
print('=' * 70)
code_lines = SRC.split('\r\n')
exe_hits = [i + 1 for i, ln in enumerate(code_lines)
            if 'PYRAMID_BATCHES' in ln and not ln.lstrip().startswith('#')
            and not ln.lstrip().startswith('版本号')]
ok('C1.1 no executable PYRAMID_BATCHES', not exe_hits, exe_hits)
ok('C1.2 def print_summary exactly once',
   sum(1 for ln in code_lines if ln.startswith('def print_summary(')) == 1)
ok('C1.3 atexit.register(print_summary) present',
   any('atexit.register(print_summary)' in ln for ln in code_lines))
ok('C1.4 names cache register still present',
   any('atexit.register(_flush_names_cache, True)' in ln for ln in code_lines))
ok('C1.5 compile OK', bool(compile(SRC, P, 'exec')))
ok('C1.6 CRLF only', SRC.count('\r\n') == len(code_lines) - 1)
ok('C1.7 no bare LF', SRC.replace('\r\n', '').count('\n') == 0)

print()
print('=' * 70)
print('RESULT: %d passed, %d failed' % (PASS, FAIL))
print('=' * 70)
sys.exit(1 if FAIL else 0)
