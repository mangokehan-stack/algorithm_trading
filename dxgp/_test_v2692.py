# -*- coding: utf-8 -*-
"""V2.6.92 专项单测(独立执行, 不依赖 QMT 环境)

覆盖第 6 项(当日重载)与第 7 项(数据源健康):
  T1 首次装载            —— 3 只装入 + 当日锁定 + 记账文件指纹
  T2 节流窗口内不读盘    —— 60 秒内改了文件也不动(守住选股循环 IO 成本)
  T3 节流到期后当日重载  —— 指纹变了立刻重装, 不再等次日/重启(本次核心)
  T4 指纹未变不重装      —— 无"已更新"日志, 返回缓存
  T5 重载遇坏文件        —— 绝不用空表覆盖, 沿用更新前旧表并告警
  T6 数据源失败可见      —— st 源失败必须打出来, 且 pnl_alert 恰一次
  T7 同日不重复告警      —— 第二次装载不再 pnl_alert
  T8 公告覆盖不足提示    —— cover 4天 < 窗口45天 时提示立案/处罚可能漏检
  T9 老格式兼容          —— 清单没有 sources/errors 字段时不告警、不崩

设计原则(延续 _test_v2688~2691): 从母版源码 exec 出真实函数来跑, 不重写判据;
  log / pnl_alert 换成记录器, 逐条断言日志文案, 避免"看着通过实际没提示"。
"""
import contextlib
import datetime
import io
import json
import os
import tempfile
import time
from types import SimpleNamespace

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
ACC = 'TESTACC'
SRC = io.open(P, 'r', encoding='gbk', newline='').read()
TMP = tempfile.mkdtemp(prefix='v2692_')
PATH = os.path.join(TMP, 'zt_shrink_risk_exclude_%s.json' % ACC)

PASS, FAIL = [], []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))


def load_ns():
    ns = {'__file__': os.path.join(TMP, 'fake_strategy.py'), '__name__': 'v2692_probe'}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(SRC.replace('\r\n', '\n'), P, 'exec'), ns)
    ns['G'] = SimpleNamespace(
        accid=ACC, today='20261019', ready=True, C=None,
        risk_ex={}, risk_ex_date='', risk_ex_try_ts=0.0,
        risk_ex_sig=None, risk_ex_stat_ts=0.0, risk_ex_src_warn_date='',
        risk_ex_note_date='', state_broken=False, accid_ok=True)
    ns['_LOGS'] = []
    ns['_ALERTS'] = []
    ns['log'] = lambda *a, **k: ns['_LOGS'].append(' '.join(str(x) for x in a))
    ns['pnl_alert'] = lambda *a, **k: ns['_ALERTS'].append(' '.join(str(x) for x in a))
    return ns


def write_list(stocks, sources=None, errors=None, window=45, asof=None, raw=None):
    if raw is not None:
        io.open(PATH, 'w', encoding='utf-8').write(raw)
    else:
        j = {'schema': 1, 'asof': asof or datetime.date.today().strftime('%Y%m%d'),
             'window_days': window, 'counts': {}, 'total_stocks': len(stocks),
             'stocks': stocks}
        if sources is not None:
            j['sources'] = sources
        if errors is not None:
            j['errors'] = errors
        io.open(PATH, 'w', encoding='utf-8').write(json.dumps(j, ensure_ascii=False))
    _t = time.time() + 10          # 保证 mtime 整秒变化, 指纹可比
    os.utime(PATH, (_t, _t))


def sample(n, tag='lift'):
    d = {}
    for i in range(n):
        d['60000%d.SH' % i] = {'tags': [tag], 'reasons': ['测试原因%d' % i]}
    return d


ns = load_ns()
load = ns['load_risk_exclude']
G = ns['G']

STOCKS = sample(3)
write_list(STOCKS, sources={'st': {'ok': True, 'n': 3}}, errors=[])

# ---------------------------------------------------------------- T1
d = load()
chk('T1 首次装载3只', len(d) == 3, 'got=%d' % len(d))
chk('T1 当日锁定', G.risk_ex_date == '20261019', 'date=%r' % G.risk_ex_date)
chk('T1 记账文件指纹', isinstance(G.risk_ex_sig, tuple) and G.risk_ex_sig[0] == PATH,
    'sig=%r' % (G.risk_ex_sig,))
chk('T1 装载日志正常', any('已装载提前排雷清单3只' in x for x in ns['_LOGS']),
    ns['_LOGS'][:2])

# ---------------------------------------------------------------- T2 节流内
G.risk_ex_stat_ts = time.time()
write_list(dict(list(sample(4).items())), sources={'st': {'ok': True, 'n': 4}}, errors=[])
ns['_LOGS'][:] = []
d = load()
chk('T2 60秒内不重读(仍3只)', len(d) == 3, 'got=%d' % len(d))
chk('T2 无重装日志', not any('清单文件已更新' in x for x in ns['_LOGS']))

# ---------------------------------------------------------------- T3 节流到期重载
G.risk_ex_stat_ts = 0.0
ns['_LOGS'][:] = []
d = load()
chk('T3 指纹变化当日重载为4只', len(d) == 4, 'got=%d' % len(d))
chk('T3 打出"清单文件已更新"', any('清单文件已更新' in x for x in ns['_LOGS']),
    [x for x in ns['_LOGS'] if '更新' in x][:1])
