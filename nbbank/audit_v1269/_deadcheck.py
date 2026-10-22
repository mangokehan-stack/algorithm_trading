# -*- coding: utf-8 -*-
"""静态扫描：函数/模块级变量的「只定义不引用」与引用计数（仅读取，不修改交付件）。"""
import ast
import collections
import io
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_utf8.py")
src = io.open(SRC, "r", encoding="utf-8").read()
tree = ast.parse(src)

# 函数定义（含嵌套）
funcs = {}
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        funcs[node.name] = node.lineno

# 模块级赋值目标
mod_assign = {}
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                mod_assign[t.id] = node.lineno
    elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
        mod_assign[node.target.id] = node.lineno

counts = collections.Counter()
for node in ast.walk(tree):
    if isinstance(node, ast.Name):
        counts[node.id] += 1
    elif isinstance(node, ast.Attribute):
        counts[node.attr] += 1

print("=== total lines:", src.count("\n") + 1, " funcs:", len(funcs), " modvars:", len(mod_assign))
print()
print("=== A. 函数零引用（疑似死代码）===")
un = [(ln, n) for n, ln in funcs.items() if counts.get(n, 0) == 0]
for ln, n in sorted(un):
    print("  L%-6d %s" % (ln, n))
print("  -> count:", len(un))
print()
print("=== B. 函数仅 1 次引用（可能只在自己定义行附近）===")
one = [(ln, n) for n, ln in funcs.items() if counts.get(n, 0) == 1]
for ln, n in sorted(one):
    print("  L%-6d %s" % (ln, n))
print("  -> count:", len(one))
print()
print("=== C. 模块级变量零读取（只写不读）===")
for n, ln in sorted(mod_assign.items(), key=lambda x: x[1]):
    if counts.get(n, 0) <= 1:   # 1 = 只有赋值目标本身那次 Name
        print("  L%-6d %s  (refs=%d)" % (ln, n, counts.get(n, 0)))
print()
print("=== D. 关键函数引用计数 ===")
for n in ("passorder", "_r1_net_profit_gate", "_sentiment_eval", "manual_sell",
          "manual_hold_watch", "add_position_signal", "intraday_add", "split_followup",
          "can_invest", "buy_shares", "sell_all", "_sync_state_to_actual",
          "check_hard_stop", "_subproc_read_bytes", "_win32_read_bytes",
          "settle_pending_timeout", "has_live_buy_order", "_handlebar_impl"):
    print("  %-28s refs=%d" % (n, counts.get(n, 0)))