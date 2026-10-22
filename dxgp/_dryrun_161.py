# -*- coding: utf-8 -*-
"""V2.6.161 干跑: 第14轮审计修复(投资金额突破上限)端到端实测。
原则: 真实模块从 GBK 母版解码后整体 exec, 不注入被测代码桩;
      buy_stock 全链路真跑(守卫->新手数计算->占位->DRY_RUN 模拟成交->记账);
      仅对【上游依赖】(_slippage_for/SIM_*概率)做受控设置以覆盖特定分支。
修正记录(首轮跑挂后的测试自身缺陷):
  ① 日志捕获原先只取 log() 第一个参数(显示名), 漏掉消息正文 -> 改全参数拼接
  ② 前一用例 buy_stock 的 save_state 把状态写进临时目录, 后续 load_state 装载
     -> 每例 fresh() 先删状态文件再装载, 并断言 used_capital()==0 防泄漏
  ③ 期望值错误: F2 手数应是 2000(20000/10/100=20手); 组合帽算出来 0 股时
     正确行为是拒单(不足一手)而非"削平到0"
"""
import sys, os, io, types, tempfile, traceback, ast

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
RAW = open(P, 'rb').read().decode('gbk')
SRC = RAW.replace('\r\n', '\n')

TMP = tempfile.mkdtemp(prefix='dry161_')
os.chdir(TMP)
print('临时目录 =', TMP)

M = types.ModuleType('strat')
exec(compile(SRC, '<strat>', 'exec'), M.__dict__)
print('装载 OK, VERSION =', M.VERSION)

# 记录被用例临时改写的上游参数原值, fresh() 时恢复
_ORIG = {k: getattr(M, k) for k in ('TARGET_BUY_AMOUNT', 'FIXED_BUY_VOL',
                                    'STRATEGY_CASH_CAP', 'SIM_FILL_PROB',
                                    'SIM_DRY_FILL_PROB', 'SIM_PARTIAL_FILL_ON')}

RES = []


def check(name, cond, detail=''):
    RES.append((name, bool(cond), detail))
    print(('PASS ' if cond else 'FAIL ') + name + (('  | ' + detail) if detail else ''))


S = '601595.SH'


def fresh(**over):
    """每个用例全新状态: 删状态文件 -> 真 load_state -> 最小 G 就绪集 -> 恢复上游参数原值"""
    for k, v in _ORIG.items():
        setattr(M, k, v)
    try:
        _sp = M.state_path()
        if os.path.exists(_sp):
            os.remove(_sp)
    except Exception:
        pass
    M.G.state = M.load_state()
    M.G.today = '20261022'
    M.G.ready = True
    M.G.C = object()
    M.G.accid = ''
    M.G.state_broken = False
    M.G.candidates = [{'stock': S, 'name': '上海电影', 't0': 'T0',
                       'base_vol': 100000, 'zt_close': 11.0, 'offset': 1}]
    M.G.prev_close = {S: 10.00}
    M.G.hist = {S: [{'date': '20261021', 'close': 10.00, 'vol': 100000,
                     'high': 10.20, 'low': 9.90, 'open': 10.00}]}
    # 上游依赖受控设置(覆盖 DRY_RUN 分支, 消除随机未命中)
    M.DRY_RUN = True
    M.SIM_FILL_PROB = 1.0
    M.SIM_DRY_FILL_PROB = 1.0
    M.SIM_PARTIAL_FILL_ON = False
    for k, v in over.items():
        setattr(M, k, v)
    return M.G.state


LOGS = []


def cap_log(*a, **k):
    try:
        LOGS.append(' '.join(str(x) for x in a))
    except Exception:
        pass


M.log = cap_log


def run_buy(lp, want_vol=None, cash=10_000_000.0):
    LOGS.clear()
    c = {'stock': S, 'name': '上海电影', 't0': 'T0', 'base_vol': 100000,
         'zt_close': 11.0, 'offset': 1}
    try:
        r = M.buy_stock(c, lp, 50000.0, 0.5, cash, want_vol=want_vol)
        return r, list(LOGS)
    except Exception:
        traceback.print_exc()
        return '<EXC>', list(LOGS)


def clip_line(logs, kind):
    for l in logs:
        if kind in l and '超过仓位帽, 削平为' in l:
            return l
    return ''


print('\n' + '=' * 72)
print('A~D  want_vol 动态手数分支: 双帽兜底(单票绝对额度 + 组合剩余额度)')
print('=' * 72)

