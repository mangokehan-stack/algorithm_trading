# -*- coding: utf-8 -*-
"""V2.6.96 专项单测(独立执行, 不依赖 QMT 环境)

用户点选第 1、3、4 项, 三项都围绕"下载与情绪取数抢接口"这条线:
  T1 元数据      —— VERSION / 版本头 / 全 CRLF
  T2 下载阶段1   —— 真跑 step_day_init 的阶段1 代码块, 用假时钟+假接口验证:
                    块大小 x5(2000)/瞬时接口一轮到底/预算用完让出并续下/
                    单只即超预算的死循环保护/no_download 语义不变
  T3 情绪推迟闸门 —— 真跑 sent_daily_refresh, 验证下载中推迟、日志 300 秒节流、
                    推迟满 30 分钟强制发起、下载结束后恢复发起
  T4 预算命中门槛 —— 真跑 _sent_apply_rows 的判定段: 94.3% 在预算命中时被拒(98%),
                    未命中时沿用原 90% 门槛
  T5 铁律与指纹   —— stop_order 0 / NEVER_STOP_LOSS 未动 / Thread 1 / _api 52 / 8a4ab7e8

设计原则(延续 _test_v2688~2695): exec 母版真实代码块, 不重写判据。
"""
import hashlib
import io
import re
import textwrap

P = 'zt_shrink_strategy_gbk.py'
raw = io.open(P, 'rb').read()
SRC = raw.decode('gbk')
FULL = SRC.replace('\r\n', '\n')
BODY = '\n'.join(l for l in FULL.split('\n') if not l.startswith(u'版本号: '))
LINES = SRC.split('\r\n')

PASS, FAIL = [], []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))


# ================================================================ T1
print('=== T1 元数据 ===')
m = re.search(r"VERSION = '([^']+)'", BODY)
_vt = tuple(int(x) for x in m.group(1).lstrip('V').split('.')) if m else (0, 0, 0)
chk('T1.1 VERSION>=V2.6.96', _vt >= (2, 6, 96), m.group(1) if m else '?')
_mh = re.match(u'版本号: V2\\.6\\.(\\d+)', LINES[4])
chk('T1.2 版本头首条不早于 V2.6.96',
    _mh is not None and int(_mh.group(1)) >= 96, LINES[4][:40])
chk('T1.3 全 CRLF 无裸 LF', SRC.count('\r\n') == SRC.count('\n'),
    'CRLF=%d LF=%d' % (SRC.count('\r\n'), SRC.count('\n')))
chk('T1.4 上一版记录仍在(V2.6.95)',
    any(l.startswith(u'版本号: V2.6.95') for l in LINES[5:12]))
print('       行数=%d 字节=%d MD5=%s'
      % (len(LINES), len(raw), hashlib.md5(raw).hexdigest().upper()))

# ================================================================ T2 下载阶段1
print('=== T2 下载阶段1(真跑代码块) ===')
_i0 = FULL.index('    if G.dl_phase == 1:')
_i1 = FULL.index('    # 阶段2: 加载历史 + 选股')
DL_SRC = 'def _run():\n' + textwrap.indent(textwrap.dedent(FULL[_i0:_i1]), '    ')
chk('T2.0 块大小写成局部算式(不改模块级常量)',
    '_chunk_n = DOWNLOAD_CHUNK * 5' in FULL and 'DOWNLOAD_CHUNK = 400' in FULL
    and 'DOWNLOAD_CHUNK = 2000' not in FULL)
chk('T2.0b while 条件含 no_download 短路',
    'while G.dl_i < _u_tot and not G.no_download:' in DL_SRC)


class RecList(list):
    """记录被切片取走的长度, 用来验证单块确实是 2000(块x5)。"""

    def __init__(self, seq):
        list.__init__(self, seq)
        self.slices = []

    def __getitem__(self, k):
        r = list.__getitem__(self, k)
        if isinstance(k, slice):
            self.slices.append(len(r))
        return r


class FakeG(object):
    def __init__(self, n, dl_i=0, no_dl=False):
        self.universe = RecList(['%06d.SZ' % k for k in range(n)])
        self.dl_i = dl_i
        self.dl_phase = 1
        self.dl_start = '20260901'
        self.today = '20261020'
        self.no_download = no_dl
        self.dl_mark = -1
        self.state = {}