chk('T3 重装后重新锁定当日', G.risk_ex_date == '20261019')

# ---------------------------------------------------------------- T4 指纹未变
G.risk_ex_stat_ts = 0.0
ns['_LOGS'][:] = []
d = load()
chk('T4 指纹未变仍4只', len(d) == 4)
chk('T4 不重复重装', not any('清单文件已更新' in x for x in ns['_LOGS']))

# ---------------------------------------------------------------- T5 坏文件
G.risk_ex_stat_ts = 0.0
write_list(None, raw='{"stocks": {"600000.SH": ')     # 非法 JSON
ns['_LOGS'][:] = []
ns['_ALERTS'][:] = []
d = load()
chk('T5 坏文件不覆盖旧表(仍4只)', len(d) == 4, 'got=%d' % len(d))
chk('T5 明确"沿用更新前旧表"', any('沿用更新前旧表' in x for x in ns['_LOGS']),
    [x for x in ns['_LOGS'] if '沿用' in x][:1])

# ---------------------------------------------------------------- T6 数据源失败
G.risk_ex_stat_ts = 0.0
G.risk_ex_src_warn_date = ''
G.risk_ex = {}          # 让 T6 走一次"首次装载"路径, 便于断言告警
G.risk_ex_date = ''
write_list(sample(5), sources={
    'st': {'ok': False, 'n': 0, 'err': "RemoteDisconnected('Remote end closed')"},
    'lift': {'ok': True, 'n': 5, 'sec': 0.1}},
    errors=["st: RemoteDisconnected('Remote end closed')"])
ns['_LOGS'][:] = []
ns['_ALERTS'][:] = []
d = load()
chk('T6 装载5只', len(d) == 5, 'got=%d' % len(d))
chk('T6 告警写明类别与原因',
    any('1类数据源失败' in x and 'st:' in x and 'RemoteDisconnected' in x for x in ns['_LOGS']),
    [x for x in ns['_LOGS'] if '数据源' in x][:1])
chk('T6 pnl_alert 恰一次', len(ns['_ALERTS']) == 1, 'n=%d' % len(ns['_ALERTS']))

# ---------------------------------------------------------------- T7 同日不重复告警
G.risk_ex = {}
G.risk_ex_date = ''
ns['_ALERTS'][:] = []
d = load()
chk('T7 第二次装载仍5只', len(d) == 5)
chk('T7 不再重复 pnl_alert', len(ns['_ALERTS']) == 0, 'n=%d' % len(ns['_ALERTS']))

# ---------------------------------------------------------------- T8 公告覆盖不足
G.risk_ex = {}
G.risk_ex_date = ''
write_list(sample(2), window=45, sources={
    'st': {'ok': True, 'n': 2},
    'ann': {'ok': True, 'n': 15, 'seen': 2000, 'skip_note': 5,
            'cover_from': '2026-10-17', 'cover_to': '2026-10-20'}}, errors=[])
ns['_LOGS'][:] = []
d = load()
chk('T8 提示未达窗口',
    any('仅覆盖45天窗口的' in x and '2026-10-17' in x for x in ns['_LOGS']),
    [x for x in ns['_LOGS'] if '公告' in x][:1])
# V2.6.97(4b): 夹具里没有 ann 标签 -> ann 计数为 0, 必须走"未采到"分支,
#   绝不能打出"满覆盖约0只, 缺约0只"(那读起来像没有风险)
chk('T8 ann=0 明示未采到(不许说缺约0只)',
    any('ann类0只' in x and '不等于无风险' in x for x in ns['_LOGS'])
    and not any('缺约0只' in x for x in ns['_LOGS']),
    [x for x in ns['_LOGS'] if '公告' in x][:1])

# ---------------------------------------------------------------- T8b ann>0 推算
G.risk_ex = {}
G.risk_ex_date = ''
_mix = {'600000.SH': {'tags': ['st'], 'reasons': ['a']},
        '600001.SH': {'tags': ['ann'], 'reasons': ['b']},
        '600002.SH': {'tags': ['ann'], 'reasons': ['c']}}
write_list(_mix, window=45, sources={
    'st': {'ok': True, 'n': 1},
    'ann': {'ok': True, 'n': 15, 'seen': 2000,
            'cover_from': '2026-10-17', 'cover_to': '2026-10-20'}}, errors=[])
ns['_LOGS'][:] = []
d = load()
chk('T8b ann>0 打同比推算缺口',
    any('同比推算45天满覆盖约' in x and 'ann类2只' in x for x in ns['_LOGS']),
    [x for x in ns['_LOGS'] if '公告' in x][:1])

# ---------------------------------------------------------------- T9 老格式兼容
G.risk_ex = {}
G.risk_ex_date = ''
write_list(sample(2))          # 无 sources/errors
ns['_LOGS'][:] = []
ns['_ALERTS'][:] = []
d = load()
chk('T9 老格式仍装载2只', len(d) == 2)
chk('T9 不误报告警', not any('数据源失败' in x or '生成端报错' in x for x in ns['_LOGS']),
    ns['_LOGS'][:2])

print('\n=== V2.6.92 单测: %d PASS / %d FAIL ===' % (len(PASS), len(FAIL)))
if FAIL:
    raise SystemExit(1)
