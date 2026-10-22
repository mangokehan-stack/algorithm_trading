# -*- coding: utf-8 -*-
"""V2.6.158 干跑: 五项修复逐条实测。
原则: 用真实模块(从 GBK 母版解码后 exec), 不注入模块桩;
      涉及 deal_callback 片段时从新版源码里【原样截取文本】再执行, 不用手写复刻。
"""
import sys, os, io, ast, json, types, tempfile, datetime, traceback, textwrap

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
RAW = open(P, 'rb').read().decode('gbk')
SRC = RAW.replace('\r\n', '\n')
LINES = SRC.split('\n')

TMP = tempfile.mkdtemp(prefix='dry158_')
os.chdir(TMP)          # 让 state_path / run_log 落到临时目录, 绝不碰生产状态文件
print('临时工作目录 =', TMP)

M = types.ModuleType('strat')
exec(compile(SRC, '<strat>', 'exec'), M.__dict__)
print('模块装载 OK, VERSION =', M.VERSION)

RESULT = []


def check(name, cond, detail=''):
    RESULT.append((name, bool(cond), detail))
    print(('PASS ' if cond else 'FAIL ') + name + (('  | ' + detail) if detail else ''))


# ============ 修 1: 排雷装载调用不再传函数不接收的参数 ============
print('\n' + '=' * 70)
print('修 1  load_risk_exclude(force=True) -> load_risk_exclude()')
print('=' * 70)
_sig = M.load_risk_exclude.__code__
check('1a 装载函数确实不接收任何参数', _sig.co_argcount == 0,
      'argcount=%d' % _sig.co_argcount)
try:
    M.load_risk_exclude(force=True)
    check('1b 旧写法能跑通(应该报错)', False, '竟然没抛异常')
except TypeError as e:
    check('1b 旧写法必抛 TypeError(证实是致命调用)', True, str(e)[:60])

_fc = [n for n in ast.walk(ast.parse(SRC))
       if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
       and n.func.id == 'load_risk_exclude']
check('1c 新版全文已无带参数的调用', all(len(x.args) == 0 and not x.keywords for x in _fc),
      '调用点 %d 处' % len(_fc))
_calls = [(x.lineno, len(x.args), len(x.keywords)) for x in _fc]
print('     调用点明细(行, 位置参数, 关键字参数):', _calls)

# 新版调用点外面有 try 保护?
_l = [x.lineno for x in _fc]
_guard = False
for _ln in _l:
    _w = '\n'.join(LINES[_ln - 4:_ln])
    if 'try:' in _w:
        _guard = True
check('1d 装载调用已置于保护块内', _guard)

# ============ 修 4: 装载函数有返回值 ============
print('\n' + '=' * 70)
print('修 4  load_risk_exclude 走完读盘分支后有返回值')
print('=' * 70)
M.G.today = '20261021'
M.G.risk_ex = {}
M.G.risk_ex_date = ''
M.G.risk_ex_try_ts = 0.0
M.G.risk_ex_sig = None
M.G.risk_ex_stat_ts = 0.0
M.G.risk_ex_note_date = '20261021'
M.G.risk_ex_src_warn_date = '20261021'
M.G.risk_ex_data = None

_r = M.load_risk_exclude()
check('4a 清单文件不存在时返回 dict 而非 None', isinstance(_r, dict), 'type=%s' % type(_r).__name__)

# 造一份合法清单, 让读盘分支真正跑通
_cands = M._risk_exclude_candidates()
print('     候选路径:', _cands)
_p0 = _cands[0]
os.makedirs(os.path.dirname(_p0), exist_ok=True)
_payload = {'asof': '20261021', 'window_days': 45,
            'stocks': {'600000.SH': {'tags': ['st'], 'reasons': ['测试']},
                       '002142.SZ': {'tags': ['ann'], 'reasons': ['测试2']}},
            'sources': {'st': {'ok': True}}, 'errors': []}
with open(_p0, 'w', encoding='utf-8') as f:
    json.dump(_payload, f, ensure_ascii=False)

