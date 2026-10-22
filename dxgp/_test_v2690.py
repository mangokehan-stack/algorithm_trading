# -*- coding: utf-8 -*-
"""V2.6.90 专项单测(独立执行, 不依赖 QMT 环境)

覆盖用户 2026-10-19 23:04 回"剩余三项也改一下"的三项:
  T1 整体不可用熔断 —— 接口全挂: 18 批 x 拆批重试应被 3 批后截断, 不是跑满 576 次
  T2 部分可用不误杀 —— 首批成功则照常走覆盖率判定, 绝不提前放弃
  T3 取数总预算     —— 主循环在预算处收尾, 带已取到部分退出
  T4 跳过日志带时长 —— 323 秒与 400 秒两种文案, 以及"锁不可用"分支
  T5 零成功也写明细 —— 不再出现"失败0只 + 覆盖率0%"
  T6 参数未动      —— 模块级大写常量集合与参数指纹必须与 V2.6.89 完全一致

设计原则(延续 _test_v2688/v2689): 从母版源码里"抽"真实 _sent_fetch_sync 来跑,
  只把 _BUDGET_SEC 按用例缩小, 不重写任何判据 —— 否则母版改了、测试还按老逻辑算,
  会出现"测试全绿但线上错"的假安全。
"""
import ast
import contextlib
import io
import os
import re
import sys
import threading
import time
from types import SimpleNamespace

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
BASE = r'E:\桌面\666666\dxgp\_baseline\V2.6.89.py'
SRC = io.open(P, 'r', encoding='gbk', newline='').read()
LINES = SRC.split('\r\n')

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


def load_ns(path):
    """exec 母版/基线, 得到与 QMT 同口径的运行时命名空间"""
    src = io.open(path, 'r', encoding='gbk', newline='').read()
    ns = {'__file__': os.path.abspath(path), '__name__': 'fp_probe'}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(src.replace('\r\n', '\n'), path, 'exec'), ns)
    return ns


STOCKS = ['%06d.SZ' % (i + 1) for i in range(900)]


class FakeC(object):
    """假 QMT 行情接口; mode 控制失败形态"""

    def __init__(self, mode='allfail', sleep=0.0):
        self.mode = mode
        self.sleep = sleep
        self.calls = 0

    def get_stock_list_in_sector(self, name, *a):
        return list(STOCKS)

    def get_market_data_ex(self, fields, codes, period, start, end, cnt, fq, a, b):
        self.calls += 1
        if self.sleep:
            time.sleep(self.sleep)
        if self.mode == 'allfail':
            raise RuntimeError('接口超时无响应')
        if self.mode == 'first_ok' and self.calls > 1:
            raise RuntimeError('接口超时无响应')
        out = {}
        for c in codes:
            out[c] = {'20261016': {'close': 11.0, 'preClose': 10.0}}
        return out


LOGS = []


def run_sync(mode='allfail', budget=None, sleep=0.0, ns=None):
    """跑一次真实 _sent_fetch_sync; budget 非 None 时按该值替换局部常量"""
    del LOGS[:]
    _ns = ns if ns is not None else load_ns(P)
    c = FakeC(mode, sleep)
    _ns['G'] = SimpleNamespace(C=c, no_download=True)
    _ns['_sent_wlog'] = lambda m: LOGS.append(m)
    _ns['download_history_data'] = lambda *a, **k: None
    _ns['SENT_STATE'].clear()
    body = func_src('_sent_fetch_sync', SRC, LINES)
    if budget is not None:
        assert body.count('_BUDGET_SEC = 180.0') == 1
        body = body.replace('_BUDGET_SEC = 180.0', '_BUDGET_SEC = %.3f' % budget)
    exec(compile(body, '<sync>', 'exec'), _ns)
    r = _ns['_sent_fetch_sync']()
    return r, c, _ns


# ============================================================
# T1 整体不可用熔断
# ============================================================
print('=' * 60)
print('T1 整体不可用熔断(接口全挂)')
r, c, ns1 = run_sync('allfail')
cov = ns1['SENT_STATE'].get('cover') or {}
txt = ' | '.join(LOGS)

# 单批 300 只失败 -> 1 + 3x(1 + 4) = 16 次调用; 3 批后熔断 -> 48 次
chk('T1 熔断后总调用次数=48(3批x16)', c.calls == 48, 'actual=%d' % c.calls)
chk('T1 远小于旧版最坏 576 次', c.calls < 100, 'actual=%d' % c.calls)
chk('T1 熔断告警已打出', '判定行情接口整体不可用' in txt)
chk('T1 熔断后不再进第二轮全字段重试',
    '改用全字段重试' not in txt, txt[:120])
