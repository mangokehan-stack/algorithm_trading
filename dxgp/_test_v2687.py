# -*- coding: utf-8 -*-
"""V2.6.87 六项改动专项验证
【1】批量取数失败拆 100/30 重试 + 失败样本带类型
【2B】覆盖率不足沿用上次成功信号(无历史/过期则降级中性)
【3】信号分量可用性标注
【4】ready 三态 + fetching 标志
【5】双实例心跳检测(只告警不阻断)
【6】buy_stock lp<=0 保护
"""
import os
import sys
import json
import time
import shutil
import tempfile

P = 'zt_shrink_strategy_gbk.py'
text = open(P, 'rb').read().decode('gbk')

TMP = tempfile.mkdtemp(prefix='v2687_')
LOGS, NOTIFIES = [], []
fails = []


class FakeG(object):
    def __init__(self):
        self.today = '20261019'
        self.calendar = []
        self.accid = '8973786'
        self.state = {}
        self.ready = True
        self.no_download = True


def fake_log(msg, *a, **kw):
    LOGS.append(str(msg))


def fake_notify(t):
    NOTIFIES.append(str(t))


ns = {'__name__': 'strat_v2687',
      '__file__': os.path.join(TMP, 'zt_shrink_strategy_gbk.py')}
exec(compile(text, P, 'exec'), ns)
ns['log'] = fake_log
ns['notify_enqueue'] = fake_notify
ns['G'] = FakeG()

SENT_STATE = ns['SENT_STATE']
_cache_p = os.path.join(TMP, 'zt_shrink_sent_cache_8973786.json')
ns['_sent_cache_path'] = lambda: _cache_p


def chk(name, got, exp):
    stats['n'] += 1
    ok = (got == exp)
    print('%-58s %s' % (name, 'PASS' if ok else 'FAIL  got=%r exp=%r' % (got, exp)))
    if not ok:
        fails.append(name)


stats = {'n': 0}


def reset_sent():
    SENT_STATE.clear()
    ns['_SENTIMENT_READY'] = False
    del LOGS[:]
    del NOTIFIES[:]


# ==================== 【1】分批拆分重试 ====================
print('--- 【1】批量取数失败拆 100/30 重试 ---')


class FakeC(object):
    def __init__(self, fail_over):
        self.fail_over = fail_over
        self.calls = []

    def get_market_data_ex(self, fields, codes, period, start, end, cnt, fq, a, b):
        self.calls.append(len(codes))
        if len(codes) > self.fail_over:
            raise RuntimeError('')          # 空消息: 复现实盘"第5批失败: "后面一片空白
        return dict((c, {'close': 10.0, 'preClose': 9.9}) for c in codes)


codes300 = ['%06d.SZ' % i for i in range(300)]

C = FakeC(150)
box = [0, 0, 0, []]
md = ns['_sent_fetch_md_batch'](C, codes300, ['close'], '20250101', 300, box, 0)
chk('T1a 300只批失败 -> 拆100后全部取到', len(md), 300)
chk('T1b 成功计数', box[0], 300)
chk('T1c 失败计数', box[1], 0)
chk('T1d 拆分重试次数=1', box[2], 1)
chk('T1e 实际调用批次 300,100,100,100', C.calls[:4], [300, 100, 100, 100])

C2 = FakeC(-1)                              # 全失败
box2 = [0, 0, 0, []]
md2 = ns['_sent_fetch_md_batch'](C2, codes300, ['close'], '20250101', 300, box2, 0)
chk('T1f 全失败返回空', len(md2), 0)
chk('T1g 全失败计数=300', box2[1], 300)
chk('T1h 失败样本带异常类型(不再是空白)', 'RuntimeError' in (box2[3][0] if box2[3] else ''), True)

# ==================== 【1b】整链路: 覆盖率如实上报 ====================
print('--- 【1b】_sent_fetch_sync 整链路覆盖率 ---')


class FakeC2(object):
    """600 只票; 代码 >= 000300 的段落一律失败(模拟"部分代码段取不到")"""

    def get_stock_list_in_sector(self, name, extra=None):
        return ['%06d.SZ' % i for i in range(600)]

    def get_market_data_ex(self, fields, codes, period, start, end, cnt, fq, a, b):
        if list(codes) == ['000001.SH']:
            return {'000001.SH': {'20261016': {'amount': 1e12}}}
        if any(int(c[:6]) >= 300 for c in codes):
            raise RuntimeError('')
        return dict((c, {'20261016': {'close': 10.0, 'preClose': 9.9}}) for c in codes)


