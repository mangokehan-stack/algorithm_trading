# -*- coding: utf-8 -*-
u"""V2.6.98 专项单测(独立执行, 不依赖 QMT 环境)

用户回"全部修复, 根据你的推荐思路", 1 项真风险 + 4 项日志:
  T1 元数据      —— VERSION / 版本头 / 全 CRLF / 行数
  T2 数据阶段    —— 真跑 status_log 代码块: 0/1/2/未知 四档中文且不再出现"初始化阶段=0"
  T3 候选口径    —— 真跑口径注代码块: 截断前 4 / 入库 2 时点明差异
  T4 日志顺序    —— 优选行 -> 口径注 -> 落选行(不再先落选后候选)
  T5 回撤符号    —— 真跑优选项格式: pullback<0 印"昨收上涨", >=0 印百分数
  T6 补选股兜底  —— 真跑 rescreen 尾部: 1次不重置 / 3次且未达上限则重置 / 超上限只告警 / 无接口只告警
  T7 铁律与指纹  —— stop_order 0 / NEVER_STOP_LOSS / Thread 1 / _api 52 / 参数指纹 8a4ab7e8

设计原则(延续 _test_v2687~2697): exec 母版真实代码块, 不重写判据。
"""
import io
import re
import textwrap

P = 'zt_shrink_strategy_gbk.py'
_raw = io.open(P, 'rb').read()
SRC = _raw.decode('gbk')
FULL = SRC.replace('\r\n', '\n')
LINES = SRC.split('\r\n')

PASS, FAIL = [], []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))


# ---------------------------------------------------------------- T1 元数据
print('=== T1 元数据 ===')
m = re.search(r"VERSION\s*=\s*'(V2\.6\.\d+)'", SRC)
chk('T1.1 VERSION>=V2.6.98', bool(m) and tuple(int(x) for x in m.group(1)[1:].split('.')) >= (2,6,98), m.group(1) if m else '?')
chk('T1.2 版本头首条不早于 V2.6.98', LINES[4].startswith(u'版本号: V2.6.'), LINES[4][:44])
chk('T1.3 上一版记录仍在(V2.6.98)', any(l.startswith(u'版本号: V2.6.98') for l in LINES[5:12]))
chk('T1.4 全 CRLF 无裸 LF', SRC.count('\r\n') == SRC.count('\n'),
    'CRLF=%d LF=%d' % (SRC.count('\r\n'), SRC.count('\n')))
chk('T1.5 行数>=12660', len(LINES) >= 12660, 'actual=%d' % len(LINES))

# ---------------------------------------------------------------- T2 数据阶段
print('=== T2 数据阶段中文映射(真跑状态日志块) ===')
t0 = FULL.index(u"    _ds = '' if bool(getattr(G, 'loss_data_ok', True)) else")
t1 = FULL.index(u"pnl_brief(), sig[7], sig[8], _ds))", t0)
t1 = FULL.index('\n', t1) + 1
PH = textwrap.dedent(FULL[t0:t1])
chk('T2.0 块含三档映射', u"{0: u'已完成', 1: u'下载中', 2: u'待加载'}" in PH)
chk('T2.0b 旧格式串"初始化阶段=%d"已不在', u'初始化阶段=%d' not in PH and u'数据阶段=%s(dl_phase=%d)' in PH)


class _GPh(object):
    loss_data_ok = True
    acct_ok = True
    state_broken = False


def run_ph(dl_phase, acct_ok=True, broken=False):
    logs = []
    g = _GPh()
    g.acct_ok = acct_ok
    g.state_broken = broken
    sig = ('20261020', 'pre', dl_phase, acct_ok, broken,
           ['a', 'b'], ['x', 'y'], 0, 0, (), 14504, True)
    ns = {'G': g,
          'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
          'PHASE_NAME': {'pre': u'非交易时段(盘前/午休/盘后)'},
          'pnl_brief': lambda: u'浮动盈亏=-207.00元',
          'sig': sig}
    exec(compile(PH, '<ph>', 'exec'), ns)
    return logs[0] if logs else ''


s0 = run_ph(0)
chk('T2.1 dl_phase=0 印"已完成"', u'数据阶段=已完成(dl_phase=0)' in s0, s0)
s1 = run_ph(1)
chk('T2.2 dl_phase=1 印"下载中"', u'数据阶段=下载中(dl_phase=1)' in s1, s1)
s2 = run_ph(2)
chk('T2.3 dl_phase=2 印"待加载"', u'数据阶段=待加载(dl_phase=2)' in s2, s2)
s9 = run_ph(9)
chk('T2.4 未知档不抛异常且原值可见', u'数据阶段=未知9(dl_phase=9)' in s9, s9)
chk('T2.5 四档都不再出现"初始化阶段"', all(u'初始化阶段' not in x for x in (s0, s1, s2, s9)))
chk('T2.6 持仓/候选数照旧', u'持仓2只 候选2只' in s0, s0)
chk('T2.7 账号异常照旧', u'账号=异常' in run_ph(0, acct_ok=False), run_ph(0, acct_ok=False))

