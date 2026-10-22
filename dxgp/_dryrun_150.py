# -*- coding: utf-8 -*-
"""V2.6.150 干跑: 问题1(80%门槛) 与 问题4(先求值后上锁) 的分支验证
函数体从母版 AST 切片执行, 不注入任何模块桩(只注入真实依赖中的少量外部对象)。
"""
import ast
import json
import os
import shutil
import tempfile
import time

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
SRC = open(P, 'rb').read().decode('gbk').replace('\r\n', '\n')
LINES = SRC.split('\n')
TREE = ast.parse(SRC)


def grab(name):
    for n in TREE.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return '\n'.join(LINES[n.lineno - 1:n.end_lineno])
    raise KeyError(name)


# ============================================================
# 问题1: _sent_fetch_from_cache 入口门槛 = 全市场池 80%(下限100)
# ============================================================
code1 = grab('_sent_fetch_from_cache')
log = []


class G(object):
    pass


ns = {'_f': lambda v: float(v or 0), 'SENT_INDEX_SYMBOL': '000001.SH',
      '_sent_wlog': lambda s: log.append(s), 'G': G}
exec(compile(code1, '<cache>', 'exec'), ns)
call = ns['_sent_fetch_from_cache']


def mk(n_hist, n_uni, with_uni=True):
    G.hist = {}
    for i in range(n_hist):
        G.hist['%06d.SZ' % i] = [
            {'date': '20261019', 'close': 10.0, 'amount': 1e8, 'zt': 0},
            {'date': '20261020', 'close': 11.0, 'amount': 1e8, 'zt': 1},
        ]
    if with_uni:
        G.universe = ['%06d.SZ' % i for i in range(n_uni)]
    else:
        if hasattr(G, 'universe'):
            del G.universe


res = []

# 1) 80% 边界: universe=150 -> need=120; hist=119 -> 拦
log.clear(); mk(119, 150)
r = call()
assert r is None, '用例1 应拦下: %r' % (r,)
assert '119只' in log[-1] and '需>=120只' in log[-1] and '全市场150只' in log[-1], log[-1]
res.append(('边界:119/150 -> 拦(需>=120)', log[-1]))

# 2) hist=120 -> 恰好 80% 放行
log.clear(); mk(120, 150)
r = call()
assert r and len(r) == 1, '用例2 应放行: %r' % (r,)
res.append(('边界:120/150 -> 放行', log[-1]))

# 3) 旧口径会放行的 101 只, 新版必须拦(方案A的核心)
log.clear(); mk(101, 5226)
r = call()
assert r is None, '用例3 101只/5226 应拦下, 实际放行'
assert '需>=4180只' in log[-1], log[-1]
res.append(('101/5226 -> 拦(需>=4180)', log[-1]))

# 4) 全市场池为空 -> 退回旧口径 100 只: 99 拦 / 100 放行
log.clear(); mk(99, 0)
assert call() is None, '用例4a 99只(池空) 应拦'
assert '需>=100只' in log[-1] and '全市场池未知' in log[-1], log[-1]
res.append(('池为空:99只 -> 拦(退回100)', log[-1]))
log.clear(); mk(100, 0)
assert call() is not None, '用例4b 100只(池空) 应放行'
res.append(('池为空:100只 -> 放行', log[-1]))

# 5) G.universe 属性不存在 -> 同样退回 100
log.clear(); mk(99, 0, with_uni=False)
assert call() is None, '用例5 无 universe 属性 99只 应拦'
assert '全市场池未知' in log[-1], log[-1]
res.append(('无 universe 属性:99只 -> 拦', log[-1]))

# 6) 池子比下限还小(50) -> need 不得低于 100
log.clear(); mk(99, 50)
assert call() is None, '用例6 池50/99只 应拦(need 仍为100)'
assert '需>=100只' in log[-1], log[-1]
res.append(('池50:99只 -> 拦(need下限100)', log[-1]))

