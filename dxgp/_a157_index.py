# -*- coding: utf-8 -*-
"""全新审计：结构索引（函数/类/常量/行号）"""
import ast, io, sys

P = r'E:\桌面\666666\dxgp\_a157_u8.py'
src = io.open(P, encoding='utf-8', newline='').read()
src_lf = src.replace('\r\n', '\n')
tree = ast.parse(src_lf)
L = src_lf.split('\n')

out = []
def w(s=''):
    out.append(s)

# 顶层结构
for n in tree.body:
    if isinstance(n, ast.Assign):
        tg = ', '.join(getattr(t, 'id', getattr(t, 'attr', '?')) for t in n.targets)
        w('L%-6d ASSIGN  %s' % (n.lineno, tg[:90]))
    elif isinstance(n, ast.AnnAssign):
        w('L%-6d ANNASSIGN %s' % (n.lineno, getattr(n.target, 'id', '?')))
    elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        w('L%-6d DEF     %s(%s)' % (n.lineno, n.name, ', '.join(a.arg for a in n.args.args)[:70]))
    elif isinstance(n, ast.ClassDef):
        w('L%-6d CLASS   %s' % (n.lineno, n.name))
        for m in n.body:
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                w('    L%-6d  .%s(%s)' % (m.lineno, m.name, ', '.join(a.arg for a in m.args.args)[:60]))
    elif isinstance(n, ast.If):
        w('L%-6d IF(module-level)' % n.lineno)
    elif isinstance(n, (ast.Import, ast.ImportFrom)):
        w('L%-6d IMPORT  %s' % (n.lineno, ast.get_source_segment(src_lf, n) or '')[:80])
    elif isinstance(n, ast.Expr):
        w('L%-6d EXPR    %s' % (n.lineno, (ast.get_source_segment(src_lf, n) or '')[:60].replace('\n', ' ')))
    else:
        w('L%-6d OTHER   %s' % (n.lineno, type(n).__name__))

io.open(r'E:\桌面\666666\dxgp\_a157_index.txt', 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
print('lines_in_tree=%d  total_lines=%d  top_nodes=%d' % (len(L), len(L), len(tree.body)))
print('wrote _a157_index.txt  rows=%d' % len(out))