# ---------------------------------------------------------------- T3 候选口径注
print('=== T3 候选数两个口径点明(真跑) ===')
c0 = FULL.index(u'    if total > len(G.candidates):')
c1 = FULL.index(u'    for i, c in enumerate(G.candidates):', c0)
NOTE = textwrap.dedent(FULL[c0:c1])
chk('T3.0 块含口径说明', u'上方漏斗' in NOTE and u'状态行' in NOTE)


def run_note(total, kept):
    logs = []
    ns = {'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
          'total': total, 'G': type('G', (), {'candidates': [0] * kept})()}
    exec(compile(NOTE, '<note>', 'exec'), ns)
    return logs


lg = run_note(4, 2)
chk('T3.1 4->2 时打一条口径注', len(lg) == 1, repr(lg))
chk('T3.2 注里三个数字都对', u'候选4只' in lg[0] and u'入库的2只' in lg[0]
    and u'差出的2只' in lg[0], repr(lg))
chk('T3.3 未截断时不打注', run_note(2, 2) == [], repr(run_note(2, 2)))
chk('T3.4 空候选不打注', run_note(0, 0) == [], repr(run_note(0, 0)))

# ---------------------------------------------------------------- T4 日志顺序
print('=== T4 输出顺序: 优选 -> 口径注 -> 落选 ===')
_i_pref = FULL.index(u'  第%d优先 %s %s T0=%s')
_i_note = FULL.index(u'  注: 上方漏斗')
_i_rej = FULL.index(u'  落选(超出每日优选上限')
_i_cand = FULL.index(u'今日低吸候选共%d只')
chk('T4.1 口径注紧跟在候选行之后', _i_cand < _i_note < _i_pref)
chk('T4.2 落选行在优选项之后', _i_pref < _i_rej)
chk('T4.3 落选循环已不在切片处', FULL.index(u'    for _rlc in _rej:') > _i_pref)
chk('T4.4 落选循环读的是 _rej(切片前存下的)',
    u'_rej = list(G.candidates[MAX_DAILY_PICKS:])' in FULL)
chk('T4.5 口径注指向下方落选行', u'明细见下方' in NOTE)

# ---------------------------------------------------------------- T5 回撤符号
print('=== T5 回撤负数换算成上涨(真跑优选项格式) ===')
p0 = FULL.index(u"        _pb_raw = c['pullback'] * 100.0")
p1 = FULL.index(u"_pb_txt, c['zt_close'], c['offset'], _tt_txt, _fin_txt))", p0)
p1 = FULL.index('\n', p1) + 1
PREF = textwrap.dedent(FULL[p0:p1])


class _GC(object):
    pass


def run_pref(pullback):
    logs = []
    c = {'stock': '002543.SZ', 'name': u'万和电气', 't0': '20261013',
         'base_vol': 823441, 'shrink_rank': 0.87, 'pullback': pullback,
         'zt_close': 14.25, 'offset': 3}
    ns = {'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
          'c': c, 'i': 0, '_tt_txt': u'涨停日换手=9.4%',
          '_fin_txt': u'公告日期=20260827 | 净利润=6145.61万元'}
    exec(compile(PREF, '<pref>', 'exec'), ns)
    return logs[0]


chk('T5.1 负回撤印"昨收上涨1.9%"', u'昨收回撤=昨收上涨1.9%' in run_pref(-0.019), run_pref(-0.019))
chk('T5.2 正回撤照旧印百分数', u'昨收回撤=7.9%' in run_pref(0.079), run_pref(0.079))
chk('T5.3 零回撤印0.0%', u'昨收回撤=0.0%' in run_pref(0.0), run_pref(0.0))
chk('T5.4 不再出现负号', u'回撤=-' not in run_pref(-0.019), run_pref(-0.019))

# ---------------------------------------------------------------- T6 补选股兜底
print('=== T6 补选股加载不足时的下载兜底(真跑 rescreen 尾部) ===')
r0 = FULL.index(u"    _tries = int(getattr(G, 'rescreen_tries', 0)) + 1")
r1 = FULL.index(u"        (_tries, MIN_UNIVERSE_FOR_SCREEN, len(G.hist), G.rsdl_reset_n))", r0)
r1 = FULL.index('\n', r1) + 1
RS = textwrap.dedent(FULL[r0:r1])
chk('T6.0 块含重置三件套',
    u"G.state['last_dl_date'] = ''" in RS and u"G.state['last_init_date'] = ''" in RS
    and u'G.dl_phase = 0' in RS)


class _GRs(object):
    def __init__(self, tries=0, resets=0, n_hist=500, no_dl=False):
        self.state = {'last_dl_date': '20261020', 'last_init_date': '20261020'}
        self.hist = dict((str(i), []) for i in range(n_hist))
        self.no_download = no_dl
        self.dl_phase = 2
        self.dl_i = 5226
        self.dl_mark = 2
        self.rescreen_tries = tries
        self.rsdl_reset_n = resets


