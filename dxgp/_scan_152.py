# -*- coding: utf-8 -*-
"""V2.6.152 文案扫描：只查代码字符串常量(排除模块/函数 docstring 与注释)
   目的：确认 19 处旧口径文案已全部改为「暂停开新仓 + 卖出不受影响」双段表述
"""
import ast
import sys

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
src = open(P, "rb").read().decode("gbk")
tree = ast.parse(src)

# 收集所有 docstring 节点的区间，扫的时候排除
doc_ranges = []
for node in ast.walk(tree):
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) \
                and isinstance(node.body[0].value.value, str):
            d = node.body[0].value
            doc_ranges.append((d.lineno, d.col_offset, d.end_lineno, d.end_col_offset))

def in_doc(lineno, col):
    for l1, c1, l2, c2 in doc_ranges:
        if (lineno, col) >= (l1, c1) and (lineno, col) < (l2, c2):
            return True
    return False

lines = src.split("\r\n")

BAD = [
    "不拦截买入",
    "主策略不受影响",
    "不影响原策略",
    "按中性处理",
    "全部中性",
    "全按中性",
    "买入侧保持中性",
    "情绪跳过",
    "跳开买入闸门",
    "跳开",
    "不影响交易",
    "不影响卖出",
    "保持中性",
]

hits = {}
total_str = 0
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if in_doc(node.lineno, node.col_offset):
            continue
        total_str += 1
        for kw in BAD:
            if kw in node.value:
                hits.setdefault(kw, []).append((node.lineno, node.value.replace("\r\n", "\\r\\n")[:150]))

print("非 docstring 字符串常量总数: %d" % total_str)
print("docstring 区间数: %d" % len(doc_ranges))
print("-" * 70)
if not hits:
    print("旧文案残留: 0 处  ==> PASS")
else:
    for kw, items in hits.items():
        print("[命中] %s  共 %d 处" % (kw, len(items)))
        for ln, txt in items:
            print("   L%-6d %s" % (ln, txt))
        print()

print("=" * 70)
# 正向确认：新表述应存在的样本
GOOD = [
    "暂停开新仓",
    "卖出不受影响",
    "暂停分批加仓",
    "情绪L1闸门放行",
    "情绪数据未就绪",
]
print("新表述出现计数(全文件含注释):")
for kw in GOOD:
    print("  %-14s %d 次" % (kw, src.count(kw)))