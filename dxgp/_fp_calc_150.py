# -*- coding: utf-8 -*-
"""复算参数指纹: 从源码顺序 exec 模块级大写常量, 再按 _fp_keys/_fp_calc 的口径求值。
用途: 给用户一个重粘后应看到的 [参数指纹] 预期值。"""
import ast
import re
import sys

P = sys.argv[1] if len(sys.argv) > 1 else r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
SRC = open(P, 'rb').read().decode('gbk').replace('\r\n', '\n')
TREE = ast.parse(SRC)

# 取 _FP_DENY 字面量
DENY = None
for n in TREE.body:
    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == '_FP_DENY':
        DENY = ast.literal_eval(n.value)
assert DENY is not None and len(DENY) >= 21, 'DENY 项数 %s' % (len(DENY) if DENY else None)
print('_FP_DENY 共 %d 项, 含 HISTORY_BARS: %s' % (len(DENY), 'HISTORY_BARS' in DENY))

ns = {}
skipped = []
order = []
for n in TREE.body:
    tgts, val = [], None
    if isinstance(n, ast.Assign):
        tgts, val = n.targets, n.value
    elif isinstance(n, ast.AnnAssign) and n.value is not None:
        tgts, val = [n.target], n.value
    else:
        continue
    names = [t.id for t in tgts if isinstance(t, ast.Name)]
    if not names:
        continue
    try:
        code = compile(ast.Module(body=[n], type_ignores=[]), '<c>', 'exec')
        exec(code, ns)
    except Exception as e:
        skipped.append((names[0], type(e).__name__, str(e)[:60]))
        continue
    for nm in names:
        order.append(nm)


def fp(d, keys):
    raw = '|'.join('%s=%s' % (k, d.get(k)) for k in sorted(keys))
    h = 2166136261
    for c in raw.encode('utf-8'):
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return '%08x' % h, raw


TYPES = (int, float, bool, str, tuple, list, dict, type(None))
keys = [k for k in ns if k.isupper() and not k.startswith('_') and k not in DENY and isinstance(ns[k], TYPES)]
print('参与指纹的常量 %d 个' % len(keys))

v_par, raw = fp(ns, keys)
v_code, _ = fp(ns, keys + ['VERSION'])
print('参数指纹 =', v_par)
print('版本指纹 =', v_code, '(含 VERSION=%s)' % ns.get('VERSION'))
print('HISTORY_BARS 在参与集合中: %s (应为 False)' % ('HISTORY_BARS' in keys))
print('FEE_TRANSFER_RATE =', ns.get('FEE_TRANSFER_RATE'))

if skipped:
    print('\n未参与 exec 的赋值语句 %d 条(需人工确认是否影响指纹):' % len(skipped))
    for s in skipped[:20]:
        print('  %-24s %s %s' % s)
