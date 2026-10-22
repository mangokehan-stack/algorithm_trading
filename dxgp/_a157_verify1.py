# -*- coding: utf-8 -*-
"""核实子代理结论：日期解析 / state_broken / load_risk_exclude 返回值"""
import ast, io, datetime, re

P = r'E:\桌面\666666\dxgp\_a157_u8.py'
src = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
L = src.split('\n')

print('=' * 70)
print('1) _ts_to_date 实测（直接抄函数体逻辑）')
print('=' * 70)
def _ts_to_date(t):
    try:
        if isinstance(t, str) and t.strip().isdigit():
            t = int(t.strip())
        if isinstance(t, (int, float)):
            ts = t / 1000.0 if t > 10 ** 12 else float(t)
            d = datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d')
            return d if len(d) == 8 and d.isdigit() else ''
        v = str(t).replace('-', '')[:8]
        return v if len(v) == 8 and v.isdigit() else ''
    except Exception:
        return ''

cases = ['20260930', 20260930, '2026-09-30 00:00:00', '20260930.0',
         1759161600000, 1759161600, '1759161600', '', None, 0]
for c in cases:
    print('  %-24r -> %-10r' % (c, _ts_to_date(c)))

print()
print('=' * 70)
print('2) state_broken 的全部赋值点')
print('=' * 70)
for i, ln in enumerate(L, 1):
    if 'state_broken' in ln:
        print('  L%-6d %s' % (i, ln.strip()[:130]))

print()
print('=' * 70)
print('3) load_risk_exclude 函数范围内是否有 return data')
print('=' * 70)
tree = ast.parse(src)
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name == 'load_risk_exclude':
        rets = [x.lineno for x in ast.walk(n) if isinstance(x, ast.Return)]
        print('  函数 L%d-%d, return 行号: %s' % (n.lineno, max(x.lineno for x in ast.walk(n)), rets))
        print('  最后一条语句 L%d: %r' % (n.body[-1].lineno, L[n.body[-1].lineno - 1].strip()[:100]))
        # 检查最后语句之后是否紧跟 return
    if isinstance(n, ast.FunctionDef) and n.name == '_auto_risk_exclude':
        rets = [(x.lineno, ast.get_source_segment(src, x)) for x in ast.walk(n) if isinstance(x, ast.Return)]
        print('  _auto_risk_exclude L%d 内 return: %s' % (n.lineno, rets))

print()
print('=' * 70)
print('4) load_risk_exclude 的调用点（是否接收返回值）')
print('=' * 70)
for i, ln in enumerate(L, 1):
    if 'load_risk_exclude(' in ln and 'def ' not in ln:
        print('  L%-6d %s' % (i, ln.strip()[:120]))

print()
print('=' * 70)
print('5) step_day_init 中 L5674 所在 try 结构（向前找最近 try/if）')
print('=' * 70)
depth = 0
for i in range(5673, 5655, -1):
    print('  L%-6d %r' % (i, L[i - 1][:110]))