# ---- A: 帽内不变 ----
fresh()
check('A0 隔离: 初始 used_capital=0', M.used_capital() == 0, 'used=%s' % M.used_capital())
r, lg = run_buy(10.00, want_vol=6000)
h = M.G.state['hold'].get(S, {})
check('A1 帽内(6000股@10.00)照常成交, 返回6000', r == 6000, 'ret=%s' % r)
check('A2 无削平日志(只削不增)', not clip_line(lg, '动态'), clip_line(lg, '动态')[:60])
check('A3 占位持仓手数=6000', h.get('buy_vol') == 6000, 'buy_vol=%s' % h.get('buy_vol'))
check('A4 委托金额未超单票绝对额度', h.get('buy_vol', 0) * h.get('buy_price', 0)
      <= M.MAX_POS_VALUE_ABS + 0.01,
      '%.2f<=%.2f' % (h.get('buy_vol', 0) * h.get('buy_price', 0), M.MAX_POS_VALUE_ABS))

# ---- B: 超单票绝对额度 -> 削平 ----
fresh()
_px_g = M._round2(10.00 * (1.0 + M._slippage_for(10.00)))
_cap_abs = int(int(M.MAX_POS_VALUE_ABS / _px_g) / 100) * 100   # 与被测代码同一表达式
r, lg = run_buy(10.00, want_vol=8000)
h = M.G.state['hold'].get(S, {})
_c = clip_line(lg, '动态')
check('B1 超单票帽(8000股)削平为%d股' % _cap_abs, r == _cap_abs,
      'ret=%s 期望=%d' % (r, _cap_abs))
check('B2 削平日志出现且数字一致', ('削平为%d股' % _cap_abs) in _c, _c[:90])
check('B3 削平后金额仍在帽内', h.get('buy_vol', 0) * h.get('buy_price', 0)
      <= M.MAX_POS_VALUE_ABS + 0.01,
      '%.2f' % (h.get('buy_vol', 0) * h.get('buy_price', 0)))
check('B4 反证: 旧口径(不削)会突破单票帽', 8000 * _px_g > M.MAX_POS_VALUE_ABS,
      '旧口径超帽 %.2f 元' % (8000 * _px_g - M.MAX_POS_VALUE_ABS))

# ---- C: 组合剩余额度绑定 ----
fresh()
_hold_other = {'000001.SZ': {'name': '平安银行', 'buy_price': 150.0, 'buy_vol': 1000,
                             'fee': 100.0, 'cost_total': 150100.0, 'fill_vol': 1000,
                             'managed': True, 'exited': False, 'paper': True,
                             'buy_date': '20261020', 'fee_pre': 100.0,
                             'pend_vol': 0, 'order_ts': 0.0}}
M.G.state['hold'].update(_hold_other)
_used = M.used_capital()
_cl = M.abs_cap_left(_px_g)
_cap_combo = int(int(_cl) / 100) * 100
check('C0 隔离: used_capital=%.0f(仅注入仓), 组合帽=%.0f股' % (_used, _cl),
      abs(_used - 150100.0) < 1.0, 'used=%.2f' % _used)
r, lg = run_buy(10.00, want_vol=20000)
h = M.G.state['hold'].get(S, {})
_c = clip_line(lg, '动态')
check('C1 组合帽绑定: %d股 < 单票帽%d股' % (_cap_combo, _cap_abs),
      0 < _cap_combo < _cap_abs, '组合帽%d 单票帽%d' % (_cap_combo, _cap_abs))
check('C2 削平到组合帽%d股' % _cap_combo, r == _cap_combo,
      'ret=%s 期望=%d' % (r, _cap_combo))
check('C3 削平日志数字一致', ('削平为%d股' % _cap_combo) in _c, _c[:90])

# ---- D: 帽不足一手 -> 拒单且不留占位 ----
fresh()
M.G.state['hold'].update({'000001.SZ': {'name': '平安银行', 'buy_price': 199.9,
                                        'buy_vol': 1000, 'fee': 50.0,
                                        'cost_total': 199950.0, 'fill_vol': 1000,
                                        'managed': True, 'exited': False, 'paper': True,
                                        'buy_date': '20261020', 'fee_pre': 50.0,
                                        'pend_vol': 0, 'order_ts': 0.0}})
_cl_d = M.abs_cap_left(_px_g)
r, lg = run_buy(10.00, want_vol=6000)
check('D1 组合帽只剩 %.1f 股(不足一手)时拒单返回 None' % _cl_d,
      r is None and _cl_d < 100, 'ret=%s cap=%.2f' % (r, _cl_d))
check('D2 拒单日志说明不足一手', any('不足一手' in l for l in lg),
      str([l for l in lg if '不足一手' in l])[:90])
check('D3 拒单不留占位持仓', S not in M.G.state['hold'])

print('\n' + '=' * 72)
print('E~G  目标金额回退分支(else): 原本两帽全无, 现补同口径双帽')
print('=' * 72)