M.G.risk_ex = {}
M.G.risk_ex_date = ''
M.G.risk_ex_try_ts = 0.0
M.G.risk_ex_sig = None
_r2 = M.load_risk_exclude()
check('4b 读盘成功后返回的正是清单内容', isinstance(_r2, dict) and len(_r2) == 2,
      'len=%s' % (len(_r2) if isinstance(_r2, dict) else 'None'))
check('4c 返回内容与文件一致', isinstance(_r2, dict) and '600000.SH' in _r2)
check('4d 装载后已锁定当日(说明走的是成功分支)',
      M.G.risk_ex_date == M.G.today, 'risk_ex_date=%r' % M.G.risk_ex_date)

# ============ 修 6: 八位年月日不再被当成 1970 年起的秒数 ============
print('\n' + '=' * 70)
print('修 6  _ts_to_date 八位年月日识别')
print('=' * 70)
_old_wrong = datetime.datetime.fromtimestamp(20260930).strftime('%Y%m%d')
print('     旧版把 20260930 当秒数会算成:', _old_wrong)
check('6a 字符串八位日期', M._ts_to_date('20260930') == '20260930',
      '实际=%r' % M._ts_to_date('20260930'))
check('6b 整数八位日期', M._ts_to_date(20260930) == '20260930',
      '实际=%r' % M._ts_to_date(20260930))
check('6c 带横线日期仍正常', M._ts_to_date('2026-09-30') == '20260930',
      '实际=%r' % M._ts_to_date('2026-09-30'))
check('6d 带时分秒仍正常', M._ts_to_date('2026-09-30 00:00:00') == '20260930',
      '实际=%r' % M._ts_to_date('2026-09-30 00:00:00'))
_ts_sec = 1792503584
_ts_ms = 1792503584000
_exp_sec = datetime.datetime.fromtimestamp(_ts_sec).strftime('%Y%m%d')
_exp_ms = datetime.datetime.fromtimestamp(_ts_ms / 1000.0).strftime('%Y%m%d')
check('6e 真秒级时间戳仍正常', M._ts_to_date(_ts_sec) == _exp_sec,
      '实际=%r 期望=%r' % (M._ts_to_date(_ts_sec), _exp_sec))
check('6f 真毫秒时间戳仍正常', M._ts_to_date(_ts_ms) == _exp_ms,
      '实际=%r 期望=%r' % (M._ts_to_date(_ts_ms), _exp_ms))
check('6g 字符串时间戳仍正常', M._ts_to_date(str(_ts_ms)) == _exp_ms,
      '实际=%r 期望=%r' % (M._ts_to_date(str(_ts_ms)), _exp_ms))
check('6h 空值不炸', M._ts_to_date('') == '' and M._ts_to_date(None) == '')

# ============ 修 3: 买入费用不再记两遍 ============
print('\n' + '=' * 70)
print('修 3  预填费用在首笔成交时清零, 费用只认成交回报')
print('=' * 70)
# --- 从新版源码原样截取 deal_callback 里 BUY 分支的记账片段 ---
_lo = _hi = None
for _i, _s in enumerate(LINES):
    if 'was_new = int(_f(h.get(' in _s and "'fill_vol', 0) or 0)) <= 0" in _s:
        _lo = _i
    if _lo is not None and "h['cost_total'] = _round2(h['fill_sum'] + h['fee'])" in _s:
        _hi = _i
        break
assert _lo is not None and _hi is not None, '没能定位记账片段'
_frag = '\n'.join(LINES[_lo:_hi + 1])
_frag_nc = textwrap.dedent('\n'.join(x for x in LINES[_lo:_hi + 1]
                                     if not x.strip().startswith('#')))
print('     截取源码行 L%d~L%d (去注释后 %d 行)' % (_lo + 1, _hi + 1, len(_frag_nc.split('\n'))))

px, vol = 28.02, 900
_amt_total = M._round2(px * vol)
_init_fee = M.fee_buy(px * vol, '601595.SH')
print('     委托金额 %.2f, 发单预填费 %.2f' % (_amt_total, _init_fee))

