# -*- coding: utf-8 -*-
"""过户费口径实测：从母版 AST 抽出 _transfer_rate_for 与相关常量，真执行
   （不注桩，直接跑母版源码片段）
"""
import ast
import math
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
src = open(P, "rb").read().decode("gbk")
tree = ast.parse(src)

WANT_CONST = {"FEE_ON", "FEE_COMMISSION_RATE", "FEE_COMMISSION_MIN",
              "FEE_STAMP_RATE", "FEE_TRANSFER_RATE", "FEE_PROFILE"}
WANT_FUNC = {"_round2", "_prod_of", "fee_profile", "_transfer_rate_for",
             "fee_buy", "fee_sell"}

segs, got_c, got_f = [], set(), set()
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 \
            and isinstance(node.targets[0], ast.Name) and node.targets[0].id in WANT_CONST:
        segs.append(ast.get_source_segment(src, node))
        got_c.add(node.targets[0].id)
    if isinstance(node, ast.FunctionDef) and node.name in WANT_FUNC:
        segs.append(ast.get_source_segment(src, node))
        got_f.add(node.name)

print("抽到常量: %s" % sorted(got_c))
print("抽到函数: %s" % sorted(got_f))
miss_c = WANT_CONST - got_c
miss_f = WANT_FUNC - got_f
if miss_c:
    print("!! 缺常量: %s" % sorted(miss_c))
if miss_f:
    print("!! 缺函数: %s" % sorted(miss_f))

ns = {"math": math}   # 真实标准库, 非桩（母版自身也 import math）
exec("\r\n\r\n".join(segs), ns)

_tf = ns["_transfer_rate_for"]
FB, FS = ns["fee_buy"], ns["fee_sell"]

print("\n费率常量: 佣金=%.7f 最低=%.2f 印花税=%.5f 过户费=%.5f"
      % (ns["FEE_COMMISSION_RATE"], ns["FEE_COMMISSION_MIN"],
         ns["FEE_STAMP_RATE"], ns["FEE_TRANSFER_RATE"]))

print("\n--- 1. 过户费率按市场分列 ---")
cases = ["600519.SH", "601398.SH", "603232.SH", "605588.SH",
         "688517.SH", "689009.SH", "000001.SZ", "002232.SZ", "300750.SZ", ""]
exp_sh = {"600519.SH", "601398.SH", "603232.SH", "605588.SH", "688517.SH", "689009.SH"}
ok = True
for c in cases:
    r = _tf(c)
    want = 0.00001 if c in exp_sh else (0.00001 if c == "" else 0.0)
    flag = "OK" if abs(r - want) < 1e-12 else "BAD"
    if flag == "BAD":
        ok = False
    print("  %-12s -> %.5f   %s" % (c or "(空)", r, flag))

print("\n--- 2. 买卖各收一次（沪市 12000 元一笔）---")
A = 12000.0
for c in ("600519.SH", "000001.SZ"):
    b, s = FB(A, c), FS(A, c)
    print("  %-11s 买入费=%.2f  卖出费=%.2f  双边合计=%.2f  占金额=%.4f%%"
          % (c, b, s, b + s, (b + s) / A * 100))
    # 手算核对
    comm = max(A * ns["FEE_COMMISSION_RATE"], ns["FEE_COMMISSION_MIN"])
    tr = A * _tf(c)
    st = A * ns["FEE_STAMP_RATE"]
    print("               手算: 买=%.2f(佣金%.2f+过户%.2f)  卖=%.2f(佣金%.2f+印花%.2f+过户%.2f)"
          % (comm + tr, comm, tr, comm + st + tr, comm, st, tr))
    if abs(b - (comm + tr)) > 0.005 or abs(s - (comm + st + tr)) > 0.005:
        ok = False
        print("               !! 与手算不一致")

print("\n--- 3. 过户费单边金额（每万元）---")
print("  沪市 1 万元: 买入 0.10 元, 卖出 0.10 元, 双边 0.20 元")
print("  深市 1 万元: 0.00 元（并入佣金, 不另收）")

print("\n结论: %s" % ("过户费按沪市双边万0.1 正常收取、买卖各一次 == 现状 0.00001 正确"
                     if ok else "存在不一致，需复查"))
sys.exit(0 if ok else 1)