# ---- E: 超帽削平 ----
fresh(TARGET_BUY_AMOUNT=100000.0, FIXED_BUY_VOL=0)
_cv_e = int(int(M.MAX_POS_VALUE_ABS / _px_g) / 100) * 100
_amt_cap = _cv_e * _px_g
r, lg = run_buy(10.00, want_vol=None)
h = M.G.state['hold'].get(S, {})
_c = clip_line(lg, '目标金额')
check('E1 amount=100000 超帽, 削平为 %.0f 元' % _amt_cap,
      '削平为' in _c, _c[:90])
check('E2 削平后金额数字一致(%.0f)' % _amt_cap, ('削平为%.0f元' % _amt_cap) in _c, _c[:90])
check('E3 折算手数=%d股' % _cv_e, r == _cv_e, 'ret=%s' % r)
check('E4 委托金额未超单票绝对额度', h.get('buy_vol', 0) * h.get('buy_price', 0)
      <= M.MAX_POS_VALUE_ABS + 0.01,
      '%.2f' % (h.get('buy_vol', 0) * h.get('buy_price', 0)))

# ---- E5: 残余越界回归(干跑首轮实测翻车场景 lp=10.10) ----
fresh(TARGET_BUY_AMOUNT=100000.0, FIXED_BUY_VOL=0)
M.G.prev_close = {S: 10.00}
r, lg = run_buy(10.10, want_vol=None)
h = M.G.state['hold'].get(S, {})
_amt5 = h.get('buy_vol', 0) * h.get('buy_price', 0)
check('E5 lp=10.10 场景: 实收金额 %.2f 不超单票帽(补强前=66792.00, 超125.34元)' % _amt5,
      r is not None and _amt5 <= M.MAX_POS_VALUE_ABS + 0.01,
      'ret=%s vol=%s px=%s 金额=%.2f 帽=%.2f' % (r, h.get('buy_vol'), h.get('buy_price'),
                                            _amt5, M.MAX_POS_VALUE_ABS))

# ---- F: 帽内不变 ----
fresh(TARGET_BUY_AMOUNT=20000.0, FIXED_BUY_VOL=0)
r, lg = run_buy(10.00, want_vol=None)
check('F1 amount=20000 在帽内, 不削平', not clip_line(lg, '目标金额'),
      clip_line(lg, '目标金额')[:60])
check('F2 手数=2000股(20000/10/100=20手)', r == 2000, 'ret=%s' % r)

# ---- G: else 分支组合帽绑定 ----
fresh(TARGET_BUY_AMOUNT=100000.0, FIXED_BUY_VOL=0)
M.G.state['hold'].update(_hold_other)
_cv_g_g = int(int(M.abs_cap_left(_px_g)) / 100) * 100
_amt_cap_c = _cv_g_g * _px_g
r, lg = run_buy(10.00, want_vol=None)
_c = clip_line(lg, '目标金额')
check('G1 组合帽折算金额 %.0f 元削平' % _amt_cap_c,
      ('削平为%.0f元' % _amt_cap_c) in _c, _c[:90])
check('G2 折算手数=%d股' % _cv_g_g, r == _cv_g_g, 'ret=%s' % r)

print('\n' + '=' * 72)
print('H~J  分支覆盖: 低价股0.3%滑点 / 无组合帽(None) / 滑点价折算兜底')
print('=' * 72)

# ---- H: 低价股 0.3% 滑点(本修复的动机场景) ----
fresh()
_sl = M._slippage_for(9.80)
_px_g2 = M._round2(9.80 * (1.0 + _sl))
_cap_low = int(int(M.MAX_POS_VALUE_ABS / _px_g2) / 100) * 100
check('H1 lp=9.80 滑点率为 0.3%', abs(_sl - 0.003) < 1e-9, 'slip=%s' % _sl)
check('H2 折算滑点价=%.2f, 单票帽=%d股' % (_px_g2, _cap_low), _px_g2 > 9.80,
      'px_g=%.2f' % _px_g2)
r, lg = run_buy(9.80, want_vol=6000)
h = M.G.state['hold'].get(S, {})
check('H3 6000股在帽内不削平', r == 6000 and not clip_line(lg, '动态'), 'ret=%s' % r)
check('H4 占位成交价=%.2f(含0.3%%滑点)' % _px_g2,
      abs(h.get('buy_price', 0) - _px_g2) < 0.011, 'buy_price=%s' % h.get('buy_price'))
fresh()
r, lg = run_buy(9.80, want_vol=8000)
_c = clip_line(lg, '动态')
check('H5 8000股超帽削平为%d股' % _cap_low, r == _cap_low, 'ret=%s' % r)
check('H6 削平日志数字一致', ('削平为%d股' % _cap_low) in _c, _c[:90])
check('H7 反证: 旧口径 8000x%.2f=%.0f 突破单票帽 %.2f 元' % (
    _px_g2, 8000 * _px_g2, 8000 * _px_g2 - M.MAX_POS_VALUE_ABS),
    8000 * _px_g2 > M.MAX_POS_VALUE_ABS, '突破 %.2f 元' % (8000 * _px_g2 - M.MAX_POS_VALUE_ABS))

