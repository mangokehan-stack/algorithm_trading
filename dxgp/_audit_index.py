# -*- coding: utf-8 -*-
"""结构索引: 函数清单 / 常量表 / 分节标题, 输出到 _audit_index.txt"""
import ast, io, sys

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
lines = t.split('\r\n')
tree = ast.parse(t.replace('\r\n', '\n'))

out = []
def w(s):
    out.append(s)

w('总行数 %d' % len(lines))
w('=' * 90)
w('【一】顶层函数/类 (按行号)')
w('=' * 90)
tot = 0
for n in tree.body:
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        span = (n.end_lineno or n.lineno) - n.lineno + 1
        tot += span
        args = [a.arg for a in n.args.args]
        w('L%-6d %-4d行  def %s(%s)' % (n.lineno, span, n.name, ', '.join(args)))
    elif isinstance(n, ast.ClassDef):
        span = (n.end_lineno or n.lineno) - n.lineno + 1
        tot += span
        w('L%-6d %-4d行  class %s' % (n.lineno, span, n.name))
w('')
w('顶层函数总行数 %d / %d (占 %.1f%%)' % (tot, len(lines), 100.0 * tot / len(lines)))

w('')
w('=' * 90)
w('【二】模块级大写常量 (%d 个)')
w('=' * 90)
cnt = 0
for n in tree.body:
    tgts, val = [], None
    if isinstance(n, ast.Assign):
        tgts, val = n.targets, n.value
    elif isinstance(n, ast.AnnAssign) and n.value is not None:
        tgts, val = [n.target], n.value
    else:
        continue
    for tg in tgts:
        if isinstance(tg, ast.Name) and tg.id.isupper() and not tg.id.startswith('_'):
            cnt += 1
            try:
                v = ast.literal_eval(val)
                vs = repr(v)
            except Exception:
                vs = '<表达式>'
            if len(vs) > 90:
                vs = vs[:87] + '...'
            w('L%-6d %-28s = %s' % (n.lineno, tg.id, vs))
w('合计 %d' % cnt)

w('')
w('=' * 90)
w('【三】分节标题 (全大写#注释 / 含"====")')
w('=' * 90)
import re as _re
_pat = _re.compile(r'^#\s*(?:[=\-*]{3,})')
for i, l in enumerate(lines):
    s = l.strip()
    if s.startswith('#') and len(s) < 100 and (_pat.match(s) or '====' in s):
        w('L%-6d %s' % (i + 1, s[:100]))

open(r'E:\桌面\666666\dxgp\_audit_index.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('\n'.join(out[:80]))
print('...(完整见 _audit_index.txt, 共 %d 行)' % len(out))