chk('T1 覆盖率记 0', cov.get('ratio') == 0.0, str(cov.get('ratio')))
chk('T1 请求只数=900', cov.get('req') == 900, str(cov.get('req')))
chk('T1 零成功时失败数已写入(非 0)', cov.get('fail') == 900, str(cov.get('fail')))
# 每批 300 失败: depth0 拆一次 + 3 个 100 各拆一次 = 4 次; 3 批 = 12
chk('T1 拆分重试次数如实=12(3批x4)', cov.get('retry') == 12, str(cov.get('retry')))
chk('T1 字段口径仍是 close/preClose', cov.get('fields_all') is False)
chk('T1 失败样本被记录(最多3条)', len(cov.get('samples') or []) == 3,
    str(len(cov.get('samples') or [])))
chk('T1 返回 None(上游走沿用/中性)', r is None)
# 关键: 熔断判据不能是"只要有一批失败就放弃"
chk('T1 无"部分可用"误报', '部分' not in txt)

# ============================================================
# T2 部分可用不得误杀
# ============================================================
print('=' * 60)
print('T2 部分可用不误杀(首批成功, 后续全失败)')
r2, c2, ns2 = run_sync('first_ok')
cov2 = ns2['SENT_STATE'].get('cover') or {}
txt2 = ' | '.join(LOGS)
chk('T2 未触发熔断', '判定行情接口整体不可用' not in txt2, txt2[:120])
chk('T2 首批 300 只记为成功', cov2.get('ok') == 300, str(cov2.get('ok')))
chk('T2 后续 600 只记为失败', cov2.get('fail') == 600, str(cov2.get('fail')))
chk('T2 覆盖率如实=33.3%', abs((cov2.get('ratio') or 0) - 0.3333) < 0.001,
    str(cov2.get('ratio')))
# first_ok: 第1批1次 + 第2批16次 + 第3批16次 + 上证指数1次 = 34
chk('T2 调用次数=34(3批33次+指数1次)', c2.calls == 34, 'actual=%d' % c2.calls)
chk('T2 统计数据非空(未中止整轮)', r2 is not None and len(r2) > 0,
    str(len(r2 or [])))
chk('T2 取数完成日志已打出', '内置通道取数完成' in txt2)
chk('T2 覆盖率不足告警已打出', '行情覆盖率不足' in txt2)

# ============================================================
# T3 取数总预算
# ============================================================
print('=' * 60)
print('T3 取数总预算(每批 0.8s, 预算 1.5s)')
r3, c3, ns3 = run_sync('allok', budget=1.5, sleep=0.8)
cov3 = ns3['SENT_STATE'].get('cover') or {}
txt3 = ' | '.join(LOGS)
chk('T3 触发预算告警', '情绪取数触发总预算' in txt3, txt3[:140])
# 2 批行情(含 sleep) + 1 次上证指数 = 3 次; 第 3 批行情在预算检查处被拦下
chk('T3 只跑完 2 批(第3批前超时)', c3.calls == 3, 'actual=%d' % c3.calls)
chk('T3 第3批300只未被请求', (cov3.get('ok') or 0) == 600, str(cov3.get('ok')))
chk('T3 已取到 600 只带出(不丢弃)',
    (cov3.get('ok') or 0) >= 600, str(cov3.get('ok')))
chk('T3 预算收尾仍产出 rows', r3 is not None and len(r3) > 0)
chk('T3 预算文案含"本轮放弃"', '本轮放弃' in txt3)
chk('T3 未误报熔断', '判定行情接口整体不可用' not in txt3)

# 预算充足时不该有任何"超时"痕迹
r3b, c3b, ns3b = run_sync('allok', budget=180.0)
txt3b = ' | '.join(LOGS)
chk('T3 预算充足时跑满 3 批', c3b.calls == 4, 'actual=%d(3批+指数1次)' % c3b.calls)
chk('T3 预算充足时无预算告警', '情绪取数触发总预算' not in txt3b)

# ============================================================
# T4 跳过日志带已运行时长
# ============================================================
print('=' * 60)
print('T4 跳过日志带已运行时长')


