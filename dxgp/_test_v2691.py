# -*- coding: utf-8 -*-
"""V2.6.91 专项单测(独立执行, 不依赖 QMT 环境)

覆盖用户 2026-10-19 23:24 回"改"的三项:
  T1 世代文件        —— 启动宣告写入内容/原子替换/按账号隔离
  T2 旧代判定        —— 三个条件缺一不可(自己/更新/新鲜), 四种反例必须放行
  T3 取数入口自愈    —— 旧代线程直接退出: 0 次接口调用, 不写 cover 不返回 rows
  T4 取数中途自愈    —— 第 1 批后才发现新代接管, 立刻退出而不是带半份数据跑完
  T5 完成行耗时      —— 日志带"耗时N秒", 且数值与实际耗时可对上
  T6 心跳节拍        —— 30 秒间隔必须落一拍; 与 V2.6.90 基线做同场景对照(旧版跳过)
  T7 告警分档未被节拍拖累 —— 40 秒前的同伴仍判 live(告警), 60 秒判 stale(提示)

设计原则(延续 _test_v2688/v2689/v2690): 从母版源码里"抽"真实函数来跑,
  不重写任何判据; 否定用例一律与 _baseline/V2.6.90.py 同场景对照, 证明差异确实来自本次改动。
"""
import ast
import contextlib
import io
import json
import os
import shutil
import tempfile
import time
from types import SimpleNamespace

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
BASE = r'E:\桌面\666666\dxgp\_baseline\V2.6.90.py'
SRC = io.open(P, 'r', encoding='gbk', newline='').read()
LINES = SRC.split('\r\n')
ACC = 'TESTACC'

PASS = []
FAIL = []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))


def func_src(name, src=None, lines=None):
    _src = src if src is not None else SRC
    _lines = lines if lines is not None else LINES
    tree = ast.parse(_src)
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return '\n'.join(_lines[n.lineno - 1:n.end_lineno])
    raise AssertionError('函数未找到: %s' % name)


def load_ns(path, tmpdir):
    """exec 整份母版拿运行时命名空间; __file__ 指到临时目录, 让 _join_base 落到沙箱里"""
    src = io.open(path, 'r', encoding='gbk', newline='').read()
    ns = {'__file__': os.path.join(tmpdir, 'fake_strategy.py'), '__name__': 'v2691_probe'}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(src.replace('\r\n', '\n'), path, 'exec'), ns)
    ns['__file__'] = os.path.join(tmpdir, 'fake_strategy.py')
    ns['G'] = SimpleNamespace(accid=ACC)
    return ns


TMP = tempfile.mkdtemp(prefix='v2691_')


def gen_file(tmpdir):
    return os.path.join(tmpdir, 'zt_shrink_gen_%s.json' % ACC)


def hb_file(tmpdir, pid):
    return os.path.join(tmpdir, 'zt_shrink_heartbeat_%s_%d.json' % (ACC, pid))


def write_json(p, obj):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f)


def read_json(p):
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============================================================
# T1 世代文件
# ============================================================
print('=' * 60)
print('T1 世代文件写入')
d1 = os.path.join(TMP, 't1')
os.makedirs(d1)
ns1 = load_ns(P, d1)
g1 = ns1['gen_announce']()
p1 = gen_file(d1)
chk('T1 世代文件已生成', os.path.exists(p1), p1)
o1 = read_json(p1)
chk('T1 gen/pid/ts/ver 四个字段齐备',
    set(o1.keys()) == {'gen', 'pid', 'ts', 'ver'}, str(o1))
chk('T1 gen 与 ts 相同(同一时刻)', abs(o1['gen'] - o1['ts']) < 1e-6)
chk('T1 gen 等于返回值', abs(o1['gen'] - g1) < 1e-6)
chk('T1 pid 是本进程', o1['pid'] == os.getpid(), str(o1['pid']))
chk('T1 ver 是当前版本', o1['ver'] == ns1['VERSION'], o1['ver'])
chk('T1 临时文件已清掉(原子替换)', not os.path.exists(p1 + '.tmp'))

ns1b = load_ns(P, d1)
ns1b['G'] = SimpleNamespace(accid='OTHERACC')
ns1b['gen_announce']()
chk('T1 世代文件按账号隔离',
    os.path.exists(os.path.join(d1, 'zt_shrink_gen_OTHERACC.json')))

# 写失败不阻断: 把目录换成不可写路径
ns1c = load_ns(P, os.path.join(TMP, 'no_such_dir_x'))
try:
    _r = ns1c['gen_announce']()
    _err_ok = (_r == 0.0)
