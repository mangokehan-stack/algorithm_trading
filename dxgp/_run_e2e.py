# -*- coding: utf-8 -*-
"""End-to-end harness for zt_shrink_strategy_gbk.py (V2.6.82).

Scope:
  - exec the real GBK source into an isolated namespace
  - virtual clock (time.time / datetime.now / date.today), sandboxed __file__
  - full QMT API stub surface (C methods + bare globals)
  - deterministic synthetic market: 002142.SZ passes the shrink-pullback gate chain
  - Day1 (2026-10-19): init -> screen -> shrink buy (DRY_RUN simulated fill)
  - Day2 (2026-10-20): volume expansion + profit -> sell (never-stop-loss honoured)
  - asserts: no traceback, no stop-loss sell, pyramid path no NameError,
             state persisted, print_summary output, atexit double registration

Config switches changed in-namespace (documented runtime options, no source edits):
  DRY_RUN=True, SIM_FILL_PROB=1.0, SIM_DRY_FILL_PROB=1.0,
  STALL_CONFIRM_ON=False, _SENTIMENT_ON=False
"""
import contextlib
import io
import json
import os
import random
import sys
import tempfile
import types
import datetime as _dt
import time as _time

SRC_PATH = 'zt_shrink_strategy_gbk.py'
src = open(SRC_PATH, 'rb').read().decode('gbk', 'strict')
SB = tempfile.mkdtemp(prefix='e2e_')

PASS = []
FAIL = []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s  %s  %s' % ('PASS' if cond else 'FAIL', name, extra if not cond else ''))


# ---------------------------------------------------------------- virtual clock
CLOCK = {'ts': _dt.datetime(2026, 10, 19, 10, 40, 0).timestamp()}


