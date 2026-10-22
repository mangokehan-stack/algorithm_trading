# -*- coding: utf-8 -*-
"""V2.6.156 终态体检"""
import ast
import hashlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
CRLF = "\r\n"
b = open(P, "rb").read()
t = b.decode("gbk")
L = t.split(CRLF)

print("MD5        = %s" % hashlib.md5(b).hexdigest())
print("字节       = %d" % len(b))
print("段数       = %d (真实行数 %d)" % (len(L), len(L) - 1))
print("裸LF       = %d" % t.replace(CRLF, "").count("\n"))
print("裸CR       = %d" % t.replace(CRLF, "").count("\r"))
print("BOM        = %s" % (b[:3] == b"\xef\xbb\xbf"))
print("GBK往返    = %s" % (t.encode("gbk").decode("gbk") == t))
print("文件头     = %s" % L[4][:66])
print("VERSION    = %s" % [l for l in L if l.startswith("VERSION = ")][0])
print()

tree = ast.parse(t)
consts = []
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 \
            and isinstance(node.targets[0], ast.Name):
        nm = node.targets[0].id
        if nm.isupper() and not nm.startswith("_"):
            consts.append(nm)
print("模块级大写常量 = %d (V2.6.155 亦为 284)" % len(consts))
print("stop_order AST = %d (铁律要求 0)" %
      len([n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "stop_order"]))
print("fee = fee_buy(amt, s) = %d (应为 1)" % t.count("fee = fee_buy(amt, s)"))
print()

# 关键函数签名
import re
for pat in (r"def _order_fee_delta\([^)]*\):",
            r"def fee_buy\([^)]*\):",
            r"def fee_sell\([^)]*\):",
            r"def ledger_buy\([^)]*\):",
            r"def ledger_sell\([^)]*\):"):
    m = re.search(pat, t)
    print("  %s" % (m.group(0) if m else "!! 缺失 %s" % pat))
print()

# 交叉核对: 每个新增调用点的副作用只发生一次
print("fee_buy 传入 order_id 的处数 = %d (应为 1, 即成交回报买入分支)"
      % t.count("fee_buy(amt, code, order_id=_order_id)"))
print("fee_sell 传入 order_id 的处数 = %d (应为 1, 在 ledger_sell 内部)"
      % t.count("fee_sell(amt, s, order_id=order_id)"))
print("ledger_buy 传 fee 的处数 = %d (应为 1)" % t.count("pos_before=pos_before, fee=fee))"))
print("ledger_sell 传 order_id 的处数 = %d (应为 1)"
      % t.count("order_id=_order_id)" + CRLF))
print("order_fee_acc 引用 = %d 处" % t.count("order_fee_acc"))
print("order_cnt 引用 = %d 处" % t.count("order_cnt"))
print()

# 确认 order_fee_acc 只被 deal_callback 使用
lines = [i + 1 for i, l in enumerate(L) if "order_fee_acc" in l]
print("order_fee_acc 出现行: %s" % lines)
lines2 = [i + 1 for i, l in enumerate(L) if "order_cnt" in l]
print("order_cnt 出现行: %s" % lines2)
