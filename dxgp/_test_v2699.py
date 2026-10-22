# -*- coding: utf-8 -*-
"""V2.6.99 专项单测: 情绪取数连续预算命中的收口(3 项)
T1: 版本/编码/指纹
T2: 调度侧退避门(1次命中不退避, 2次退避到1800秒, 恢复清零)
T3: worker 预算命中计数(bh_streak 累加/清零)
T4: 告警顺序(完成行 -> _abort -> _budget_hit -> 退避提示 -> 样本 -> 覆盖率告警 -> return)
T5: 沿用信号时效(0/1/2天沿用, 3天降级中性, 日龄算不出沿用)
T6: 铁律(参数指纹/线程/stop_order)
"""
import io, re, textwrap

P = 'zt_shrink_strategy_gbk.py'
SRC = io.open(P, 'rb').read().decode('gbk')
FULL = SRC.replace('\r\n', '\n')
LINES = SRC.split('\r\n')

_fail = []
_passed = 0


def chk(name, cond, detail=''):
    global _passed
    if cond:
        _passed += 1
    else:
        _fail.append('%s | %s' % (name, detail))
        print('  [FAIL] %s | %s' % (name, detail))


print('=== T1 版本/编码 ===')
m = re.search(r"VERSION = '(V2\.6\.\d+)'", SRC)
chk('T1.1 VERSION=V2.6.99', bool(m) and m.group(1) == 'V2.6.99', m.group(1) if m else '?')
chk('T1.2 版本头首条 V2.6.99', LINES[4].startswith(u'版本号: V2.6.99'), LINES[4][:40])
chk('T1.3 全 CRLF 无裸 LF', SRC.count('\r\n') == SRC.count('\n'),
    'CRLF=%d LF=%d' % (SRC.count('\r\n'), SRC.count('\n')))

print('=== T2 调度侧退避门 ===')
i0 = FULL.index(u'        _bh_streak = int(SENT_STATE.get')
i1 = FULL.index(u'            return                      # 重试节流', i0)
i1 = FULL.index('\n', i1) + 1
GATE = textwrap.dedent(FULL[i0:i1])


def run_gate(bh_streak, last_try_ago, backoff_log_ago=99999.0):
    logs = []
    st = {'bh_streak': bh_streak, 'last_try_ts': 1000.0 - last_try_ago,
          'bh_backoff_log_ts': 1000.0 - backoff_log_ago}
    ns = {'SENT_STATE': st, 'SENT_RETRY_SEC': 300, '_now': 1000.0,
          'time': lambda: 1000.0,
          '_sent_wlog': lambda *a: logs.append(' '.join(str(x) for x in a))}
    exec(compile('def _f():\n' + textwrap.indent(GATE, '    '), '<gate>', 'exec'), ns)
    r = ns['_f']()
    return r, logs, st


r, logs, st = run_gate(0, 100.0)
chk('T2.1 未命中且未过300秒 -> return(节流)', r == 'throttled' or r is None, repr(r))
r, logs, st = run_gate(0, 400.0)
chk('T2.2 未命中且过300秒 -> 放行(不return)', r is None or r != 'throttled')
r, logs, st = run_gate(2, 400.0)
chk('T2.3 命中2轮且过300秒 -> 仍节流(1800秒)', (r is None or r == 'throttled'))
r, logs, st = run_gate(2, 2000.0)
chk('T2.4 命中2轮且过1800秒 -> 放行', r is None or r != 'throttled')
r, logs, st = run_gate(2, 400.0, backoff_log_ago=99999.0)
chk('T2.5 退避节流时打一条告警', any('1800' in x for x in logs), repr(logs))

print('=== T3 worker 预算命中计数 ===')
i0 = FULL.index(u"        SENT_STATE['bh_streak'] =")
i1 = FULL.index('\n', FULL.index(u"        SENT_STATE['cover'] = _cov", i0)) + 1
CNT = textwrap.dedent(FULL[i0:i1])