class FakeDT(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fromtimestamp(CLOCK['ts'])

    @classmethod
    def today(cls):
        return cls.fromtimestamp(CLOCK['ts'])


class FakeDate(_dt.date):
    @classmethod
    def today(cls):
        return cls.fromtimestamp(CLOCK['ts']).date()


dt_mod = types.ModuleType('datetime')
for _n in dir(_dt):
    setattr(dt_mod, _n, getattr(_dt, _n))
dt_mod.datetime = FakeDT
dt_mod.date = FakeDate

tm_mod = types.ModuleType('time')
for _n in dir(_time):
    setattr(tm_mod, _n, getattr(_time, _n))
tm_mod.time = lambda: CLOCK['ts']

# ---------------------------------------------------------------- calendar/data
def weekdays(a, b):
    out = []
    d = a
    while d <= b:
        if d.weekday() < 5:
            out.append(d)
        d += _dt.timedelta(days=1)
    return out


CAL = weekdays(_dt.date(2026, 7, 1), _dt.date(2026, 12, 31))
YMD = [d.strftime('%Y%m%d') for d in CAL]
TODAY1 = '20261019'
TODAY2 = '20261020'
PREV = [y for y in YMD if y < TODAY1]
D25 = PREV[-25:]

UNIVERSE = ['002142.SZ', '600000.SH', '600036.SH', '600519.SH', '601318.SH',
            '000001.SZ', '000333.SZ', '000651.SZ', '600276.SH', '601166.SH']


def mk_bar(o, h, l, c, v, to=0.03):
    return {'open': round(o, 2), 'high': round(h, 2), 'low': round(l, 2),
            'close': round(c, 2), 'volume': float(v),
            'amount': round(c, 2) * float(v) * 100.0, 'turnover': to}


BARS = {}
# --- 002142.SZ: ZT at D25[-6], then shrinking volume, closes above MA10/ZT low ---
_b = {}
_px = 10.0
for _d in D25[:-6]:
    _px = round(_px * 1.002, 2)
    _b[_d] = mk_bar(_px * 0.995, _px * 1.01, _px * 0.99, _px, 12000, 0.03)
T0 = D25[-6]
_pc = _px
_t0c = round(_pc * 1.10, 2)
_b[T0] = mk_bar(_pc * 1.03, _t0c, _pc * 1.02, _t0c, 18000, 0.10)   # 放量涨停
_seq = [(11.45, 9500, 0.05), (11.48, 8000, 0.04), (11.50, 7500, 0.04),
        (11.52, 7000, 0.035), (11.53, 9000, 0.045)]
for _d, (_c, _v, _to) in zip(D25[-5:], _seq):
    _b[_d] = mk_bar(_c - 0.08, _c * 1.008, _c - 0.12, _c, _v, _to)
BARS['002142.SZ'] = _b
T0_DATE = T0

# --- other 9 codes: flat, no limit-up ever ---
for _code in UNIVERSE[1:]:
    _p = 15.0
    _bb = {}
    for _d in D25:
        _p = round(_p * 1.0005, 2)
        _bb[_d] = mk_bar(_p * 0.995, _p * 1.01, _p * 0.985, _p, 20000, 0.03)
    BARS[_code] = _bb

# --- index: gently rising (no tide block) ---
IDX = {}
_p = 3200.0
for _d in YMD:
    if _d > TODAY1:
        break
    _p = round(_p * (1.003 if _d in D25 else 1.0), 2)
    IDX[_d] = mk_bar(_p * 0.998, _p * 1.004, _p * 0.996, _p, 3000000, 0.02)

DETAIL = {}
for _code in UNIVERSE:
    _cl = BARS[_code][D25[-1]]['close']
    DETAIL[_code] = {
        'InstrumentName': '宁波银行' if _code == '002142.SZ' else ('测试股%s' % _code[:6]),
        'FloatVolume': 8.0e8, 'FloatVolumn': 8.0e8, 'CirculatingVolume': 8.0e8,
        'TotalVolume': 2.0e9, 'PreClose': _cl, 'LastPrice': _cl,
        'UpStopPrice': round(_cl * 1.10, 2), 'DownStopPrice': round(_cl * 0.90, 2),
    }

# --- today's tick + 1m bars, mutable per day ---
STATE = {'px': 11.56, 'prev_close': 11.53, 'min_vol': 12.0, 'day': 1}


def build_intraday():
    """rebuild 1m bars + tick from STATE; last bar aligns to current clock minute"""
    code = '002142.SZ'
    now = FakeDT.now()
    day = now.strftime('%Y%m%d')
    n = max(1, (now.hour * 60 + now.minute) - (9 * 60 + 30) + 1)
    m1 = {}
    px0 = STATE['prev_close']
    px = px0
    for i in range(n):
        px = round(px + (STATE['px'] - px0) / float(n), 3)
        tot = 9 * 60 + 30 + i
        hh, mm = divmod(tot, 60)
        key = day + '%02d%02d' % (hh, mm)
        m1[key] = {'open': px, 'high': px + 0.01, 'low': px - 0.01,
                   'close': px, 'volume': STATE['min_vol'],
                   'amount': px * STATE['min_vol'] * 100}
    cum = STATE['min_vol'] * n
    tick = {code: {'lastPrice': STATE['px'], 'volume': cum,
                   'high': STATE.get('high') or max(STATE['px'], px0),
                   'low': STATE.get('low') or min(px0, STATE['px']),
                   'lastClose': STATE['prev_close'], 'open': px0,
                   'amount': STATE['px'] * cum * 100, 'bar_cnt': n}}
    return {code: m1}, tick


M1_TODAY, TICK = build_intraday()


# ---------------------------------------------------------------- stubs
class Ctx(object):
    def __init__(self):
        self.run_time_calls = []
        self.accid = ''
        self.barpos = 1
        self.passorder_calls = []

    def run_time(self, name, period, start):
        self.run_time_calls.append((name, period, start))
        return True

    def set_account(self, accid):
        self.accid = accid
        return True

    def subscribe_quote(self, *a, **kw):
        return True

    def get_stock_list_in_sector(self, name, extra=None):
        if '沪深' in str(name) or str(name) == 'A股':
            return list(UNIVERSE)
        return []

    def get_sector_list(self):
        return ['沪深A股']

    def get_trading_dates(self, market, start, end, count, period):
        return [y for y in YMD if str(start) <= y <= str(end)]

    def get_instrument_detail(self, code):
        return dict(DETAIL.get(code) or {})

    def get_full_tick(self, codes):
        return {c: dict(TICK.get(c) or {}) for c in (codes or [])}

    def get_market_data_ex(self, fields=None, codes=None, period='1d', start='', end='',
                           count=0, *a, **kw):
        if period == '1d':
            out = {}
            for c in (codes or []):
                if c == '000001.SH':
                    out[c] = dict(IDX)
                else:
                    out[c] = dict(BARS.get(c) or {})
            return out
        if period == '1m':
            return {c: dict(M1_TODAY.get(c) or {}) for c in (codes or [])}
        return {}

    def get_raw_financial_data(self, fields, stocks, start, end, **kw):
        out = {}
        ts = int(_dt.datetime(2026, 6, 30).timestamp() * 1000)
        for s in (stocks or []):
            out[s] = {'ASHAREINCOME.net_profit_excl_min_int_inc': {ts: 8.6e8}}
        return out

    def get_financial_data(self, *a, **kw):
        return None

    def is_last_bar(self):
        return True


CTX = Ctx()


def passorder(op, ot, accid, code, prt, px, vol, remark, qt, uid, C):
    CTX.passorder_calls.append((op, code, px, vol, remark))
    return True


def cancel(oid, accid, kind, C=None):
    return True


def can_cancel_order(oid, accid, kind):
    return True


def get_trade_detail_data(accid, kind1, kind2):
    if kind2 == 'ACCOUNT':
        o = types.SimpleNamespace()
        o.m_dAvailable = 200000.0
        o.m_dBalance = 200000.0
        return [o]
    return []


def download_history_data(*a, **kw):
    return None


# ---------------------------------------------------------------- exec module
ns = {'__file__': os.path.join(SB, SRC_PATH), '__name__': 'zt_e2e'}
_real_time = sys.modules['time']
_real_dt = sys.modules['datetime']
sys.modules['time'] = tm_mod
sys.modules['datetime'] = dt_mod
try:
    exec(compile(src, SRC_PATH, 'exec'), ns)
finally:
    sys.modules['time'] = _real_time
    sys.modules['datetime'] = _real_dt

# namespace-level option switches
ns['DRY_RUN'] = True
ns['SIM_FILL_PROB'] = 1.0
ns['SIM_DRY_FILL_PROB'] = 1.0
ns['STALL_CONFIRM_ON'] = False
ns['_SENTIMENT_ON'] = False
random.seed(20261019)

ns['G'].C = CTX
ns['G'].accid = '8973786'
ns.update({'passorder': passorder, 'cancel': cancel, 'can_cancel_order': can_cancel_order,
           'get_trade_detail_data': get_trade_detail_data,
           'download_history_data': download_history_data})

print('=' * 74)
print('E2E V2.6.82  sandbox=%s' % SB)
print('=' * 74)

# ---------------------------------------------------------------- registers
import atexit as _atexit
_ncb0 = _atexit._ncallbacks()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ns['init'](CTX)
init_log = buf.getvalue()
_ncb1 = _atexit._ncallbacks()
chk('init 无异常', True)
chk('atexit 双注册成功(+2)', _ncb1 - _ncb0 == 2, 'delta=%d' % (_ncb1 - _ncb0))

ns['G'].state['dry_cash'] = 200000.0
ns['G'].state['状态资金'] = 200000.0
ns['G'].acct_ok = True


def rounds(n, tag):
    out = []
    for i in range(n):
        CLOCK['ts'] += 45
        _m1, _tk = build_intraday()      # keep 1m bars fresh relative to virtual now
        M1_TODAY.clear(); M1_TODAY.update(_m1)
        TICK.clear(); TICK.update(_tk)
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            ns['timer_poll'](CTX)
        out.append(b.getvalue())
    txt = '\n'.join(out)
    print('--- %s: %d 轮 %d 字符 ---' % (tag, n, len(txt)))
    return txt


def state():
    return ns['G'].state


# ---------------------------------------------------------------- Day 1
d1 = rounds(6, 'Day1')
st = state()
hold = st.get('hold') or {}
chk('Day1 选股产出候选', any('今日低吸候选共' in x for x in [d1]) and '002142' in d1)
chk('Day1 买入成交落库', '002142.SZ' in hold, 'hold=%r' % list(hold)[:3])
chk('Day1 持仓股数>0', bool(hold.get('002142.SZ')) and
    int(hold['002142.SZ'].get('fill_vol', 0)) > 0,
    'fill_vol=%r' % (hold.get('002142.SZ') or {}).get('fill_vol'))
_plan1 = list((hold.get('002142.SZ') or {}).get('plan_batches') or [])
_fill1 = int((hold.get('002142.SZ') or {}).get('fill_vol', 0) or 0)
chk('Day1 分批计划已落地', bool(_plan1), 'plan=%r' % _plan1)
chk('Day1 无 Traceback', 'Traceback' not in d1, d1[-400:] if 'Traceback' in d1 else '')
chk('Day1 无盘中轮询异常', '盘中轮询异常' not in d1)
chk('Day1 无 PYRAMID_BATCHES NameError', 'PYRAMID_BATCHES' not in d1 and 'NameError' not in d1)
chk('Day1 状态文件已落盘', os.path.exists(ns['state_path']()), ns['state_path']())

# ---------------------------------------------------------------- Day1 afternoon: pyramid add
CLOCK['ts'] = _dt.datetime(2026, 10, 19, 11, 17, 0).timestamp()
STATE.update({'px': 11.56, 'high': 11.60, 'low': 11.45, 'min_vol': 12.0})
d1b = rounds(4, 'Day1-加仓')
h1b = state().get('hold') or {}
_hb = h1b.get('002142.SZ') or {}
chk('加仓段无 NameError', 'NameError' not in d1b and 'is not defined' not in d1b,
    d1b[-400:] if 'NameError' in d1b else '')
chk('加仓段无 Traceback', 'Traceback' not in d1b, d1b[-400:] if 'Traceback' in d1b else '')
chk('第2批加仓已评估/成交', (int(_hb.get('plan_idx', 0) or 0) >= 1) or ('分批低吸第' in d1b),
    'plan_idx=%r fill_vol=%r' % (_hb.get('plan_idx'), _hb.get('fill_vol')))
chk('加仓后股数增加', int(_hb.get('fill_vol', 0) or 0) >= _fill1,
    'fill=%r vs %r' % (_hb.get('fill_vol'), _fill1))
chk('无参数一致性误告警', '参数一致性告警' not in d1b,
    [l for l in d1b.split('\n') if '参数一致性告警' in l][:2])

# ---------------------------------------------------------------- Day 2
CLOCK['ts'] = _dt.datetime(2026, 10, 20, 10, 40, 0).timestamp()
STATE.update({'day': 2, 'px': 12.45, 'prev_close': 11.53, 'min_vol': 430.0})
_m1, _tk = build_intraday()
M1_TODAY.clear()
M1_TODAY.update(_m1)
TICK.clear()
TICK.update(_tk)
# update detail for day2 (limit prices based on day1 close)
for _c in UNIVERSE:
    DETAIL[_c]['UpStopPrice'] = round(11.53 * 1.10, 2)
    DETAIL[_c]['DownStopPrice'] = round(11.53 * 0.90, 2)

d2 = rounds(10, 'Day2')
st2 = state()
hold2 = st2.get('hold') or {}
trades = st2.get('trades') or []
chk('Day2 无 Traceback', 'Traceback' not in d2, d2[-500:] if 'Traceback' in d2 else '')
chk('Day2 无盘中轮询异常', '盘中轮询异常' not in d2)
chk('Day2 触发放量止盈', '放量止盈' in d2, d2[-600:] if '放量止盈' not in d2 else '')
_buys = [t for t in trades if t.get('dir') == '买入']
_sells = [t for t in trades if t.get('dir') == '卖出']
chk('Day1 买入记录入账本', len(_buys) >= 1 and all(b.get('code') == '002142.SZ' for b in _buys),
    'buys=%r' % [b.get('code') for b in _buys])
chk('金字塔加仓产生独立买入记录(≥2笔)', len(_buys) >= 2, 'n=%d' % len(_buys))
chk('Day2 卖出记录入账本', len(_sells) == 1 and _sells[0].get('code') == '002142.SZ',
    'sells=%r' % [(s.get('code'), s.get('dir')) for s in _sells])
chk('卖出扣费后净利>0(绝不止损铁律)', bool(_sells) and float(_sells[0].get('pnl') or 0) > 0,
    'pnl=%r' % (_sells[0].get('pnl') if _sells else None))
chk('卖出价格高于买入成本', bool(_sells) and bool(_buys)
    and float(_sells[0].get('price') or 0) > float(_buys[0].get('price') or 0))
chk('分批计划为3批(PYRAMID_SPLITS)', len(_plan1) == 3, 'plan=%r' % _plan1)
h2 = hold2.get('002142.SZ') or {}
chk('Day2 持仓已清/退出', (not hold2) or h2.get('exited') or int(h2.get('fill_vol', 0)) == 0,
    'h2=%r' % {k: h2.get(k) for k in ('fill_vol', 'exited', 'sell_pending')})
chk('全程无止损卖出', ('止损卖出' not in d1 + d2) and ('已止损' not in d1 + d2))
chk('全程无NameError', 'NameError' not in (d1 + d2) and 'is not defined' not in (d1 + d2))

# ---------------------------------------------------------------- summary
b2 = io.StringIO()
with contextlib.redirect_stdout(b2):
    ns['print_summary']()
sumo = b2.getvalue()
chk('print_summary 输出汇总', '本次运行结束汇总' in sumo, sumo[:200])
chk('print_summary 含买卖笔数', ('买入' in sumo) and ('卖出' in sumo), sumo[:200])

files = sorted(os.listdir(SB))
print('\n沙箱文件: %s' % files)
print('订单: %d 笔 passorder(实盘通道未触发则0) | 成交记录: %d 条' %
      (len(CTX.passorder_calls), len(trades)))

print('\n' + '=' * 74)
print('RESULT: %d passed, %d failed' % (len(PASS), len(FAIL)))
if FAIL:
    print('FAILED: %s' % FAIL)
print('=' * 74)
sys.exit(1 if FAIL else 0)