def run_skip(age, lock_none=False):
    del LOGS[:]
    ns = load_ns(P)
    ns['_sent_wlog'] = lambda m: LOGS.append(m)
    if lock_none:
        def _boom():
            raise RuntimeError('无法创建锁')
        ns['threading'] = SimpleNamespace(Lock=_boom)
        ns['_SENT_FETCH_LOCK'] = None
    else:
        lk = threading.Lock()
        lk.acquire()          # 模拟"已有线程持锁在跑"
        ns['_SENT_FETCH_LOCK'] = lk
    ns['SENT_STATE']['fetch_start_ts'] = time.time() - age
    ns['sent_fetch_all_data']()
    return ' | '.join(LOGS)


t323 = run_skip(323)
chk('T4 323秒 -> 打出已运行323秒', '已运行323秒' in t323, t323[:140])
chk('T4 323秒 -> 不喊卡死(未超2倍预算)', '疑似卡死' not in t323)

t400 = run_skip(400)
chk('T4 400秒 -> 提示疑似卡死', '疑似卡死' in t400, t400[:160])
chk('T4 400秒 -> 文案仍说明中性不阻断', '中性' in t400)

tnone = run_skip(10, lock_none=True)
chk('T4 锁不可用 -> 独立文案', '情绪取数锁不可用' in tnone, tnone[:140])
chk('T4 旧合并文案已消失', '已在运行或锁不可用' not in tnone)

tnofield = run_skip(0)
chk('T4 fetch_start_ts 缺失时不崩且为0秒', '已运行0秒' in tnofield, tnofield[:140])

# ============================================================
# T5 fetch_start_ts 写入点
# ============================================================
print('=' * 60)
print('T5 取数起点写入')
_fa_src = func_src('sent_fetch_all_data', SRC, LINES)
chk('T5 起点写入在发起线程处', '_th.start()' in _fa_src
    and _fa_src.index('_th.start()') < _fa_src.index("SENT_STATE['fetch_start_ts']"))
chk('T5 起点写入在 fetching=True 之后',
    _fa_src.index("SENT_STATE['fetching'] = True") <
    _fa_src.index("SENT_STATE['fetch_start_ts']"))
chk('T5 起点不写入状态文件(仅 SENT_STATE)',
    'fetch_start_ts' not in func_src('save_state', SRC, LINES)
    if 'def save_state(' in SRC else True)

# ============================================================
# T6 参数未动 + 铁律未动
# ============================================================
print('=' * 60)
print('T6 参数指纹与铁律')
ns89 = load_ns(BASE)
ns90 = load_ns(P)
k89 = set(ns89['_fp_keys']())
k90 = set(ns90['_fp_keys']())
chk('T6 模块级大写常量集合与 V2.6.89 完全一致', k89 == k90,
    'only90=%s only89=%s' % (sorted(k90 - k89), sorted(k89 - k90)))
chk('T6 常量个数一致', len(k89) == len(k90), '%d vs %d' % (len(k89), len(k90)))
p89 = ns89['param_fingerprint']()[0]
p90 = ns90['param_fingerprint']()[0]
chk('T6 参数指纹不变', p89 == p90, '%s -> %s' % (p89, p90))
c89 = ns89['code_fingerprint']()[0]
c90 = ns90['code_fingerprint']()[0]
chk('T6 版本指纹已变化', c89 != c90, '%s -> %s' % (c89, c90))
_v90 = str(ns90.get('VERSION') or '')
_m90 = re.match(r'V(\d+)\.(\d+)\.(\d+)$', _v90)
chk('T6 VERSION 不早于 V2.6.90',
    bool(_m90) and tuple(int(x) for x in _m90.groups()) >= (2, 6, 90), _v90)
_body = '\r\n'.join(l for l in LINES if not l.startswith('版本号: '))
chk('T6 stop_order 代码区仍为 0(铁律)', _body.count('stop_order') == 0,
    'actual=%d' % _body.count('stop_order'))
chk('T6 NEVER_STOP_LOSS=True 未动', 'NEVER_STOP_LOSS = True' in _body)
_ctx = {k: v for k, v in ns90.items() if isinstance(v, (int, float))}
chk('T6 情绪取数不含任何下单调用',
    all(x not in func_src('_sent_fetch_sync', SRC, LINES)
        for x in ('passorder', 'order_target', 'cancel_order')))

# ============================================================
print('=' * 60)
print('%d/%d PASS' % (len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print('FAILED:')
    for f in FAIL:
        print('  - %s' % f)
    sys.exit(1)
print('ALL PASS')
