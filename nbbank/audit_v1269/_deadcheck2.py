# -*- coding: utf-8 -*-
"""静态扫描 v2：只写不读的模块级变量 + 局部变量覆盖同名模块级函数（照成 TypeError）。"""
import ast
import collections
import io
import os

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_utf8.py")
src = io.open(SRC, "r", encoding="utf-8").read()
tree = ast.parse(src)

mod_funcs = {}
mod_vars = {}
for node in tree.body:
    if isinstance(node, ast.FunctionDef):
        mod_funcs[node.name] = node.lineno
    elif isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                mod_vars[t.id] = node.lineno

loads = collections.Counter()
stores = collections.Counter()
for node in ast.walk(tree):
    if isinstance(node, ast.Name):
        if isinstance(node.ctx, ast.Load):
            loads[node.id] += 1
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            stores[node.id] += 1

print("=== A. 模块级变量：零 Load（只写不读）===")
n = 0
for name, ln in sorted(mod_vars.items(), key=lambda x: x[1]):
    if loads.get(name, 0) == 0:
        print("  L%-6d %-28s stores=%d loads=0" % (ln, name, stores.get(name, 0)))
        n += 1
print("  -> count:", n)
print()

print("=== B. 局部赋值覆盖同名模块级函数（调用即 TypeError）===")
for fn in [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)]:
    locals_assigned = set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name):
                    locals_assigned.add(t.id)
        elif isinstance(sub, (ast.For,)):
            if isinstance(sub.target, ast.Name):
                locals_assigned.add(sub.target.id)
        elif isinstance(sub, ast.ExceptHandler) and sub.name:
            locals_assigned.add(sub.name)
    called = set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            called.add(sub.func.id)
    hit = sorted((locals_assigned & called) & set(mod_funcs))
    if hit:
        for h in hit:
            print("  %s() @L%d  局部变量 %s 覆盖模块级函数 def %s() @L%d —— 该处调用必抛 TypeError"
                  % (fn.name, fn.lineno, h, h, mod_funcs[h]))
print()

print("=== C. 全局变量在函数内被赋值但未声明 global（UnboundLocalError 风险）===")
for fn in [x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)]:
    decl = set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Global):
            decl.update(sub.names)
    assigned = set()
    read = set()
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Name):
            if isinstance(sub.ctx, ast.Store):
                assigned.add(sub.id)
            elif isinstance(sub.ctx, ast.Load):
                read.add(sub.id)
    bad = sorted((assigned & read) & set(mod_vars) - decl)
    for b in bad:
        # 判断「读」是否发生在「写」之前不可静态确定，但赋值即视为局部 -> 读必抛
        print("  %s() @L%d  变量 %s (模块级 def/var @L%d) 既读又写但无 global 声明"
              % (fn.name, fn.lineno, b, mod_vars[b]))