def run_rs(tries=0, resets=0, n_hist=500, no_dl=False):
    logs, saved = [], []
    g = _GRs(tries, resets, n_hist, no_dl)
    ns = {'G': g, 'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
          'MIN_UNIVERSE_FOR_SCREEN': 2000, 'save_state': lambda: saved.append(1)}
    # RS 块里有多个 return, 必须包成函数执行(textwrap.indent 保持相对缩进)
    src = 'def _wrap():\n' + textwrap.indent(RS, '    ')
    exec(compile(src, '<rs>', 'exec'), ns)
    ns['_wrap']()
    return logs, g, saved


lg1, g1, sv1 = run_rs(tries=0)
chk('T6.1 第1次不足: 只计数不重置', lg1 == [] and g1.rescreen_tries == 1
    and g1.state['last_init_date'] == '20261020' and sv1 == [], repr(lg1))
lg2, g2, sv2 = run_rs(tries=1)
chk('T6.2 第2次不足: 仍不重置', lg2 == [] and g2.rescreen_tries == 2
    and g2.state['last_dl_date'] == '20261020', repr(lg2))
lg3, g3, sv3 = run_rs(tries=2)
chk('T6.3 第3次不足: 重置下载状态机', len(lg3) == 1 and u'判定本地日线缓存残缺' in lg3[0], repr(lg3))
chk('T6.4 重置清空两个日期键', g3.state['last_dl_date'] == ''
    and g3.state['last_init_date'] == '', repr(g3.state))
chk('T6.5 重置阶段机与游标', g3.dl_phase == 0 and g3.dl_i == 0 and g3.dl_mark == -1,
    '%s/%s/%s' % (g3.dl_phase, g3.dl_i, g3.dl_mark))
chk('T6.6 重置次数+1 且重试计数清零', g3.rsdl_reset_n == 1 and g3.rescreen_tries == 0,
    '%s/%s' % (g3.rsdl_reset_n, g3.rescreen_tries))
chk('T6.7 重置即落盘', sv3 == [1], repr(sv3))
chk('T6.8 日志含实际只数与第几次', u'实际仅500只' in lg3[0] and u'第1/2次' in lg3[0], repr(lg3))
lg4, g4, sv4 = run_rs(tries=2, resets=2)
chk('T6.9 已达重置上限: 只告警不再重置', len(lg4) == 1 and u'已重置下载2次仍未补齐' in lg4[0]
    and g4.state['last_init_date'] == '20261020' and sv4 == [], repr(lg4))
lg5, g5, sv5 = run_rs(tries=2, no_dl=True)
chk('T6.10 无下载接口: 只告警不重置', len(lg5) == 1
    and u'本机无 download_history_data 接口' in lg5[0]
    and g5.state['last_init_date'] == '20261020' and sv5 == [], repr(lg5))
lg6, g6, sv6 = run_rs(tries=5, resets=0, n_hist=10)
chk('T6.11 极端(只剩10只)也能重置且不抛', len(lg6) == 1 and g6.rsdl_reset_n == 1, repr(lg6))

# ---------------------------------------------------------------- T7 铁律与指纹
print('=== T7 铁律与指纹 ===')
BODY = '\n'.join(l for l in FULL.split('\n') if not l.startswith(u'版本号: '))
chk('T7.1 正文 stop_order 0 次', BODY.count('stop_order') == 0, BODY.count('stop_order'))
chk('T7.2 NEVER_STOP_LOSS 未动', 'NEVER_STOP_LOSS = True' in BODY)
chk('T7.3 threading.Thread 仍1处', BODY.count('threading.Thread(target=') == 1,
    BODY.count('threading.Thread(target='))
chk('T7.4 _api( 仍52次', BODY.count('_api(') == 52, BODY.count('_api('))
try:
    _ns = {'__name__': 'fp_probe'}
    exec(compile(SRC, P, 'exec'), _ns)
    _fpr = _ns['param_fingerprint']()      # 返回 (指纹, 规范化参数串)
    _fp = _fpr[0] if isinstance(_fpr, tuple) else _fpr
except Exception as _e:
    _fp = 'ERR:%s' % _e
chk('T7.5 参数指纹仍 8a4ab7e8', _fp == '8a4ab7e8', 'got=%s' % _fp)
chk('T7.6 未新增模块级大写常量',
    'RESCREEN_DOWNLOAD_AFTER' not in BODY and 'RSDL_RESET_MAX' not in BODY
    and 'DL_PHASE_TXT' not in BODY)

print('\n========== %d PASS / %d FAIL ==========' % (len(PASS), len(FAIL)))
if FAIL:
    print('FAILED: %s' % FAIL)
    raise SystemExit(1)
print('ALL GREEN')