ns['G'].C = FakeC2()
SENT_STATE.pop('cover', None)
del LOGS[:]
_rows = ns['_sent_fetch_sync']()
_cov = SENT_STATE.get('cover') or {}
chk('T7a 300/600 取到 -> 覆盖率 50%', round(_cov.get('ratio') or 0, 4), 0.5)
chk('T7b 成功/失败计数如实', (_cov.get('ok'), _cov.get('fail')), (300, 300))
chk('T7c 完成日志写明覆盖率', any('覆盖率50.0%' in x for x in LOGS), True)
chk('T7d 完成日志用"请求N只/成功M只"而不是股票池长度',
    any('请求600只 成功300只' in x for x in LOGS), True)
chk('T7e 覆盖率不足有明确告警', any('行情覆盖率不足' in x for x in LOGS), True)
chk('T7f 失败样本带异常类型', any('RuntimeError' in x for x in LOGS), True)
chk('T7g rows 仍返回(是否采用由上层决定)',
    isinstance(_rows, list) and len(_rows) > 0, True)

# ==================== 【2B】覆盖率不足沿用上次信号 ====================
print('--- 【2B】覆盖率不足沿用上次成功信号 ---')


def write_cache(d, extra=None):
    _d = {'date': d, 'sentiment': -1.27, 'regime': 'panic', 'gate_skip': False,
          'size_mult': 1.0,
          'overrides': {'BUY_MIN_ELAPSED_MIN': 45, 'SHRINK_BUY_RATIO': 0.3},
          'events': {}, 'ver': 'V2.6.87', 'ts': time.time()}
    if extra:
        _d.update(extra)
    with open(_cache_p, 'w') as fh:
        json.dump(_d, fh)


reset_sent()
if os.path.exists(_cache_p):
    os.remove(_cache_p)
r = ns['_sent_use_last_good']('测试:覆盖率不足')
chk('T2a 无历史信号 -> 不沿用', r, False)
chk('T2b 无历史 -> ready=False', SENT_STATE.get('ready'), False)

reset_sent()
write_cache('20261016')
r = ns['_sent_use_last_good']('行情覆盖率仅23.0%(<90%下限)')
chk('T2c 有历史 -> 沿用成功', r, True)
chk('T2d 沿用后 ready=True', SENT_STATE.get('ready'), True)
chk('T2e 沿用档位=panic', SENT_STATE.get('regime'), 'panic')
chk('T2f 沿用覆写 BUY_MIN_ELAPSED_MIN=45',
    (SENT_STATE.get('overrides') or {}).get('BUY_MIN_ELAPSED_MIN'), 45)
chk('T2g 沿用不写 last_fetch_date(必须继续重试真实数据)',
    SENT_STATE.get('last_fetch_date'), None)
chk('T2h 沿用打告警日志', any('沿用上一次成功信号' in x for x in LOGS), True)
chk('T2i 沿用推强提醒', any('沿用上一次成功信号' in x for x in NOTIFIES), True)

reset_sent()
write_cache('20250101')                     # 远超 5 个交易日
r = ns['_sent_use_last_good']('测试:覆盖率不足')
chk('T2j 历史信号过期 -> 不沿用', r, False)

reset_sent()
write_cache('20261016')
SENT_STATE['cover'] = {'req': 5226, 'ok': 1200, 'fail': 4026, 'retry': 14,
                       'ratio': 1200.0 / 5226.0, 'samples': [], 'fields_all': False}
ns['_sent_apply_rows']([{'date': '20261016', 'mkt_advance': 10.0,
                         'mkt_decline': 90.0, 'limit_up_cnt': 1.0,
                         'mkt_amount': 1e12}])
chk('T2k 覆盖率23% -> 不采用残缺样本(走沿用)', SENT_STATE.get('regime'), 'panic')
chk('T2l 沿用原因含覆盖率', '覆盖率' in str(SENT_STATE.get('err', '')), True)

reset_sent()
write_cache('20261016')
SENT_STATE['cover'] = {'req': 5226, 'ok': 5200, 'fail': 26, 'retry': 3,
                       'ratio': 5200.0 / 5226.0, 'samples': [], 'fields_all': False}
ns['_sent_apply_rows']([])                  # rows 空但覆盖率足够 -> 走原降级, 不沿用
chk('T2m 覆盖率足够但行情空 -> 仍按原逻辑降级', SENT_STATE.get('ready'), False)

# ==================== 【3】分量标注 ====================
print('--- 【3】信号分量可用性标注 ---')
n1 = ns['_sent_comp_note']({'comp_have': ['z_advpct', 'z_limit_up'],
                            'comp_miss': ['z_turnover'], 'comp_total': 3})
chk('T3a 缺分量标注 2/3 + 中文名',
    ('2/3' in n1 and '缺成交额' in n1 and '归一化' in n1), True)