class FakeClock(object):
    """时间只在"接口调用"上推进 —— 真实耗时本来就在 download_history_data 里,
    time.time() 本身不耗时。若让每次 time() 都推进, 会在 while 顶部就超预算 break,
    反而测不到 for 内"单只即超预算"的分支。"""

    def __init__(self, t=1000.0, step=0.0):
        self.t = t
        self.step = step

    def time(self):
        return self.t

    def advance(self):
        self.t += self.step


def run_dl(n, budget=8.0, step=0.0, dl_i=0, no_dl=False, drop_api=False):
    g = FakeG(n, dl_i, no_dl)
    clock = FakeClock(step=step)
    logs, calls = [], []

    def _download(code, period, start, end):
        calls.append(code)
        clock.advance()

    class _State(dict):
        pass

    g.state = {'last_dl_date': ''}
    # V2.6.97(3): 完成行要算总耗时, 用本次时钟的起点回推 786 秒(对齐 2026-10-20 实盘那一轮)
    g.dl_t0 = clock.t - 786.0
    ns = {
        'G': g,
        'time': clock,
        'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
        'save_state': lambda: None,
        'DOWNLOAD_CHUNK': 400,
        'DOWNLOAD_TIME_BUDGET_SEC': budget,
        '_api': lambda fn, *a, **kw: fn(*a, **kw),
        '_f': lambda x: float(x or 0),
    }
    if not drop_api:
        ns['download_history_data'] = _download
    exec(compile(DL_SRC, '<dl>', 'exec'), ns)
    ns['_run']()
    return g, logs, calls


# A) 瞬时接口: 8 秒预算永远不到 -> 一轮应当把 5226 只全部下完(切 2000/2000/1226 三块)
g, lg, cl = run_dl(5226, budget=8.0, step=0.0)
chk('T2.1 瞬时接口一轮到底(5226 只)', g.dl_i == 5226 and len(cl) == 5226,
    'dl_i=%d calls=%d' % (g.dl_i, len(cl)))
chk('T2.2 单块=2000(块x5 生效)', g.universe.slices[:3] == [2000, 2000, 1226],
    str(g.universe.slices))
chk('T2.3 下完进阶段2并落盘', g.dl_phase == 2 and g.state.get('last_dl_date') == '20261020',
    'phase=%s last=%s' % (g.dl_phase, g.state.get('last_dl_date')))
chk('T2.4 终值进度行只打一次且是 5226',
    sum(1 for x in lg if x.startswith('下载进度 5226 / 5226')) == 1
    and lg[-1].startswith('下载进度 5226 / 5226'), repr(lg))
chk('T2.4b 完成行带耗时与均速(V2.6.97(3))',
    '耗时786秒' in lg[-1] and '均速6.6只/秒' in lg[-1], repr(lg[-1:]))

# B) 慢接口(每只 0.01 秒, 预算 0.05 秒): 一轮只推进几只就应让出, 且 phase 仍 1
g, lg, cl = run_dl(5226, budget=0.05, step=0.01)
chk('T2.5 预算用完就让出(不再固定 400 只/轮)', 1 <= g.dl_i <= 12 and g.dl_phase == 1,
    'dl_i=%d phase=%s calls=%d' % (g.dl_i, g.dl_phase, len(cl)))
chk('T2.6 让出时进度行照打(跨桶首轮)',
    any(x.startswith('下载进度') for x in lg), repr(lg))
_progress = g.dl_i

# C) 下一轮从上次断点续下, 总进度前进
g2, lg2, cl2 = run_dl(5226, budget=0.05, step=0.01, dl_i=_progress)
chk('T2.7 下一轮从断点续下', g2.dl_i > _progress,
    '%d -> %d' % (_progress, g2.dl_i))

# D) 单只即超预算: 必须至少推进一只, 不能死循环
g, lg, cl = run_dl(5226, budget=8.0, step=10.0)
chk('T2.8 单只即超预算也推进一只(防死循环)', g.dl_i == 1 and g.dl_phase == 1,
    'dl_i=%d phase=%s calls=%d' % (g.dl_i, g.dl_phase, len(cl)))

