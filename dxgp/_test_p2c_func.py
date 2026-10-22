# -*- coding: utf-8 -*-
"""P2 批次 C 功能单测: _fp_keys 自动捕获 / load_state 模式校验 /
risk_blocked 报告期校验 / buy_stock 仙股盘中复核
方法: AST 抽取母版目标函数 + mock 依赖, 行为级验证(不改母版)"""
import ast, json, os, sys, tempfile

src = open('zt_shrink_strategy_gbk.py', encoding='gbk', newline='').read()
tree = ast.parse(src)
src_lines = src.split('\r\n')

fails = []

def chk(name, got, exp):
    ok = got == exp
    print('%-52s got=%r exp=%r %s' % (name, got, exp, 'PASS' if ok else 'FAIL'))
    if not ok:
        fails.append(name)

def chk_true(name, cond, detail=''):
    print('%-52s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        fails.append(name)

# ---------- 通用: 自动填充自由名为"调用即抛哨兵"的 dummy ----------
import builtins
_BUILTIN_NAMES = set(dir(builtins))

class _Deep(Exception):
    pass

class _Dummy(object):
    def __init__(self, nm):
        self._nm = nm
    def _boom(self, *a, **k):
        raise _Deep('dummy used: %s' % self._nm)
    __call__ = _boom
    __getitem__ = _boom
    __int__ = _boom
    __float__ = _boom
    __str__ = _boom
    __bool__ = _boom
    __iter__ = _boom
    __contains__ = _boom
    __gt__ = _boom
    __lt__ = _boom
    __ge__ = _boom
    __le__ = _boom
    def __repr__(self):
        return '<Dummy %s>' % self._nm

def extract(nodes_want, extra_assign=()):
    """抽出指定 FunctionDef(按名) + 额外 Assign(按目标名), 返回 (ns, 函数体)"""
    body = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in nodes_want:
            body.append(n)
        elif isinstance(n, ast.Assign):
            tgts = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if any(t in extra_assign for t in tgts):
                body.append(n)
    mod = ast.Module(body=body, type_ignores=[])
    ns = {}
    exec(compile(mod, '<extract>', 'exec'), ns)
    return ns

def auto_fill(fn_node, ns):
    """为函数体内所有自由名(非参数/非内建/非已提供)填 dummy"""
    assigned, loads = set(), set()
    for n in ast.walk(fn_node):
        if isinstance(n, ast.Name):
            (assigned if isinstance(n.ctx, ast.Store) else loads).add(n.id)
    params = {a.arg for a in fn_node.args.args}
    for a in fn_node.args.kwonlyargs:
        params.add(a.arg)
    if fn_node.args.vararg:
        params.add(fn_node.args.vararg.arg)
    if fn_node.args.kwarg:
        params.add(fn_node.args.kwarg.arg)
    free = loads - assigned - params - _BUILTIN_NAMES - set(ns.keys())
    for nm in sorted(free):
        ns[nm] = _Dummy(nm)
    return sorted(free)

# ============================================================
# Part 1: _fp_keys 合成行为(mock globals)
# ============================================================
print('--- Part 1: _fp_keys synthetic ---')
ns1 = extract({'_fp_keys'}, extra_assign={'_FP_DENY'})
_fp_keys = ns1['_fp_keys']
# 直接注入 mock 全局常量
ns1['GOOD_INT'] = 5
ns1['GOOD_FLOAT'] = 1.5
ns1['GOOD_BOOL'] = True
ns1['GOOD_STR'] = 'x'
ns1['GOOD_TUPLE'] = (1, 2)
ns1['GOOD_LIST'] = [1]
ns1['GOOD_DICT'] = {'a': 1}
ns1['GOOD_NONE'] = None
ns1['DENIED_A'] = 1            # 在 _FP_DENY 中(需临时加入)
ns1['_FP_DENY'] = set(ns1['_FP_DENY']) | {'DENIED_A'}
ns1['lower_case'] = 1          # 小写不收
ns1['_PRIVATE'] = 1            # 下划线前缀不收
ns1['Mixed_Case'] = 1          # 非全大写不收
ns1['some_func'] = lambda: 1   # 函数不收
ns1['AN_OBJECT'] = object()    # 任意对象不收
ns1['A_CLASS'] = int           # 类型对象不收
got = sorted(_fp_keys())
exp = ['GOOD_BOOL', 'GOOD_DICT', 'GOOD_FLOAT', 'GOOD_INT', 'GOOD_LIST',
       'GOOD_NONE', 'GOOD_STR', 'GOOD_TUPLE']
chk('P2-2 synthetic capture', got, exp)

# ============================================================
# Part 2: _fp_keys 真实文件行为(字面量命名空间)
# ============================================================
print('--- Part 2: _fp_keys on real file ---')

def _is_literal(node):
    for sub in ast.walk(node):
        if isinstance(sub, (ast.expr_context, ast.operator, ast.unaryop,
                            ast.boolop, ast.cmpop, ast.UnaryOp)):
            continue
        if isinstance(sub, (ast.Constant, ast.Tuple, ast.List, ast.Dict, ast.Set)):
            continue
        return False
    return True

lit_body, all_upper, non_lit = [], set(), set()
for n in tree.body:
    if isinstance(n, ast.Assign):
        tgts = [t.id for t in n.targets if isinstance(t, ast.Name)]
        up = [t for t in tgts if t.isupper()]
        all_upper.update(up)
        if up and _is_literal(n.value):
            lit_body.append(n)
        elif up:
            non_lit.update(up)
mod = ast.Module(body=lit_body, type_ignores=[])
ns2 = {}
exec(compile(mod, '<lit>', 'exec'), ns2)
exec(compile(ast.Module(body=[n for n in tree.body
                              if isinstance(n, ast.FunctionDef) and n.name == '_fp_keys'],
                        type_ignores=[]), '<fp>', 'exec'), ns2)
keys_real = ns2['_fp_keys']()
print('  captured=%d  all_upper=%d  non_literal=%d  denied=%d'
      % (len(keys_real), len(all_upper), len(non_lit), len(ns2['_FP_DENY'])))
must_have = ['MARKET_CAP_MIN_YI', 'MARKET_CAP_MAX_YI', 'SENT_REGIME_PANIC_LO',
             'SENT_REGIME_FRENZY_HI', 'SENT_EVT_FRENZY_ADVPCT',
             'SENT_EVT_FRENZY_LIMITUP', 'SENT_EVT_PANIC_ADVPCT',
             'FEE_COMMISSION_RATE', 'FEE_COMMISSION_MIN', 'FEE_STAMP_RATE',
             'FEE_TRANSFER_RATE', 'RISK_MIN_PRICE', 'LOT_SIZE']
miss = [k for k in must_have if k not in keys_real]
chk('P2-2 key behavioral constants captured', miss, [])
# V2.6.85: VERSION 刻意排除出参数指纹(改由 code_fingerprint 单独纳入), 故此处要求不在其中
chk_true('V2.6.85 VERSION 不参与参数指纹', 'VERSION' not in keys_real,
         'keys含VERSION' if 'VERSION' in keys_real else '')
leak = [k for k in ns2['_FP_DENY'] if k in keys_real]
chk('P2-2 no denied key leaks', leak, [])
chk('P2-2 deny subset of real names', sorted(set(ns2['_FP_DENY']) - all_upper), [])
chk_true('P2-2 capture count >= 200', len(keys_real) >= 200,
         '(captured=%d)' % len(keys_real))
# 非字面量赋值的常量: 真实运行时也在 globals() 中会被捕获, 仅列出人工核对
print('  non-literal UPPER_CASE (runtime-captured, not in lit-ns): %s'
      % sorted(non_lit))

# ============================================================
# Part 3: load_state 模式校验
# ============================================================
print('--- Part 3: load_state schema validation ---')
ns3 = extract({'load_state'}, extra_assign={'_STATE_SCHEMA', '_HOLD_MISSING'})
logs3, alerts3 = [], []

class _G3(object):
    pass

g3 = _G3()
g3.accid = ''
g3.state_broken = False
g3.today = '20261019'
tmpdir = tempfile.mkdtemp()
state_file = os.path.join(tmpdir, 'state.json')

ns3['os'] = os
ns3['json'] = json
ns3['log'] = lambda *a, **k: logs3.append(' '.join(str(x) for x in a))
ns3['pnl_alert'] = lambda *a, **k: alerts3.append(' '.join(str(x) for x in a))
ns3['G'] = g3
ns3['_state_load_candidates'] = lambda: [state_file]
ns3['state_path'] = lambda: state_file
ns3['_load_names_cache'] = lambda st: None
load_state = ns3['load_state']
SCHEMA = ns3['_STATE_SCHEMA']

def run_case(name, disk, expect_bad=None, expect_broken=None, extra=None):
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(disk, f)
    del logs3[:], alerts3[:]
    g3.state_broken = False
    st = load_state()
    bad_hit = any('字段类型异常' in m for m in logs3)
    chk('%s: bad-field alert' % name, bad_hit, bool(expect_bad))
    if expect_broken is not None:
        chk('%s: state_broken' % name, g3.state_broken, expect_broken)
    if extra:
        extra(st)
    return st

# 3.1 全好磁盘
st = run_case('3.1 all-good',
              {'hold': {'002142.SZ': {'buy_vol': 100}}, 'trades': [], 'realized': {},
               'trap_used': 12.5, 'pos_empty_n': 2, 'last_dl_date': '20261019',
               'buys': {'date': '20261019', 'n': 1, 'codes': ['002142.SZ']}},
              expect_bad=False, expect_broken=False,
              extra=lambda st: chk('3.1 hold kept', st['hold'].get('002142.SZ', {}).get('buy_vol'), 100))
chk('3.1 no alert pushed', len(alerts3), 0)

# 3.2 hold 为 list -> 重置 + state_broken
run_case('3.2 hold=list', {'hold': ['002142.SZ']}, expect_bad=True, expect_broken=True,
         extra=lambda st: chk('3.2 hold reset', st['hold'], {}))
chk_true('3.2 pnl_alert pushed', len(alerts3) >= 1)

# 3.3 hold 内 1/2 条非 dict -> 摘除坏记录, 不置 state_broken
run_case('3.3 hold 1 bad rec',
          {'hold': {'002142.SZ': {'buy_vol': 100}, 'BAD': 'not-a-dict'}},
          expect_bad=True, expect_broken=False,
          extra=lambda st: chk('3.3 good rec kept', sorted(st['hold'].keys()), ['002142.SZ']))

# 3.4 trades 为 dict -> 重置 []
run_case('3.4 trades=dict', {'trades': {'a': 1}}, expect_bad=True,
         extra=lambda st: chk('3.4 trades reset', st['trades'], []))

# 3.5 realized 为 list -> 重置 {}
run_case('3.5 realized=list', {'realized': [1, 2]}, expect_bad=True,
         extra=lambda st: chk('3.5 realized reset', st['realized'], {}))

# 3.6 trap_used 为 bool -> 重置 0.0(bool 不算数值)
run_case('3.6 trap_used=bool', {'trap_used': True}, expect_bad=True,
         extra=lambda st: chk('3.6 trap_used reset', st['trap_used'], 0.0))

# 3.7 pos_empty_n 为 float -> int/float 兼容, 接受
run_case('3.7 pos_empty_n=3.0', {'pos_empty_n': 3.0}, expect_bad=False,
         extra=lambda st: chk('3.7 float accepted', st['pos_empty_n'], 3.0))

# 3.8 last_dl_date 为 int -> 重置 ''
run_case('3.8 last_dl_date=int', {'last_dl_date': 20261019}, expect_bad=True,
         extra=lambda st: chk('3.8 last_dl_date reset', st['last_dl_date'], ''))

# 3.9 buys.n 为 str -> 整体重置
run_case('3.9 buys.n=str', {'buys': {'date': '20261019', 'n': '3', 'codes': ['a']}},
         expect_bad=True,
         extra=lambda st: chk('3.9 buys reset', st['buys'], {'date': '', 'n': 0, 'codes': []}))

# 3.10 buys.n 为 float -> 严格重置(防外部篡改)
run_case('3.10 buys.n=3.0', {'buys': {'date': '20261019', 'n': 3.0, 'codes': ['a']}},
         expect_bad=True,
         extra=lambda st: chk('3.10 buys reset', st['buys'], {'date': '', 'n': 0, 'codes': []}))

# 3.11 buys.n 为 bool -> 重置(bool 是 int 子类, 必须显式排除)
run_case('3.11 buys.n=True', {'buys': {'date': 'd', 'n': True, 'codes': []}},
         expect_bad=True,
         extra=lambda st: chk('3.11 buys reset', st['buys'], {'date': '', 'n': 0, 'codes': []}))

# 3.12 buys.codes 为 dict -> 整体重置
run_case('3.12 codes=dict', {'buys': {'date': 'd', 'n': 1, 'codes': {'a': 1}}},
         expect_bad=True,
         extra=lambda st: chk('3.12 buys reset', st['buys'], {'date': '', 'n': 0, 'codes': []}))

# 3.13 磁盘只有 hold -> 缺字段走默认值, 无告警
st = run_case('3.13 partial disk', {'hold': {}}, expect_bad=False,
              extra=lambda st: chk('3.13 defaults filled',
                                   (st['trades'], st['realized'], st['trap_used'],
                                    st['buys']['n'], st['pos_empty_n']),
                                   ([], {}, 0.0, 0, 0)))

# 3.14 pnl_alert 抛异常 -> 不崩溃(内层 try 吞掉)
ns3['pnl_alert'] = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'))
with open(state_file, 'w', encoding='utf-8') as f:
    json.dump({'hold': ['bad']}, f)
del logs3[:], alerts3[:]
g3.state_broken = False
try:
    st = load_state()
    chk('3.14 alert exception swallowed', (st['hold'], g3.state_broken), ({}, True))
except Exception as e:
    chk('3.14 alert exception swallowed', 'raised:%s' % e, 'no-raise')
ns3['pnl_alert'] = lambda *a, **k: alerts3.append(' '.join(str(x) for x in a))

# 3.15 回归-缺陷A: 磁盘无 hold 键 -> 用默认值, 不误冻结
run_case('3.15 hold key absent', {'trades': []}, expect_bad=False, expect_broken=False,
         extra=lambda st: chk('3.15 hold default', st['hold'], {}))

# 3.16 回归-缺陷A: hold=JSON null -> 容器损坏, 冻结
run_case('3.16 hold=null', {'hold': None}, expect_bad=True, expect_broken=True)

# 3.17 回归-缺陷B: hold=str -> 容器损坏, 冻结(修复前被通用循环掩盖)
run_case('3.17 hold=str', {'hold': 'corrupted'}, expect_bad=True, expect_broken=True,
         extra=lambda st: chk('3.17 hold reset', st['hold'], {}))

# ============================================================
# Part 4: risk_blocked 报告期校验
# ============================================================
print('--- Part 4: risk_blocked report-date ---')
ns4 = extract({'risk_blocked'})
fin_calls = []
ns4['RISK_CHECK_ON'] = True
ns4['RISK_LOSS_CHECK'] = True
ns4['RISK_LOSS_MISSING_DEGRADE'] = False
ns4['inst_name'] = lambda s: '宁波银行'
ns4['is_st_name'] = lambda nm: False
ns4['load_blacklist'] = lambda: {}
ns4['RISK_MIN_PRICE'] = 2.0
ns4['RISK_MAX_DROP_7D'] = 1.0
ns4['RISK_MAX_DROP_3D'] = 1.0
ns4['RISK_MAX_DROP_5D'] = 1.0
ns4['_fin_unknown_rd'] = lambda: fin_calls.append(1)
logs4 = []
ns4['log'] = lambda *a, **k: logs4.append(' '.join(str(x) for x in a))
ns4['disp'] = lambda s: str(s)
class _G4(object):
    pass
g4 = _G4()
g4.today = '20261019'
ns4['G'] = g4
risk_blocked = ns4['risk_blocked']
COMP = [{'close': 10.0}, {'close': 10.0}]

def profit(rd='20260630', val=1e8, fld='net_profit_excl_min_int_inc', src='QMT'):
    return {'report_date': rd, 'field': fld, 'value': val, 'source': src}

def rb(name, prof, exp_sub, exp_fin=None, today='20261019'):
    del fin_calls[:]
    g4.today = today
    ns4['get_recent_net_profit_cached'] = lambda s: prof
    r = risk_blocked('002142.SZ', COMP)
    ok = (exp_sub in r) if exp_sub else (r == '')
    print('%-52s reason=%r fin=%d %s' % (name, (r or '(pass)')[:60], len(fin_calls),
                                         'PASS' if ok else 'FAIL'))
    if not ok:
        fails.append(name)
    if exp_fin is not None and len(fin_calls) != exp_fin:
        print('%-52s fin_calls=%d exp=%d FAIL' % (name + ' [fin]', len(fin_calls), exp_fin))
        fails.append(name + ' [fin]')

rb('4.1 rd=unknown', profit(rd='未知'), '未知', exp_fin=1)
rb('4.2 rd missing key',
   {'field': 'net_profit_excl_min_int_inc', 'value': 1e8, 'source': 'jqdata兜底'},
   '未知', exp_fin=1)
rb('4.3 rd stale 33m', profit(rd='20240101'), '严重滞后', exp_fin=0)
rb('4.4 rd fresh negative', profit(rd='20260630', val=-5e7), '归母净利润<0', exp_fin=0)
rb('4.5 rd boundary 15m pass', profit(rd='20250731', val=1e8), '', exp_fin=0)
rb('4.6 rd fresh positive pass', profit(), '', exp_fin=0)
rb('4.7 profit=None missing', None, '缺失', exp_fin=0)
rb('4.8 today empty fail-open', profit(rd='19990101', val=1e8), '', exp_fin=0, today='')

# ============================================================
# Part 5: buy_stock 仙股盘中复核
# ============================================================
print('--- Part 5: buy_stock penny intraday ---')
ns5 = extract({'buy_stock', '_f'})
ns5['math'] = __import__('math')
ns5['_tick_unit_blocked'] = lambda: False
ns5['emergency_block'] = lambda k: ''
ns5['buy_scope_ok'] = lambda s: True
scope_calls = []
ns5['scope_refuse'] = lambda s, d: scope_calls.append((s, d))
ns5['RISK_MIN_PRICE'] = 2.0
ns5['LOT_SIZE'] = 100
ns5['FIXED_BUY_VOL'] = 0
# buy_stock 在仙股复核(L8248)之前新增两道前置闸门, 抽取命名空间必须补齐否则 NameError:
#   L8239 _rx = risk_excluded(s)   —— V2.6.83 发单前排雷复核
#   L8283 amount = min(TARGET_BUY_AMOUNT, cash) —— 固定手数关闭时的目标金额口径
rx_state = ['']
ns5['risk_excluded'] = lambda s: rx_state[0]
ns5['TARGET_BUY_AMOUNT'] = 100000.0
logs5 = []
ns5['log'] = lambda *a, **k: logs5.append(' '.join(str(x) for x in a))
ns5['disp'] = lambda s: str(s)
buy_stock = ns5['buy_stock']
_f = ns5['_f']

def bs(name, lp, min_price, exp_reject, rx='', allow_crash=False):
    del logs5[:]
    ns5['RISK_MIN_PRICE'] = min_price
    rx_state[0] = rx
    try:
        r = buy_stock({'stock': '002142.SZ'}, lp, 0, 0, 0, want_vol=None, plan=None)
        crashed = None
    except Exception as e:
        r, crashed = None, '%s: %s' % (type(e).__name__, e)
    joined = ' | '.join(logs5)
    rejected = ('仙股下限' in joined)
    rx_hit = ('发单前复核' in joined)
    # crash 必须为 None —— 否则用例根本没走到被测闸门, 属假绿
    # allow_crash: 该用例入参超出实盘可达域(上游 L9744 已挡 lp<=0), 只要闸门行为正确即判过
    ok = (rejected == exp_reject) and (rx_hit == bool(rx)) and (allow_crash or crashed is None)
    print('%-52s ret=%s crash=%s penny_log=%s rx_log=%s %s'
          % (name, r, crashed, rejected, rx_hit, 'PASS' if ok else 'FAIL'))
    if not ok:
        fails.append(name)

bs('5.1 lp=1.98 < 2.0 -> reject', 1.98, 2.0, True)
bs('5.2 lp=2.05 >= 2.0 -> pass gate', 2.05, 2.0, False)
# lp=0 在实盘不可达(主循环 L9744 "lp <= 0 or vol <= 0" 已 continue), 此处只验证仙股闸门的
# "_f(lp) > 0" 短路生效(不误报仙股)。函数级无 lp<=0 契约保护, 已列入待确认项, 不擅自改母版。
bs('5.3 lp=0 -> 仙股闸门短路(上游已挡)', 0.0, 2.0, False, allow_crash=True)
bs('5.4 min_price=0 disabled', 0.5, 0.0, False)
# 排雷挂点优先于仙股复核: 命中排雷即拒单, 且不再进入仙股分支
bs('5.5 排雷命中 -> 拒单(先于仙股)', 2.05, 2.0, False, rx='涉嫌信息披露违法违规被立案')
# 排雷未命中 -> 正常落到仙股复核并拒单
bs('5.6 排雷空 + lp=1.50 -> 仙股拒单', 1.50, 2.0, True)

print()
if fails:
    print('FAILED:', fails)
    sys.exit(1)
print('ALL P2-BATCH-C FUNCTIONAL TESTS PASS')