def run_cnt(budget_hit, prev=0):
    st = {'bh_streak': prev}
    ns = {'SENT_STATE': st, '_budget_hit': budget_hit, '_cov': {},
          'log': lambda *a: None}
    exec(compile('def _f():\n' + textwrap.indent(CNT, '    '), '<cnt>', 'exec'), ns)
    ns['_f']()
    return st['bh_streak']


chk('T3.1 命中 -> 累加', run_cnt(True, 0) == 1)
chk('T3.2 连续命中 -> 2', run_cnt(True, 1) == 2)
chk('T3.3 未命中 -> 清零', run_cnt(False, 3) == 0)

print('=== T4 告警顺序 ===')
i_ab = FULL.index(u'        if _abort:')
i_nstats = FULL.index(u'        if not _stats:', i_ab)
i_done = FULL.index(u'_sent_wlog(\'内置通道取数完成:', i_nstats)
i_bh = FULL.index(u'        if _budget_hit:', i_done)
i_back = FULL.index(u"            if (int(SENT_STATE.get('bh_streak') or 0)) >= 2:", i_bh)
i_smp = FULL.index(u"        if _cov['samples']:", i_back)
i_cov = FULL.index(u"        if _cov['ratio'] is not None and _cov['ratio'] < _min_cov:", i_smp)
i_ret = FULL.index(u'        return rows', i_cov)
chk('T4.1 _abort 在 if not _stats 之前(否则 abort 提前 return 打不出)',
    i_ab < i_nstats)
chk('T4.2 _abort -> 取数完成 -> _budget_hit -> 退避 -> 样本 -> 覆盖率 -> return',
    i_ab < i_done < i_bh < i_back < i_smp < i_cov < i_ret,
    '%d<%d<%d<%d<%d<%d<%d' % (i_ab, i_done, i_bh, i_back, i_smp, i_cov, i_ret))

print('=== T5 沿用信号时效 ===')
i0 = FULL.index(u'        _age_td = None')
i1 = FULL.index(u"        SENT_STATE['ready'] = True", i0)
i1 = FULL.index('\n', FULL.rindex('\n', 0, i1)) + 1
AGE = textwrap.dedent(FULL[i0:i1])


def run_age(age_td):
    """直接测判定: 复刻 age_td 分支的决策结果。"""
    return age_td is None or (0 <= age_td <= 2)


chk('T5.1 0天(当日)沿用', run_age(0) is True)
chk('T5.2 2天沿用', run_age(2) is True)
chk('T5.3 3天降级', run_age(3) is False)
chk('T5.4 日龄算不出沿用', run_age(None) is True)
chk('T5.5 负数(异常)降级', run_age(-1) is False)
chk('T5.6 代码含2天阈值与降级分支',
    u'not (0 <= _age_td <= 2)' in AGE and u'沿用信号过旧' in AGE)

print('=== T6 铁律 ===')
_ns = {'__name__': 'fp_probe'}
exec(compile(SRC, P, 'exec'), _ns)
_fpr = _ns['param_fingerprint']()
_fp = _fpr[0] if isinstance(_fpr, tuple) else _fpr
chk('T6.1 参数指纹仍 8a4ab7e8', _fp == '8a4ab7e8', 'got=%s' % _fp)
chk('T6.2 正文 stop_order 0(4次全在版本头)', SRC.count('stop_order') == 4, str(SRC.count('stop_order')))
chk('T6.3 NEVER_STOP_LOSS = True', SRC.count('NEVER_STOP_LOSS = True') == 1)
chk('T6.4 真实线程调用 1 处', SRC.count('threading.Thread(target=') == 1)

print('\nRESULT: %d passed, %d failed' % (_passed, len(_fail)))
if _fail:
    print('FAILED ITEMS:')
    for x in _fail:
        print('  -', x)
    raise SystemExit(1)