except Exception as _e:
    _err_ok = False
chk('T1 写失败返回 0 且不抛异常', _err_ok, str(_r))


# ============================================================
# T2 旧代判定(三条件)
# ============================================================
print('=' * 60)
print('T2 旧代判定三条件')
d2 = os.path.join(TMP, 't2')
os.makedirs(d2)
ns2 = load_ns(P, d2)
sup2 = ns2['_gen_superseded']
ns2['gen_announce']()
chk('T2 刚宣告完自己不算旧代', sup2() is False)

mine = read_json(gen_file(d2))['gen']
# a) 世代文件更新 + 该代心跳新鲜  -> True
write_json(gen_file(d2), {'gen': mine + 100.0, 'pid': os.getpid(),
                          'ts': mine + 100.0, 'ver': 'V2.6.91'})
write_json(hb_file(d2, os.getpid()), {'pid': os.getpid(), 'ts': time.time(),
                                      'acc': ACC, 'ver': 'V2.6.91', 'boot': time.time()})
chk('T2 更新一代+心跳新鲜 -> 判为旧代', sup2() is True)

# b) 心跳过期 -> False(否则"新代启动又退出"会永久压制本代)
write_json(hb_file(d2, os.getpid()), {'pid': os.getpid(),
                                      'ts': time.time() - (ns2['HEARTBEAT_STALE_SEC'] + 60),
                                      'acc': ACC, 'ver': 'V2.6.91', 'boot': 0.0})
chk('T2 更新一代但心跳过期 -> 放行(不永久压制)', sup2() is False)

# c) 该 pid 根本没有心跳文件 -> False
os.remove(hb_file(d2, os.getpid()))
chk('T2 更新一代但无心跳文件 -> 放行', sup2() is False)

# d) 世代文件里的 gen 更旧 -> False
write_json(gen_file(d2), {'gen': mine - 100.0, 'pid': os.getpid(),
                          'ts': mine - 100.0, 'ver': 'V2.6.91'})
write_json(hb_file(d2, os.getpid()), {'pid': os.getpid(), 'ts': time.time(),
                                      'acc': ACC, 'ver': 'V2.6.91', 'boot': 0.0})
chk('T2 世代文件更旧 -> 放行', sup2() is False)

# e) 世代文件损坏 -> False
open(gen_file(d2), 'w').write('{not json')
chk('T2 世代文件损坏 -> 放行(按无法判定)', sup2() is False)

# f) 从未宣告(id=0) -> False
ns2f = load_ns(P, d2)
chk('T2 本代未宣告 -> 一律放行', ns2f['_gen_superseded']() is False)


# ============================================================
# T3/T4 取数侧: 入口与中途自愈
# ============================================================
print('=' * 60)
print('T3 取数入口自愈')
STOCKS = ['%06d.SZ' % (i + 1) for i in range(900)]
LOGS = []


class FakeC(object):
    def __init__(self, flip=False):
        self.calls = 0
        self.flip = flip
        self.flip_dir = None
        self.flip_to = None

    def get_stock_list_in_sector(self, name, *a):
        return list(STOCKS)

    def get_market_data_ex(self, fields, codes, period, start, end, cnt, fq, a, b):
        self.calls += 1
        if self.flip and self.calls == 1:
            # 第 1 批跑完, 新代接管: 写一份更新的世代 + 新鲜心跳
            write_json(self.flip_to, {'gen': time.time() + 50, 'pid': os.getpid(),
                                      'ts': time.time() + 50, 'ver': 'V2.6.91'})
            write_json(hb_file(self.flip_dir, os.getpid()),
                       {'pid': os.getpid(), 'ts': time.time(), 'acc': ACC,
                        'ver': 'V2.6.91', 'boot': 0.0})
        out = {}
        for c in codes:
            out[c] = {'20261016': {'close': 11.0, 'preClose': 10.0}}
        return out


def run_sync(ns, c, with_newer_gen):
    del LOGS[:]
    ns['G'] = SimpleNamespace(C=c, no_download=True, accid=ACC)
    ns['_sent_wlog'] = lambda m: LOGS.append(m)
    ns['download_history_data'] = lambda *a, **k: None
    ns['SENT_STATE'].clear()
    if with_newer_gen:
        write_json(gen_file(os.path.dirname(ns['__file__'])),
                   {'gen': time.time() + 50, 'pid': os.getpid(),
                    'ts': time.time() + 50, 'ver': 'V2.6.91'})
        write_json(hb_file(os.path.dirname(ns['__file__']), os.getpid()),
                   {'pid': os.getpid(), 'ts': time.time(), 'acc': ACC,
                    'ver': 'V2.6.91', 'boot': 0.0})
    exec(compile(func_src('_sent_fetch_sync'), '<sync>', 'exec'), ns)
    r = ns['_sent_fetch_sync']()
    return r


