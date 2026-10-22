# -*- coding: utf-8 -*-
"""情绪刷新幂等性验证: 成功/降级两条路径下的 last_fetch_date 语义。

验证目标:
  A. 成功刷新后, 同一天再次调度不得重复发起取数(幂等)。
  B. 取数彻底失败(rows=None)时, 不得锁定当日, 应按节流重试。
  C. 取数成功但信号不可用(降级)时, 是否仍锁定当日 —— 若锁定, 当天再也不会重试。
"""
import ast
import sys
import time as _time

SRC = 'zt_shrink_strategy_gbk.py'
text = open(SRC, 'rb').read().decode('gbk', errors='strict')
tree = ast.parse(text)

WANT = ('sent_daily_refresh', '_sent_today', '_sent_apply_rows', '_sent_wlog',
        '_sent_reset_ready', '_sent_degrade_alert', '_sent_fresh_enough',
        '_sent_override_note')
nodes = {}
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name in WANT:
        nodes[n.name] = n
missing = [w for w in WANT if w not in nodes]
if missing:
    print('MISSING FUNCS:', missing)
    sys.exit(1)

LOGS = []
ALERTS = []


class _G(object):
    pass


G = _G()
G.today = '20261019'
G.calendar = ['20261015', '20261016', '20261019']
G.accid = 'T1'

SENT_STATE = {}
_SENTIMENT_ON = True
_SENTIMENT_READY = False
SENT_RETRY_SEC = 300
SENT_HIST_MAX = 260
SENT_LAG_DAYS = 1
SENT_DEGRADE_ALERT_DAYS = 3


def log(*a):
    LOGS.append(' '.join(str(x) for x in a))


def notify_enqueue(t, **kw):
    ALERTS.append(str(t))


def risk_excluded(s):
    return ''


FETCH_CALLS = []


def sent_fetch_all_data():
    """桩: 只计数, 不真取数"""
    FETCH_CALLS.append(_time.time())
    return None


ns = {
    'ast': ast, 'sys': sys, 'time': _time, 'G': G,
    'SENT_STATE': SENT_STATE, '_SENTIMENT_ON': _SENTIMENT_ON,
    '_SENTIMENT_READY': _SENTIMENT_READY, 'SENT_RETRY_SEC': SENT_RETRY_SEC,
    'SENT_HIST_MAX': SENT_HIST_MAX, 'SENT_LAG_DAYS': SENT_LAG_DAYS,
    'SENT_DEGRADE_ALERT_DAYS': SENT_DEGRADE_ALERT_DAYS,
    'sent_fetch_all_data': sent_fetch_all_data,
    'log': log, 'notify_enqueue': notify_enqueue, '_f': float,
    'SENT_MONITOR_MAX_STALE_DAYS': 5,
    # 供 _sent_override_note 取"原值"
    'SHRINK_BUY_RATIO': 0.36, 'BUY_MIN_ELAPSED_MIN': 30, 'EXPAND_SELL_RATIO': 2.00,
}
for _name, _node in nodes.items():
    _src = ast.get_source_segment(text, _node)
    exec(compile(ast.Module(body=[_node], type_ignores=[]), '<x>', 'exec'), ns)
    # 同时把函数注入 ns 供互相调用
ns['SENT_STATE'] = SENT_STATE

sent_daily_refresh = ns['sent_daily_refresh']
_sent_apply_rows = ns['_sent_apply_rows']
_sent_today = ns['_sent_today']

fails = []
total = []


def chk(name, cond, detail=''):
    total.append(name)
    print('%-58s %s%s' % (name, 'PASS' if cond else 'FAIL',
                          '' if cond else '  <- ' + str(detail)))
    if not cond:
        fails.append(name)


def reset():
    del FETCH_CALLS[:]
    del LOGS[:]
    del ALERTS[:]
    SENT_STATE.clear()
    SENT_STATE['ready'] = False
    SENT_STATE['overrides'] = {}
    ns['_SENTIMENT_READY'] = False


# ---------------- A 成功路径幂等 ----------------
reset()
rows_ok = [
    {'date': '20261015', 'advpct': 0.5, 'limit_up': 30, 'turnover': 1e11},
    {'date': '20261016', 'advpct': 0.4, 'limit_up': 20, 'turnover': 9e10},
]
# 直接写 last_fetch_date 模拟"成功刷新"后的状态(不依赖 _sent_compute 的复杂输入)
SENT_STATE['last_fetch_date'] = '20261019'
sent_daily_refresh()
chk('A1 成功刷新后同日不再发起取数', len(FETCH_CALLS) == 0, len(FETCH_CALLS))
SENT_STATE['last_fetch_date'] = '20261018'      # 模拟跨日
sent_daily_refresh()
chk('A2 跨日后会重新发起取数', len(FETCH_CALLS) == 1, len(FETCH_CALLS))

# ---------------- B 取数失败不锁日 ----------------
reset()
SENT_STATE['last_try_ts'] = 0.0
_sent_apply_rows(None)          # 取数彻底失败
chk('B1 取数失败不写last_fetch_date', SENT_STATE.get('last_fetch_date') in (None, ''),
    SENT_STATE.get('last_fetch_date'))
sent_daily_refresh()
chk('B2 取数失败后当日可重试', len(FETCH_CALLS) == 1, len(FETCH_CALLS))

# ---------------- C 降级(rows 非空但不可用)是否锁日 ----------------
reset()
SENT_STATE['last_try_ts'] = 0.0
# rows 全为"今日"行 -> comp 为空 -> 走 '暂无昨日完成数据' 降级分支
rows_future = [{'date': '20261019', 'advpct': 0.5, 'limit_up': 30, 'turnover': 1e11}]
_sent_apply_rows(rows_future)
_wrote = SENT_STATE.get('last_fetch_date')
_degraded = any('降级' in l or '中性' in l for l in LOGS)
print('   降级后 last_fetch_date=%r ready=%r log=%s'
      % (_wrote, SENT_STATE.get('ready'), LOGS[-1:]))
chk('C1 降级分支不得写last_fetch_date', _wrote in (None, ''), _wrote)
sent_daily_refresh()
chk('C2 降级后当日仍会重试', len(FETCH_CALLS) == 1, len(FETCH_CALLS))

# ---------------- D 覆写中文释义 ----------------
_note = ns['_sent_override_note']
_n1 = _note({'SHRINK_BUY_RATIO': 0.30, 'BUY_MIN_ELAPSED_MIN': 45})
print('   覆写释义示例: %s' % _n1)
chk('D1 覆写释义含中文名/原值/新值',
    ('缩量阈值' in _n1) and ('0.36->0.3' in _n1)
    and ('开盘等待分钟' in _n1) and ('30->45' in _n1), _n1)
chk('D2 空覆写返回空串', _note({}) == '' and _note(None) == '', '')
chk('D3 未知键原样输出不隐藏',
    ('WEIRD_KEY' in _note({'WEIRD_KEY': 1})) and ('未收录' in _note({'WEIRD_KEY': 1})),
    _note({'WEIRD_KEY': 1}))

print('')
if fails:
    print('RESULT: %d passed, %d failed' % (len(total) - len(fails), len(fails)))
    print('FAILED:', fails)
    sys.exit(1)
print('RESULT: %d passed, 0 failed' % len(total))