# E) no_download: 首轮应打提示、跳过下载、直接进阶段2
g, lg, cl = run_dl(5226, budget=8.0, step=0.0, drop_api=True)
chk('T2.9 无接口时打提示并跳过下载',
    g.no_download and g.dl_phase == 2 and g.dl_i == 5226
    and any('本QMT无download_history_data接口' in x for x in lg),
    'no_dl=%s phase=%s dl_i=%d' % (g.no_download, g.dl_phase, g.dl_i))

# F) 预算关闭(0=不限)时保持旧行为: 一轮只下一块
g, lg, cl = run_dl(5226, budget=0.0, step=0.0)
chk('T2.10 预算=0 时一轮只下一块(不长时间占用轮询线程)',
    g.dl_i == 2000 and g.dl_phase == 1, 'dl_i=%d' % g.dl_i)

# ================================================================ T3 情绪推迟闸门
print('=== T3 情绪推迟闸门(真跑 sent_daily_refresh) ===')
_s0 = FULL.index('def sent_daily_refresh():')
_s1 = FULL.index('def _sent_reset_ready(why):')
SENT_SRC = FULL[_s0:_s1]


def make_sent(dl_phase):
    state = {'last_fetch_date': '', 'last_try_ts': 0.0}
    got = {'fetch': 0, 'logs': []}
    g = FakeG(10)
    g.dl_phase = dl_phase
    clock = FakeClock()
    ns = {
        'G': g,
        'time': clock,
        'SENT_STATE': state,
        'SENT_RETRY_SEC': 300,
        '_SENTIMENT_ON': True,
        '_sent_today': lambda: '20261020',
        '_sent_wlog': lambda s: got['logs'].append(s),
        'sent_fetch_all_data': lambda: got.__setitem__('fetch', got['fetch'] + 1),
    }
    exec(compile(SENT_SRC, '<sent>', 'exec'), ns)
    return ns['sent_daily_refresh'], state, got, clock


_NA = u'\u65e5\u5386'   # 占位, 不参与断言

fn, st, got, clk = make_sent(1)
clk.t = 1000.0
fn()
chk('T3.1 下载中不发起取数', got['fetch'] == 0, 'fetch=%d' % got['fetch'])
chk('T3.2 下载中首次推迟打一条说明', len(got['logs']) == 1
    and u'下载进行中' in got['logs'][0] and u'保持中性' in got['logs'][0], repr(got['logs']))
chk('T3.3 推迟起点已记录', abs((st.get('dl_wait_ts') or 0) - 1000.0) < 0.5,
    str(st.get('dl_wait_ts')))
chk('T3.4 推迟时不写 last_try_ts(不被 300 秒节流卡死)',
    (st.get('last_try_ts') or 0) == 0.0, str(st.get('last_try_ts')))

clk.t = 1100.0
fn()
chk('T3.5 300 秒内不重复刷日志', len(got['logs']) == 1 and got['fetch'] == 0,
    'logs=%d' % len(got['logs']))

clk.t = 1400.0
fn()
chk('T3.6 满 300 秒再提醒一次', len(got['logs']) == 2 and got['fetch'] == 0,
    'logs=%d' % len(got['logs']))

clk.t = 2900.0
fn()
chk('T3.7 推迟满 30 分钟强制发起并告警',
    got['fetch'] == 1 and any(u'不再等它' in x for x in got['logs']),
    'fetch=%d logs=%s' % (got['fetch'], got['logs'][-1:]))

clk.t = 2950.0
fn()
chk('T3.8 强制发起后回到正常节流', got['fetch'] == 1, 'fetch=%d' % got['fetch'])

fn2, st2, got2, clk2 = make_sent(0)
clk2.t = 1000.0
fn2()
chk('T3.9 下载结束(phase=0)恢复发起', got2['fetch'] == 1, 'fetch=%d' % got2['fetch'])
chk('T3.10 不在下载中时清零推迟起点', (st2.get('dl_wait_ts') or 0) == 0.0,
    str(st2.get('dl_wait_ts')))