# ---- I: STRATEGY_CASH_CAP<=0 -> abs_cap_left 返回 None, 只受单票帽 ----
fresh(STRATEGY_CASH_CAP=0.0)
_cl_none = M.abs_cap_left(_px_g)
check('I1 无组合上限时 abs_cap_left 返回 None', _cl_none is None, 'ret=%s' % _cl_none)
r, lg = run_buy(10.00, want_vol=8000)
_c = clip_line(lg, '动态')
check('I2 None分支不炸, 仍按单票帽削平为%d股' % _cap_abs,
      r == _cap_abs and ('削平为%d股' % _cap_abs) in _c,
      'ret=%s log=%s' % (r, _c[:60]))

# ---- J: 滑点价折算<=0 -> 兜底用 lp ----
fresh()
_orig_slip = M._slippage_for
M._slippage_for = lambda p: -1.0        # 令 lp*(1+slip)=0, 触发 _px_g<=0 兜底
try:
    r, lg = run_buy(9.80, want_vol=6900)
finally:
    M._slippage_for = _orig_slip
_px_fb = M._round2(9.80)                # 兜底应按 9.80 折算 -> 帽=6800
_cap_fb = int(int(M.MAX_POS_VALUE_ABS / _px_fb) / 100) * 100
_c = clip_line(lg, '动态')
check('J1 兜底按 lp=9.80 折算帽=%d股: 削平到%d(证明用的是lp不是滑点价), 随后夹价异常中止不炸'
      % (_cap_fb, _cap_fb),
      r is None and ('削平为%d股' % _cap_fb) in _c
      and any('委托价夹取异常' in l for l in lg),
      'ret=%s clip=%s' % (r, _c[:70]))
fresh()
r, lg = run_buy(9.80, want_vol=6900)    # 对照: 正常滑点价 9.83 -> 帽 6700 -> 削平
_c = clip_line(lg, '动态')
check('J2 对照: 正常滑点价下 6900 股削平为%d股' % _cap_low,
      r == _cap_low and ('削平为%d股' % _cap_low) in _c,
      'ret=%s clip=%s' % (r, _c[:70]))

print('\n' + '=' * 72)
print('K  AST/接线静态核查(不执行)')
print('=' * 72)

_tree = ast.parse(SRC)
_fn = None
for n in _tree.body:
    if isinstance(n, ast.FunctionDef) and n.name == 'buy_stock':
        _fn = n
        break
check('K1 buy_stock 函数存在', _fn is not None)

# 用 AST 数新局部量的赋值次数(不用字符串 count, 避免注释/格式串干扰)
_cnt = {'_px_g': 0, '_caps_g': 0, '_cl_g': 0, '_cv_g': 0, '_amt_cap': 0}
for node in ast.walk(_fn):
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id in _cnt:
                _cnt[t.id] += 1
check('K2 新局部量赋值次数: px_g 6(3分支x初值+兜底), caps_g/cl_g 各3, cv_g 3, amt_cap 1',
      _cnt == {'_px_g': 6, '_caps_g': 3, '_cl_g': 3, '_cv_g': 3, '_amt_cap': 1},
      str(_cnt))

# 模块级引用可解析
_globals_needed = ['MAX_POS_VALUE_ABS', 'abs_cap_left', '_slippage_for',
                   '_round2', 'log', 'disp', 'TARGET_BUY_AMOUNT']
_missing = [g for g in _globals_needed if not hasattr(M, g)]
check('K3 新代码引用的模块级名字全部可解析', not _missing, 'missing=%s' % _missing)

# 未新增模块级大写常量(指纹零漂移的静态侧证)
_mod_upper = set()
for n in _tree.body:
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id.isupper():
                _mod_upper.add(t.id)
check('K4 母版无本轮新增大写常量', not any(('161' in x) or x.endswith('_G') for x in _mod_upper),
      str(sorted(x for x in _mod_upper if '161' in x)))

# 墓碑注释在位
check('K5 死代码墓碑注释在位',
      '第14轮审计-死代码清理' in SRC and 'def risk_excluded(s):' in SRC)

print('\n' + '=' * 72)
_np = sum(1 for _, c, _ in RES if c)
print('干跑结果: %d/%d PASS' % (_np, len(RES)))
for n, c, d in RES:
    if not c:
        print('  FAIL:', n, '|', d)
print('=' * 72)
sys.exit(0 if _np == len(RES) else 1)