d3 = os.path.join(TMP, 't3')
os.makedirs(d3)
ns3 = load_ns(P, d3)
ns3['gen_announce']()
c3 = FakeC()
r3 = run_sync(ns3, c3, True)
chk('T3 旧代线程直接返回 None', r3 is None)
chk('T3 旧代线程 0 次接口调用(连股票列表都不拉)', c3.calls == 0, 'calls=%d' % c3.calls)
chk('T3 日志说明"不写结果, 不覆盖状态"',
    any('旧代残留' in m and '不覆盖状态' in m for m in LOGS), str(LOGS)[:140])
chk('T3 未写 SENT_STATE[cover]', 'cover' not in ns3['SENT_STATE'])

# 反例: 新代心跳过期 -> 必须放行并正常取数
d3b = os.path.join(TMP, 't3b')
os.makedirs(d3b)
ns3b = load_ns(P, d3b)
ns3b['gen_announce']()
write_json(gen_file(d3b), {'gen': time.time() + 50, 'pid': os.getpid(),
                           'ts': time.time() + 50, 'ver': 'V2.6.91'})
write_json(hb_file(d3b, os.getpid()),
           {'pid': os.getpid(), 'ts': time.time() - 600, 'acc': ACC,
            'ver': 'V2.6.91', 'boot': 0.0})
c3b = FakeC()
r3b = run_sync(ns3b, c3b, False)
# 900 只 = 3 批行情 + 1 次上证指数成交额, 共 4 次
chk('T3 新代心跳已过期 -> 照常取数(不压制)', r3b is not None and c3b.calls == 4,
    'calls=%d rows=%s' % (c3b.calls, 'None' if r3b is None else len(r3b)))
chk('T3 正常路径写入了 cover', 'cover' in ns3b['SENT_STATE'])

print('=' * 60)
print('T4 取数中途自愈')
d4 = os.path.join(TMP, 't4')
os.makedirs(d4)
ns4 = load_ns(P, d4)
ns4['gen_announce']()
c4 = FakeC(flip=True)
c4.flip_dir = d4
c4.flip_to = gen_file(d4)
r4 = run_sync(ns4, c4, False)
chk('T4 第1批后发现新代 -> 返回 None', r4 is None)
chk('T4 第1批后立即停手(只 1 次调用, 不是跑满 3 批)', c4.calls == 1, 'calls=%d' % c4.calls)
chk('T4 日志明说"提前退出"', any('提前退出' in m for m in LOGS), str(LOGS)[-1:])
chk('T4 带半份数据也不返回 rows', 'cover' not in ns4['SENT_STATE'])


# ============================================================
# T5 完成行耗时
# ============================================================
print('=' * 60)
print('T5 完成行带耗时')
d5 = os.path.join(TMP, 't5')
os.makedirs(d5)
ns5 = load_ns(P, d5)
ns5['gen_announce']()


class SlowC(FakeC):
    def get_market_data_ex(self, fields, codes, period, start, end, cnt, fq, a, b):
        time.sleep(0.05)
        return FakeC.get_market_data_ex(self, fields, codes, period, start, end, cnt, fq, a, b)


c5 = SlowC()
t5a = time.time()
r5 = run_sync(ns5, c5, False)
t5b = time.time() - t5a
done = [m for m in LOGS if '内置通道取数完成' in m]
chk('T5 完成行存在', len(done) == 1, str(len(done)))
chk('T5 完成行带"耗时N秒"', bool(done) and '耗时' in done[0] and '秒' in done[0], done[0][:130] if done else '')
if done:
    import re as _re
    m5 = _re.search(r'耗时(\d+)秒', done[0])
    chk('T5 耗时数值为正且不超过实测', bool(m5) and 0 <= int(m5.group(1)) <= int(t5b) + 1,
        'log=%s wall=%.2f' % (m5.group(1) if m5 else '?', t5b))


# ============================================================
# T6 心跳节拍(与 V2.6.90 基线同场景对照)
# ============================================================
print('=' * 60)
print('T6 心跳节拍')


class Clock(object):
    def __init__(self, t):
        self.t = t

    def time(self):
        return self.t


def hb_ts(path):
    try:
        return read_json(path)['ts']
    except Exception:
        return None


