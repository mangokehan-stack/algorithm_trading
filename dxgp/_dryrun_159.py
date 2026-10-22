# -*- coding: utf-8 -*-
"""V2.6.159 干跑: ⑤止盈口径 / ⑦情绪重启死锁 / ⑨委托号双向 / ⑩死代码清理。
真实模块装载, 不注入模块桩。
"""
import sys, os, io, ast, types, tempfile, datetime, textwrap

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
RAW = open(P, 'rb').read().decode('gbk')
SRC = RAW.replace('\r\n', '\n')
LINES = SRC.split('\n')

TMP = tempfile.mkdtemp(prefix='dry159_')
os.chdir(TMP)
print('临时目录 =', TMP)

M = types.ModuleType('strat')
exec(compile(SRC, '<strat>', 'exec'), M.__dict__)
print('装载 OK, VERSION =', M.VERSION)

RES = []


def check(name, cond, detail=''):
    RES.append((name, bool(cond), detail))
    print(('PASS ' if cond else 'FAIL ') + name + (('  | ' + detail) if detail else ''))


# ============================================================
# ⑤ 止盈滞涨确认
# ============================================================
print('\n' + '=' * 72)
print('⑤ 放量止盈的滞涨确认(方案B: 只看未创新高, 涨幅仅兜底)')
print('=' * 72)
M.G.today = '20261021'
M.G.hist = {'601595.SH': [
    {'date': '20261016', 'high': 10.70},
    {'date': '20261017', 'high': 10.80},
    {'date': '20261020', 'high': 10.60},
]}
HI = 10.80
print('     近5日最高(已完成日线) = %.2f, 昨收 = 10.00' % HI)

cases = [
    ('涨5.00%但没超前高(旧版会拒绝卖)', 10.50, True),
    ('涨10.0%且已超前高', 11.00, False),
    ('涨0.50%且没超前高', 10.05, True),
    ('涨2.00%且没超前高(旧版拒绝)', 10.20, True),
]
for _desc, _lp, _exp in cases:
    _r, _note, _deg = M.sell_stall_confirmed('601595.SH', {}, _lp, {'lastClose': 10.00})
    check('5-%-30s' % _desc, _r is _exp, 'lp=%.2f 确认=%s 降级=%s | %s' % (_lp, _r, _deg, _note))

# 高点正好等于现价(严格不创新高)
_r, _n, _d = M.sell_stall_confirmed('601595.SH', {}, HI, {'lastClose': 10.00})
check('5-现价正好等于近高时不确认(严格小于)', _r is False, _n)

# 近高取不到 -> 用涨幅兜底
M.G.hist = {}
_r1, _n1, _d1 = M.sell_stall_confirmed('601595.SH', {}, 10.05, {'lastClose': 10.00})
check('5-近高缺失+涨0.5% -> 用涨幅兜底通过', _r1 is True, _n1)
_r2, _n2, _d2 = M.sell_stall_confirmed('601595.SH', {}, 10.50, {'lastClose': 10.00})
check('5-近高缺失+涨5.0% -> 涨幅兜底拒绝', _r2 is False, _n2)

# 昨收缺失 -> 降级放行(退回纯量能口径)
M.G.hist = {}
_r3, _n3, _d3 = M.sell_stall_confirmed('601595.SH', {}, 10.50, {})
check('5-昨收取不到 -> 降级退回纯量能口径', _r3 is True and _d3 is True, '说明=%r' % _n3)

# 旧口径对照: 同一场景旧版会怎么判
_gain = 10.50 / 10.00 - 1.0
_old_would = (_gain <= 0.01) and (10.50 < HI)
check('5-对照: 旧口径对"涨5%%未创新高"判不卖', _old_would is False,
      '旧口径要 涨幅<=1%% 且 未创新高, 涨幅5%% 直接否决')
check('5-铁律二未动: 卖出仍要求盈利', 'if profitable:' in RAW and 'is_at_loss' in RAW)

# ============================================================
# ⑦ 情绪 bootstrap 死锁
# ============================================================
print('\n' + '=' * 72)
print('⑦ 启动时刷新标记与信号本体同进同出')
print('=' * 72)
M.G.today = '20261021'
TODAY = '20261021'


def _boot_case(desc, state, ready_flag, expect_ready, expect_fetch):
    M.SENT_STATE.clear()
    M.SENT_STATE.update(state)
    M._SENTIMENT_READY = ready_flag
    M.sent_bootstrap()
    _r = bool(M._SENTIMENT_READY)
    _fd = M.SENT_STATE.get('last_fetch_date')
    ok = (_r is expect_ready) and (
        (bool(_fd) is bool(expect_fetch)))
    check('7-%s' % desc, ok,
          '就绪=%s(期望%s) 刷新标记=%r | 情绪值=%r'
          % (_r, expect_ready, _fd, M.SENT_STATE.get('sentiment')))


FULL = {'ready': True, 'last_fetch_date': TODAY, 'date': TODAY,
        'sentiment': -1.16, 'regime': 'panic', 'gate_skip': True,
        'size_mult': 0.5, 'overrides': {'BUY_MIN_ELAPSED_MIN': 45},
        'events': {}, 'carried': False, 'last_sig_ts': 1.0}
_boot_case('信号完整 -> 恢复就绪且不重取', dict(FULL), True, True, True)
_boot_case('只有标记没有信号(旧版死锁场景) -> 丢标记重取',
           {'last_fetch_date': TODAY, 'date': TODAY}, False, False, False)
_boot_case('标记与信号都没有 -> 正常重取', {}, False, False, False)
_boot_case('信号完整但昨天刷的 -> 丢标记重取',
           dict(FULL, last_fetch_date='20261020', date='20261020'), True, False, False)
