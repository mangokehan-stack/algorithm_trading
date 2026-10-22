# -*- coding: utf-8 -*-
"""V2.6.88 功能单测 —— 换手率自算 / 心跳自证 / 文案口径
方法: AST 抽出母版真实函数, 注入桩 G 后执行(不是抄一份逻辑来测, 防口径漂移)。
背景: 20261019 实盘日志 "换手率不符0(字段缺失121)" —— 121 只全部取不到换手率,
      ZT_TURNOVER_MIN/MAX 自上线起从未生效。
"""
import ast, math, re, time, types

P = 'zt_shrink_strategy_gbk.py'
src = open(P, encoding='gbk', newline='').read()
tree = ast.parse(src)

fails = []
def chk(name, cond, detail=''):
    print('%-54s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        fails.append(name)

# ---------- 抽出真实函数 ----------
nodes = [n for n in tree.body
         if isinstance(n, ast.FunctionDef) and n.name in ('_f', '_float_share')]
assert len(nodes) == 2, [n.name for n in nodes]
mod = ast.Module(body=nodes, type_ignores=[])
ast.fix_missing_locations(mod)

calls = {'n': 0, 'detail': None, 'raise': None}

class _C(object):
    def get_instrument_detail(self, code):
        calls['n'] += 1
        if calls['raise']:
            raise calls['raise']
        return calls['detail']

G = types.SimpleNamespace()
ns = {'G': G, 'time': time, 'math': math,
      '_api': lambda fn, *a, **k: fn(*a, **k)}
exec(compile(mod, '<v2688>', 'exec'), ns)
_f = ns['_f']
_float_share = ns['_float_share']
G.C = _C()

mk = lambda d: (calls.__setitem__('detail', d), calls.__setitem__('n', 0))
fresh = lambda: setattr(G, '_fshare_cache', {})

# ---------- T1 字段拼写三种全试 ----------
fresh(); mk({'FloatVolume': 500000000.0})
chk('T1a FloatVolume 命中', _float_share('600000.SH') == 500000000.0, repr(_float_share('600000.SH')))

fresh(); mk({'FloatVolumn': 300000000.0})
chk('T1b FloatVolumn(低等级客户端) 命中', _float_share('600001.SH') == 300000000.0)

fresh(); mk({'CirculatingVolume': 200000000.0})
chk('T1c CirculatingVolume 命中', _float_share('600002.SH') == 200000000.0)

fresh(); mk({'CirculatingVolume': 0, 'FloatVolume': 120000000.0})
chk('T1d 首拼写为0时继续试下一个', _float_share('600003.SH') == 120000000.0)

# ---------- T2 取不到 -> 0(放行不误杀) ----------
fresh(); mk({})
chk('T2a 三拼写全空 -> 0', _float_share('600004.SH') == 0.0)
fresh(); mk(None)
chk('T2b 接口返回 None -> 0', _float_share('600005.SH') == 0.0)
fresh(); mk('garbage')
chk('T2c 接口返回非 dict -> 0', _float_share('600006.SH') == 0.0)

G_noc = types.SimpleNamespace()
_old_c = G.C
del G.C
chk('T2d 客户端无 get_instrument_detail -> 0', _float_share('600007.SH') == 0.0)
G.C = _old_c

# ---------- T3 异常不崩 ----------
fresh(); mk({}); calls['raise'] = RuntimeError('boom')
try:
    v = _float_share('600008.SH')
    crashed = None
except Exception as e:
    v, crashed = None, repr(e)
calls['raise'] = None
chk('T3 接口抛异常 -> 返回0且不崩', crashed is None and v == 0.0, 'crash=%r v=%r' % (crashed, v))

# ---------- T4 缓存 ----------
fresh(); mk({'FloatVolume': 888000000.0})
a = _float_share('600009.SH'); n1 = calls['n']
b = _float_share('600009.SH'); n2 = calls['n']
chk('T4a 首次调用打接口一次', n1 == 1, 'n1=%d' % n1)
chk('T4b 二次命中缓存不打接口', n2 == 1 and a == b == 888000000.0, 'n2=%d' % n2)
fresh(); mk({'FloatVolume': 1.0})
_float_share('600010.SH')
chk('T4c 换标的走新查询', calls['n'] == 1, 'n=%d' % calls['n'])

# ---------- T5 自算口径数值(实盘 603466 风语筑量级) ----------
# 基准量 1468009 手; 流通市值约 60 亿 / 股价 13.57 -> 流通股本约 4.42 亿股
UNIT = 100
vol_hand = 1468009.0
shares = 60e8 / 13.57
to = vol_hand * UNIT / shares
chk('T5a 风语筑量级换手率 > 20% 上限', to > 0.20, 'to=%.2f%%' % (to * 100))
chk('T5b 旧版口径(turnover=0)会放行该票',
    _f(0) <= 0, '旧逻辑 _to<=0 直接跳过剔除')
# 一字板场景: 成交量极小
to2 = 50000.0 * UNIT / shares
chk('T5c 一字板量级换手率 < 5% 下限', to2 < 0.05, 'to=%.2f%%' % (to2 * 100))

# ---------- T6 静态口径 ----------
chk('T6a 漏斗打印自算/缺失双计数', '换手率不符%d(过低%d/过高%d/自算%d/缺失放行%d)' in src)
chk('T6b 自算早于缺失放行',
    src.index('_sh_t = _float_share(s)') < src.index('st_turnover_missing += 1'))
chk('T6c 自算用 DAILY_VOL_UNIT 而非硬编码100',
    '* float(DAILY_VOL_UNIT) / _sh_t' in src)
chk('T6d 阈值未被改动', 'ZT_TURNOVER_MIN = 0.05' in src and 'ZT_TURNOVER_MAX = 0.20' in src)
chk('T6e 心跳启动自证日志', '[安全] 心跳已就绪' in src)
chk('T6f 心跳写失败显式提示', '心跳文件写入失败(双实例检测将不可用)' in src)
chk('T6g 亏损文案不重复扣除', '不重复扣除' in src)
chk('T6h 基准量不足加空格', '基准量不足 %d' in src)
def _ver_tuple(s):
    _m = re.search(r"VERSION = 'V(\d+)\.(\d+)\.(\d+)'", s)
    return tuple(int(x) for x in _m.groups()) if _m else (0, 0, 0)


chk('T6i VERSION 不早于 V2.6.88', _ver_tuple(src) >= (2, 6, 88), str(_ver_tuple(src)))

print('-' * 70)
if fails:
    print('RESULT: %d FAILED -> %s' % (len(fails), fails))
    raise SystemExit(1)
print('RESULT: ALL V2.6.88 TESTS PASS')