def tick_seq(path, gap):
    """宣告后按 gap 秒连打两拍, 返回第二拍写入的 ts(None=没写)"""
    d = os.path.join(TMP, 't6_%s_%s' % (os.path.basename(path)[:6], str(gap).replace('.', '_')))
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    ns = load_ns(path, d)
    ns['G'] = SimpleNamespace(accid=ACC)
    ns['log'] = lambda m: None
    clk = Clock(1792400000.0)
    ns['time'] = clk
    ns['heartbeat_tick'](force=True)
    first = hb_ts(hb_file(d, os.getpid()))
    clk.t = 1792400000.0 + gap
    ns['heartbeat_tick']()
    second = hb_ts(hb_file(d, os.getpid()))
    return first, second


f_new, s_new = tick_seq(P, 30.0)
chk('T6 新版: 30 秒间隔落第二拍', s_new == 1792400030.0, 'first=%s second=%s' % (f_new, s_new))
f_new2, s_new2 = tick_seq(P, 29.5)
chk('T6 新版: 29.5 秒也落拍(不再卡边界)', s_new2 == 1792400029.5,
    'second=%s' % s_new2)
f_old2, s_old2 = tick_seq(BASE, 29.5)
chk('T6 基线(V2.6.90) 29.5 秒被跳过(证明改动有效)', s_old2 == f_old2,
    'second=%s' % s_old2)
# 说明: 恰好 30.000 秒时基线也会落拍(比较是 >=, 差值为 0 就过), 线上 60 秒节拍来自
# timer 回调的亚秒抖动(实测落在 29.x)。这条断言把这个边界明确写下来, 免得日后
# 有人拿"30 秒基线也写"来质疑改动无必要。
f_old3, s_old3 = tick_seq(BASE, 30.0)
chk('T6 基线在恰好 30.000 秒时才落拍(边界极窄)', s_old3 == 1792400030.0,
    'second=%s' % s_old3)


# ============================================================
# T7 告警分档在 30 秒节拍下仍正确
# ============================================================
print('=' * 60)
print('T7 告警分档')
PEER = 99999


def kind_of(age):
    d = os.path.join(TMP, 't7_%d' % int(age))
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    ns = load_ns(P, d)
    ns['G'] = SimpleNamespace(accid=ACC)
    ns['log'] = lambda m: None
    clk = Clock(1792500000.0)
    ns['time'] = clk
    ns['heartbeat_tick'](force=True)
    write_json(hb_file(d, PEER), {'pid': PEER, 'ts': 1792500000.0 - age,
                                  'acc': ACC, 'ver': 'V2.6.91', 'boot': 0.0})
    ns['heartbeat_tick'](force=True)
    return ns['_HB_STATE'].get('peer_kind')


chk('T7 40 秒前的心跳 -> live(喊告警)', kind_of(40) == 'live', str(kind_of(40)))
chk('T7 60 秒前的心跳 -> stale(只提示)', kind_of(60) == 'stale', str(kind_of(60)))
chk('T7 100 秒前的心跳 -> stale', kind_of(100) == 'stale', str(kind_of(100)))


# ============================================================
# T8 参数指纹未漂移(模块级大写常量集合与 V2.6.90 完全一致)
# ============================================================
print('=' * 60)
print('T8 参数未动')
dn = os.path.join(TMP, 't8a')
do = os.path.join(TMP, 't8b')
os.makedirs(dn)
os.makedirs(do)
nsn = load_ns(P, dn)
nso = load_ns(BASE, do)
kn = set(nsn['_fp_keys']())
ko = set(nso['_fp_keys']())
chk('T8 大写常量集合完全一致', kn == ko,
    'only_new=%s only_old=%s' % (sorted(kn - ko), sorted(ko - kn)))
_fp_new = nsn['param_fingerprint']()
_fp_old = nso['param_fingerprint']()
chk('T8 参数指纹仍为 8a4ab7e8',
    (_fp_new[0] if isinstance(_fp_new, tuple) else _fp_new) == '8a4ab7e8', str(_fp_new)[:40])
chk('T8 参数指纹与基线完全一致(逐字节)',
    _fp_new[1] == _fp_old[1], '新版/基线 参数串不同' if _fp_new[1] != _fp_old[1] else '')
chk('T8 版本指纹已变(可区分代码改动)',
    nsn['code_fingerprint']()[0] != nso['code_fingerprint']()[0],
    '%s vs %s' % (nso['code_fingerprint']()[0], nsn['code_fingerprint']()[0]))


# ============================================================
print('=' * 60)
print('%d/%d PASS' % (len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print('FAILED: %s' % FAIL)
shutil.rmtree(TMP, ignore_errors=True)
