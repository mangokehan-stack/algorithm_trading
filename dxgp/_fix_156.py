# -*- coding: utf-8 -*-
"""修正 V2.6.156 文件头时间戳为真实落盘时刻, 并复核改动行"""
import hashlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
CRLF = "\r\n"
t = open(P, "rb").read().decode("gbk")

OLD = "# 版本号: V2.6.156             修改时间: 2026-10-21 14:22"
NEW = "# 版本号: V2.6.156             修改时间: 2026-10-21 14:16"
n = t.count(OLD)
print("时间戳锚点命中: %d" % n)
if n != 1:
    print("锚点不唯一, 中止")
    sys.exit(2)
t = t.replace(OLD, NEW, 1)
open(P, "wb").write(t.encode("gbk"))

b = open(P, "rb").read()
t2 = b.decode("gbk")
print("MD5      = %s" % hashlib.md5(b).hexdigest())
print("字节     = %d" % len(b))
print("段数     = %d" % len(t2.split(CRLF)))
print("裸LF     = %d" % t2.replace(CRLF, "").count("\n"))
print("裸CR     = %d" % t2.replace(CRLF, "").count("\r"))
print("BOM      = %s" % (b[:3] == b"\xef\xbb\xbf"))
print("GBK往返  = %s" % (t2.encode("gbk").decode("gbk") == t2))
print("文件头   = %s" % t2.split(CRLF)[4][:70])
print()

L = t2.split(CRLF)
print("=== 改动点逐处复核 ===")


def show(tag, pat, before=0, after=3):
    idx = [i for i, l in enumerate(L) if pat in l]
    print("[%s] 命中 %d 处" % (tag, len(idx)))
    for i in idx[:4]:
        for j in range(max(0, i - before), min(len(L), i + after + 1)):
            mark = ">>" if j == i else "  "
            print("  %s L%-6d %s" % (mark, j + 1, L[j][:120]))


show("_order_fee_delta定义", "def _order_fee_delta(order_id, amount, calc):", 0, 5)
show("fee_buy归并入口", "return _order_fee_delta(order_id, amount, lambda a: fee_buy(a, code))", 1, 2)
show("fee_sell归并入口", "return _order_fee_delta(order_id, amount, lambda a: fee_sell(a, code))", 1, 2)
show("deal_callback取委托号", "_order_id = str(getattr(dealInfo, 'm_strOrderID', '')", 1, 4)
show("买入回报算费", "fee = fee_buy(amt, code, order_id=_order_id)", 3, 4)
show("买入记账传fee", "pos_before=pos_before, fee=fee))", 2, 1)
show("卖出记账传order_id", "order_id=_order_id)", 2, 1)
show("校准按张数", "_fe_new = fee_buy(_round2(_fs), _code, n_order=_n_ord)", 2, 1)
show("VERSION", "VERSION = 'V2.6.156'", 0, 0)

print()
print("=== 关键静态度量 ===")
import ast
tree = ast.parse(t2)
consts = []
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        nm = node.targets[0].id
        if nm.isupper() and not nm.startswith("_"):
            consts.append(nm)
print("模块级大写常量(不含下划线前缀) = %d" % len(consts))

stop_nodes = [n for n in ast.walk(tree)
              if isinstance(n, ast.Name) and n.id == "stop_order"]
print("stop_order AST 引用 = %d (铁律要求 0)" % len(stop_nodes))
print("fee = fee_buy(amt, s) 出现 = %d (应为 1)" % t2.count("fee = fee_buy(amt, s)"))