# 7) 池子异常(非容器) -> 不抛异常, 退回 100
log.clear()
G.hist = {'%06d.SZ' % i: [{'date': '20261019', 'close': 10.0},
                          {'date': '20261020', 'close': 11.0}] for i in range(100)}
G.universe = 12345          # len() 会抛 TypeError
r = call()
assert r is not None, '用例7 池异常时不应崩, 且 100 只应放行'
assert '全市场只数未知' in log[-1], log[-1]
res.append(('池异常(int):100只 -> 放行不崩', log[-1]))

# ============================================================
# 问题4: _gen_superseded 先求值后上锁
# ============================================================
code2 = grab('_gen_superseded')
tmp = tempfile.mkdtemp()
GEND = os.path.join(tmp, 'gen.json')
HBD = os.path.join(tmp, 'hb_acct_999.json')


def mk_sup(hb_obj):
    json.dump({'gen': 2.0, 'pid': 999}, open(GEND, 'w', encoding='utf-8'))
    json.dump(hb_obj, open(HBD, 'w', encoding='utf-8'))
    n2 = {'_GEN_STATE': {'id': 1.0, 'path': GEND}, '_GEN_DOWN': {'yes': False},
          'gen_path': lambda: GEND, '_f': float, 'json': json,
          '_split_name': lambda s: ('hb', '.json'),
          'HEARTBEAT_FILE': 'zt_shrink_heartbeat.json',
          '_join_base': lambda n: os.path.join(tmp, n),
          '_account_suffix': lambda: '_acct',
          'HEARTBEAT_STALE_SEC': 60.0, 'time': time}
    exec(compile(code2, '<gen>', 'exec'), n2)
    return n2


# 1) 心跳 ts 是字符串 -> 求值抛 ValueError -> 返回 False 且【不得上锁】
n2 = mk_sup({'pid': 999, 'ts': 'not-a-number'})
r = n2['_gen_superseded']()
assert r is False, '求值异常应返回 False, 实际 %r' % (r,)
assert n2['_GEN_DOWN']['yes'] is False, '求值异常时不得上锁, 实际已上锁(旧版 bug 复现)'
res.append(('心跳ts异常 -> False 且未上锁(旧版会上锁)', ''))

# 2) 心跳 ts 新鲜 -> 判定成立且上锁
n2 = mk_sup({'pid': 999, 'ts': time.time()})
r = n2['_gen_superseded']()
assert r is True and n2['_GEN_DOWN']['yes'] is True, '新鲜心跳应 True+上锁, 实际 %r/%r' % (r, n2['_GEN_DOWN'])
res.append(('心跳新鲜 -> True 且已上锁', ''))

# 3) 心跳过期 -> 判定成立(上锁)但返回 False
n2 = mk_sup({'pid': 999, 'ts': time.time() - 600})
r = n2['_gen_superseded']()
assert r is False and n2['_GEN_DOWN']['yes'] is True, '过期心跳应 False+上锁, 实际 %r/%r' % (r, n2['_GEN_DOWN'])
res.append(('心跳过期 -> False 但已上锁(原有设计)', ''))

# 4) 世代号不大于本代 -> 直接 False, 不上锁
json.dump({'gen': 1.0, 'pid': 999}, open(GEND, 'w', encoding='utf-8'))
n2 = mk_sup({'pid': 999, 'ts': time.time()})
json.dump({'gen': 1.0, 'pid': 999}, open(GEND, 'w', encoding='utf-8'))
r = n2['_gen_superseded']()
assert r is False and n2['_GEN_DOWN']['yes'] is False, '同代不应上锁'
res.append(('同代 -> False 且不上锁', ''))

shutil.rmtree(tmp, ignore_errors=True)

print('=== %d/%d PASS ===' % (len(res), len(res)))
for i, (name, detail) in enumerate(res, 1):
    print('%2d PASS  %s' % (i, name))
    if detail:
        print('        日志: %s' % detail)