_boot_case('标记是今天但当时未就绪 -> 丢标记重取',
           dict(FULL), False, False, False)

# 恢复后 sent_daily_refresh 不会重复取数
M.SENT_STATE.clear()
M.SENT_STATE.update(dict(FULL))
M._SENTIMENT_READY = True
M.sent_bootstrap()
check('7-恢复后 last_fetch_date 仍是今天(调度不会重取)',
      M.SENT_STATE.get('last_fetch_date') == TODAY and M._SENTIMENT_READY is True,
      'last_fetch_date=%r' % M.SENT_STATE.get('last_fetch_date'))

# ============================================================
# ⑨ 委托号按方向分别登记
# ============================================================
print('\n' + '=' * 72)
print('⑨ 委托号登记表买卖不再互相覆盖')
print('=' * 72)
M.G.state = {'ordids': {}, 'hold': {}}
CODE = '601595.SH'
M.note_order_id(CODE, 'BUY|涨停缩量低吸', '1001')
M.note_order_id(CODE, 'SELL|涨停缩量低吸', '2002')
_v = M.G.state['ordids'][CODE]
check('9a 买与卖两条登记并存',
      isinstance(_v.get('buy'), dict) and isinstance(_v.get('sell'), dict)
      and _v['buy'].get('id') == '1001' and _v['sell'].get('id') == '2002',
      repr(_v)[:120])
check('9b 按方向取买', M._oid_rec(CODE, 'buy').get('id') == '1001')
check('9c 按方向取卖', M._oid_rec(CODE, 'sell').get('id') == '2002')
check('9d 按委托号反查买方向', M._oid_side_of(CODE, '1001') == 'buy')
check('9e 按委托号反查卖方向', M._oid_side_of(CODE, '2002') == 'sell')
check('9f 陌生委托号反查为空', M._oid_side_of(CODE, '9999') == '')


class _Ord(object):
    def __init__(self, rm, tag=''):
        self.m_strRemark = rm
        self.m_strStrategyName = tag
        self.m_strInstrumentID = '601595'
        self.m_strExchangeID = 'SH'


# 备注为空时按方向兜底 —— 旧版这里会拿到反方向
check('9g 备注为空+查买方向 -> 判为本策略买单',
      M._own_order(_Ord(''), CODE, 'buy') is True)
check('9h 备注为空+查卖方向 -> 判为本策略卖单',
      M._own_order(_Ord(''), CODE, 'sell') is True)

# 旧结构兼容(模拟 V2.6.158 落盘的状态文件)
M.G.state = {'ordids': {CODE: {'side': 'sell', 'id': '2002', 'ts': 1.0}}, 'hold': {}}
check('9i 旧结构: 取卖方向能读到',
      M._oid_rec(CODE, 'sell').get('id') == '2002')
check('9j 旧结构: 取买方向读不到(不串方向)',
      M._oid_rec(CODE, 'buy') == {})
check('9k 旧结构: 按号反查仍可用',
      M._oid_side_of(CODE, '2002') == 'sell')
# 旧结构上再写一笔买 -> 自动迁移, 旧的卖保留
M.note_order_id(CODE, 'BUY|涨停缩量低吸', '3003')
_v2 = M.G.state['ordids'][CODE]
check('9l 旧结构升级: 老的卖单被保留、新的买单并存',
      _v2.get('sell', {}).get('id') == '2002' and _v2.get('buy', {}).get('id') == '3003',
      repr(_v2)[:120])
check('9m 对账用"任一方向登记即放行"',
      M._oid_known(CODE, '2002') and M._oid_known(CODE, '3003')
      and not M._oid_known(CODE, '9999'))

# ============================================================
# ⑩ 死代码清理
# ============================================================
print('\n' + '=' * 72)
print('⑩ 死代码清理')
print('=' * 72)
check('10a 不可达 return data 已删(按函数体判, 不扫全文)',
      RAW.count('    return data\n') == 0 and RAW.count('    return data\r\n') == 0,
      '整行缩进4空格的 return data 剩余 %d 处'
      % (RAW.count('    return data\n') + RAW.count('    return data\r\n')))
check('10b 只写不读的就绪字段已全删', "SENT_STATE['ready']" not in RAW,
      '剩余 %d 处' % RAW.count("SENT_STATE['ready']"))
check('10c 注释与代码不符处已改准(正向判新注释在位)',
      '此处按实际行为改注释, 不动判据' in RAW)
# _auto_risk_exclude 里只剩两个 return
_t = ast.parse(SRC)
_ok = True
for _n in _t.body:
    if isinstance(_n, ast.FunctionDef) and _n.name == '_auto_risk_exclude':
        _rs = [x.lineno for x in ast.walk(_n) if isinstance(x, ast.Return)]
        _ok = len(_rs) == 2
check('10d _auto_risk_exclude 只剩 True/False 两个返回', _ok)

# ============================================================
# 铁律与指纹回归
# ============================================================
print('\n' + '=' * 72)
n_stop = sum(1 for x in ast.walk(_t) if isinstance(x, ast.Attribute) and x.attr == 'stop_order')
n_stop += sum(1 for x in ast.walk(_t) if isinstance(x, ast.Name) and x.id == 'stop_order')
check('铁律一: 止损单引用为 0', n_stop == 0, '实际 %d' % n_stop)
check('铁律一: NEVER_STOP_LOSS 仍为 True', 'NEVER_STOP_LOSS = True' in RAW)

print('\n' + '=' * 72)
_np = sum(1 for _, c, _ in RES if c)
print('干跑结果: %d/%d PASS' % (_np, len(RES)))
_f = [n for n, c, _ in RES if not c]
if _f:
    print('FAILED:', _f)
print('=' * 72)
sys.exit(0 if not _f else 1)