n2 = ns['_sent_comp_note']({'comp_have': ['z_advpct', 'z_limit_up', 'z_turnover'],
                            'comp_miss': [], 'comp_total': 3})
chk('T3b 三分量全可用', ('3/3' in n2 and '全可用' in n2), True)
n3 = ns['_sent_comp_note']({})
chk('T3c 无分量信息不抛异常', isinstance(n3, str), True)

# ==================== 【4】fetching 与 ready 三态 ====================
print('--- 【4】ready 三态 / fetching 标志 ---')
chk('T4a 发起取数时置 fetching=True', "SENT_STATE['fetching'] = True" in text, True)
chk('T4b worker 结束复位 fetching=False', "SENT_STATE['fetching'] = False" in text, True)
chk('T4c ready 三态文案齐全',
    ('取数中(后台线程' in text and '尚未发起取数' in text), True)

# ==================== 【5】双实例心跳 ====================
print('--- 【5】双实例心跳检测 ---')
ns['_HB_STATE'].update({'last_ts': 0.0, 'last_alert_ts': 0.0, 'peer': '', 'boot': 0.0})
del LOGS[:]
del NOTIFIES[:]
ns['heartbeat_tick'](True)
chk('T5a 自己的心跳文件已创建', os.path.exists(ns['heartbeat_path']()), True)
chk('T5b 单实例不告警', any('检测到另一个策略实例' in x for x in LOGS), False)

peer_pid = 999999
peer_f = ns['_join_base']('zt_shrink_heartbeat_8973786_%d.json' % peer_pid)
with open(peer_f, 'w') as fh:
    json.dump({'pid': peer_pid, 'ts': time.time(), 'acc': '8973786',
               'ver': 'V2.6.87', 'boot': 0.0}, fh)
ns['_HB_STATE'].update({'last_ts': 0.0, 'last_alert_ts': 0.0})
del LOGS[:]
del NOTIFIES[:]
ns['heartbeat_tick'](True)
chk('T5c 活跃同伴 -> 告警', any('检测到另一个策略实例' in x for x in LOGS), True)
chk('T5d 告警含同伴PID', any(str(peer_pid) in x for x in LOGS), True)
chk('T5e 告警推强提醒', any('另一个策略实例' in x for x in NOTIFIES), True)
chk('T5f 告警声明只告警不阻断(不阻断下单)',
    any('只告警, 不阻断下单' in x for x in LOGS), True)

with open(peer_f, 'w') as fh:
    json.dump({'pid': peer_pid, 'ts': time.time() - 300, 'acc': '8973786',
               'ver': 'V2.6.87', 'boot': 0.0}, fh)
ns['_HB_STATE'].update({'last_ts': 0.0, 'last_alert_ts': 0.0, 'peer': 'x'})
del LOGS[:]
ns['heartbeat_tick'](True)
chk('T5g 同伴心跳过期 -> 不告警', any('检测到另一个策略实例' in x for x in LOGS), False)
chk('T5h 同伴退出有恢复提示', any('已恢复单实例' in x or '已退出' in x for x in LOGS), True)

# ==================== 【6】buy_stock 入参保护 ====================
print('--- 【6】buy_stock lp<=0 保护 ---')
chk('T6a 保护语句存在', 'if _f(lp) <= 0:' in text, True)
chk('T6b 跳过日志存在', '无有效价格' in text, True)
import ast
_tree = ast.parse(text)
_buy = [n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == 'buy_stock'][0]
_guard_ln = None
for _n in _buy.body:
    if isinstance(_n, ast.If):
        _src = ast.get_source_segment(text, _n)
        if _src and '_f(lp) <= 0' in _src:
            _guard_ln = _n.lineno
            break
chk('T6c 保护位于 buy_stock 函数体内(非注释)', _guard_ln is not None, True)
# 必须早于除零点 int(amount / lp / ...)
_div_ln = None
for _n in ast.walk(_buy):
    if isinstance(_n, ast.BinOp) and isinstance(_n.op, ast.Div):
        _s = ast.get_source_segment(text, _n)
        if _s and '/ lp' in _s:
            _div_ln = _n.lineno
            break
chk('T6d 保护早于 int(amount/lp/...) 除零点',
    (_guard_ln is not None and _div_ln is not None and _guard_ln < _div_ln),
    True)

shutil.rmtree(TMP, ignore_errors=True)
print('')
print('RESULT: %d passed, %d failed' % (stats['n'] - len(fails), len(fails)))
if fails:
    print('FAILED:')
    for x in fails:
        print('  -', x)
    sys.exit(1)
print('ALL V2.6.87 TESTS PASS')