M.G.state = {'hold': {}, 'order_fee_acc': {}, 'trades': []}
M.G.today = '20261021'
h = {'fee': _init_fee, 'cost_total': M._round2(px * vol + _init_fee),
     'fee_pre': _init_fee, 'fill_sum': 0.0, 'fill_vol': 0, 'buy_vol': vol,
     'order_cnt': 1, 'name': '上海电影', 'buy_date': '20261021', 'buy_price': px}
M.G.state['hold']['601595.SH'] = h

for _v in (100, 100, 700):
    _amt = M._round2(px * _v)
    fee = M.fee_buy(_amt, '601595.SH', order_id='OID-601595-1')
    env = {'h': h, 'price': px, 'volume': _v, 'fee': fee,
           '_f': M._f, '_round2': M._round2}
    exec(compile(_frag_nc, '<frag>', 'exec'), {}, env)
    print('     第%d笔 %3d股 本笔费=%.2f | 累计 fee=%.2f cost_total=%.2f 标记=%r'
          % (_v, _v, fee, h['fee'], h['cost_total'], h.get('fee_pre')))

_true_fee = _amt_total * 0.00001 + 5.0
_true_fee = M._round2(_true_fee)
check('3a 累计费用等于一张委托的真实费用', abs(h['fee'] - _true_fee) < 0.005,
      '记录=%.2f 真实=%.2f' % (h['fee'], _true_fee))
check('3b 成本等于成交金额+真实费用', abs(h['cost_total'] - (_amt_total + _true_fee)) < 0.005,
      '记录=%.2f 真实=%.2f' % (h['cost_total'], _amt_total + _true_fee))
check('3c 预填标记已清除', 'fee_pre' not in h)
check('3d 与旧版对照: 旧版会记成 %.2f, 新版 %.2f, 少虚高 %.2f'
      % (_init_fee + _true_fee, h['fee'], _init_fee), True)

# 发单后的占位记录里确实带标记(源码断言)
check('3e 占位记录带 fee_pre 标记',
      "'fee_pre': _init_fee," in RAW)

# ============ 修 2: 人工核对型冻结不被写盘成功解除 ============
print('\n' + '=' * 70)
print('修 2  state_broken_lock: 写盘成功不解冻人工核对型冻结')
print('=' * 70)
M.G.today = '20261021'
M.G.state = {'hold': {}, 'buys': {'live': {'date': '', 'n': 0, 'codes': []},
                                  'paper': {'date': '', 'n': 0, 'codes': []}},
             'trades': [], 'sell_ctx': {}, 'buy_ctx': {}, 'account': ''}
M.G.state_bak_date = ''
M.G.save_fail_n = 0

M.G.state_broken = True
M.G.state_broken_lock = True
_ok = M.save_state()
check('2a 写盘本身成功', _ok is True, 'return=%r' % _ok)
check('2b 人工核对型冻结在写盘后仍然有效', M.G.state_broken is True,
      'state_broken=%r' % M.G.state_broken)
check('2c 失败计数已清零', M.G.save_fail_n == 0)

M.G.state_broken = True
M.G.state_broken_lock = False
_ok2 = M.save_state()
check('2d 写盘失败型冻结仍按原样自动解除', M.G.state_broken is False and _ok2 is True,
      'state_broken=%r' % M.G.state_broken)

# 四处人工冻结点都打了标记
_n_lock = RAW.count('G.state_broken_lock = True')
check('2e 四处人工冻结点全打了标记', _n_lock == 4, '实际 %d 处' % _n_lock)

# 修 2 没有引入新的模块级大写常量
_t = ast.parse(SRC)
_newconst = [x for x in _t.body if isinstance(x, ast.Assign)
             for _tg in x.targets
             if isinstance(_tg, ast.Name) and _tg.id.isupper() and 'STATE_BROKEN' in _tg.id]
check('2f 未新增模块级大写常量', not _newconst,
      '新增=%s' % [x.id for x in _newconst])

# ============ 汇总 ============
print('\n' + '=' * 70)
_np = sum(1 for _, c, _ in RESULT if c)
print('干跑结果: %d/%d PASS' % (_np, len(RESULT)))
_fail = [n for n, c, _ in RESULT if not c]
if _fail:
    print('FAILED:', _fail)
print('=' * 70)
sys.exit(0 if not _fail else 1)
