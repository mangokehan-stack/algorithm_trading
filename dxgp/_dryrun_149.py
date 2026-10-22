# -*- coding: utf-8 -*-
"""V2.6.149 干跑: 从母版切片执行 _sent_fetch_from_cache, 验日志的真实覆盖率分支"""
import ast, sys, io

P = 'zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk').replace('\r\n', '\n')
tree = ast.parse(t)
fn = None
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name == '_sent_fetch_from_cache':
        fn = n
assert fn is not None
src = ast.get_source_segment(t, fn)
assert src and 'len(_gh)' in src

G = type('G', (), {})()
SENT_INDEX_SYMBOL = '000001.SH'

def _f(v, d=None):
    try:
        x = float(v)
        return x
    except Exception:
        return d

log = []
def _sent_wlog(s):
    log.append(s)

ns = {'G': G, '_f': _f, '_sent_wlog': _sent_wlog, 'SENT_INDEX_SYMBOL': SENT_INDEX_SYMBOL}
exec(compile(src, '<cache>', 'exec'), ns)
call = ns['_sent_fetch_from_cache']

def mk(n_stock, n_uni, today='20261021'):
    G.today = today
    G.hist = {}
    for i in range(n_stock):
        # 需要 3 个交易日: 首日只建立 _prev_c, 后两日才各产生一行统计
        G.hist['%06d.SZ' % i] = [
            {'date': '20261017', 'close': 10.0, 'amount': 1e8, 'zt': 0},
            {'date': '20261019', 'close': 11.0, 'amount': 1e8, 'zt': 0},
            {'date': '20261020', 'close': 12.0, 'amount': 1e8, 'zt': 1},
        ]
    G.hist[SENT_INDEX_SYMBOL] = [{'date': '20261019', 'amount': 5e11},
                                 {'date': '20261020', 'amount': 5e11}]
    G.universe = ['%06d.SZ' % i for i in range(n_uni)]

res = []

# 1) 正常: 120 只有效 + 1 只指数 = 121 / 150 只全市场 -> "121/150只(80.7%)"
#    注: 分子是 len(G.hist) 含指数行, 分母 G.universe 不含 —— 母版原有口径, 差 1 只不改
log.clear(); mk(120, 150)
rows = call()
assert rows and len(rows) == 2, len(rows) if rows else None
assert log and '121/150只(80.7%)' in log[-1], log
res.append(('正常 121/150 -> 80.7%', log[-1]))

# 2) universe 为空 -> 应走 "全市场只数未知" 分支
log.clear(); mk(120, 0)
rows = call()
assert rows and len(rows) == 2
assert '全市场只数未知' in log[-1], log
res.append(('universe 空 -> 未知口径', log[-1]))

# 3) universe 缺属性 -> 同样走未知口径, 不得抛异常
log.clear(); mk(120, 150)
del G.universe
G2 = G
try:
    rows = call()
    assert rows and len(rows) == 2
    assert '全市场只数未知' in log[-1], log
    res.append(('universe 不存在 -> 未知口径', log[-1]))
except Exception as e:
    print('FAIL 3:', repr(e)); sys.exit(1)

# 4) 部分加载(105/5226) -> 2.0%, 且必须仍返回 rows(不放行判定, 不在此处卡)
log.clear(); mk(105, 5226)
rows = call()
assert rows and len(rows) == 2
assert '106/5226只(2.0%)' in log[-1], log
res.append(('部分加载 106/5226 -> 2.0%(仍放行)', log[-1]))

# 5) 门槛: 98 只 + 1 只指数 = 99 < 100 -> 返回 None, 打 "还没准备好"
log.clear(); mk(98, 150)
assert call() is None
assert '还没准备好' in log[-1], log
res.append(('99(含指数)<100 -> None', log[-1]))

for i, (k, v) in enumerate(res, 1):
    print('PASS %d  %-42s | %s' % (i, k, v))
print('ALL %d/5 PASS' % len(res))