fn3, st3, got3, clk3 = make_sent(2)
clk3.t = 1000.0
fn3()
chk('T3.11 阶段2(待加载)不推情绪', got3['fetch'] == 1, 'phase=2 取数=%d' % got3['fetch'])

# ================================================================ T4 预算命中门槛
print('=== T4 预算命中门槛(真跑 _sent_apply_rows 判定段) ===')
_a0 = FULL.index("        _min_cov = 0.98 if _cov.get('budget_hit') else SENT_COVERAGE_MIN")
_a1 = FULL.index('        if not rows:', _a0)
APPLY_SRC = 'def _run(_cov, _ratio):\n' + textwrap.indent(
    textwrap.dedent(FULL[_a0:_a1]), '    ')
chk('T4.0 取数侧也记 budget_hit 进 cover',
    "_cov['budget_hit'] = bool(_budget_hit)" in FULL
    and '_min_cov = 0.98 if _budget_hit else SENT_COVERAGE_MIN' in FULL)


def run_apply(cov, ratio):
    used = {'why': None}

    def _use(why):
        used['why'] = why

    ns = {'SENT_COVERAGE_MIN': 0.90, '_sent_use_last_good': _use}
    exec(compile(APPLY_SRC, '<apply>', 'exec'), ns)
    ns['_run'](cov, ratio)
    return used['why']


_cov_bh = {'req': 5226, 'ok': 4926, 'fail': 300, 'retry': 0, 'budget_hit': True}
_cov_no = dict(_cov_bh)
_cov_no['budget_hit'] = False
chk('T4.1 预算命中 + 94.3% -> 拒绝(门槛 98%)',
    run_apply(_cov_bh, 4926.0 / 5226.0) is not None
    and u'98%' in run_apply(_cov_bh, 4926.0 / 5226.0),
    repr(run_apply(_cov_bh, 4926.0 / 5226.0))[:90])
chk('T4.2 预算命中 + 99.5% -> 采用',
    run_apply(_cov_bh, 0.995) is None, repr(run_apply(_cov_bh, 0.995)))
chk('T4.3 未命中预算 + 94.3% -> 仍采用(保持原行为)',
    run_apply(_cov_no, 4926.0 / 5226.0) is None, repr(run_apply(_cov_no, 4926.0 / 5226.0)))
chk('T4.4 未命中预算 + 85% -> 仍按 90% 拒绝',
    run_apply(_cov_no, 0.85) is not None and u'90%' in run_apply(_cov_no, 0.85),
    repr(run_apply(_cov_no, 0.85))[:90])
chk('T4.5 cover 缺 budget_hit 键不炸', run_apply({'req': 100, 'ok': 50}, 0.50) is not None)

# ================================================================ T5 铁律与指纹
print('=== T5 铁律与指纹 ===')


def _no_head(t):
    return '\n'.join(l for l in t.replace('\r\n', '\n').split('\n')
                     if not l.startswith(u'版本号: '))


_NH = _no_head(SRC)
chk('T5.1 正文 stop_order 0 次', _NH.count('stop_order') == 0, str(_NH.count('stop_order')))
chk('T5.2 NEVER_STOP_LOSS 未动', 'NEVER_STOP_LOSS = True' in SRC)
chk('T5.3 threading.Thread 仍1处', _NH.count('threading.Thread(') == 1,
    str(_NH.count('threading.Thread(')))
chk('T5.4 _api( 仍52次', SRC.count('_api(') == 52, str(SRC.count('_api(')))

try:
    _ns = {'__name__': 'fp_probe'}
    exec(compile(SRC, P, 'exec'), _ns)
    _fp = _ns['param_fingerprint']()
    if not isinstance(_fp, str):
        _fp = str(_fp[0] if isinstance(_fp, (tuple, list)) else _fp)
except Exception as _e:
    _fp = 'ERR:%s' % _e
chk('T5.5 参数指纹仍 8a4ab7e8', _fp == '8a4ab7e8', 'got=' + _fp)

print('')
print('========== %d PASS / %d FAIL ==========' % (len(PASS), len(FAIL)))
if FAIL:
    for x in FAIL:
        print('  FAILED:', x)
    raise SystemExit(1)
print('ALL GREEN')
