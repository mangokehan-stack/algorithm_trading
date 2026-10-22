# -*- coding: utf-8 -*-
"""V2.6.157 补丁前探测: 锚点唯一性 / 局部变量冲突 / 校验脚本断言"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
K = r"E:\桌面\666666\dxgp\_check_inv.py"

t = open(P, "rb").read().decode("gbk")
L = t.split("\r\n")
CRLF = "\r\n"

print("=== A. 待改锚点唯一性 ===")
A1 = "            _fe_old = _f(_h.get('fee', 0.0))" + CRLF
A2 = "            _n_ord = max(1, int(_f(_h.get('order_cnt', 0)) or 0))" + CRLF
A3 = "            _fe_new = fee_buy(_round2(_fs), _code, n_order=_n_ord)" + CRLF
A4 = "        _fee_fixed = []" + CRLF
A5 = "        _fee_fix_sum = 0.0" + CRLF
A6 = ("            log('[安全] 存量持仓费用口径校准(V2.6.72): 重算%d只, 旧粗估0.15%%->真实费率, "
      "合计成本调整%.2f元 | %s'") + CRLF
for nm, s in (("A1 _fe_old", A1), ("A2 _n_ord", A2), ("A3 _fe_new", A3),
              ("A4 _fee_fixed", A4), ("A5 _fee_fix_sum", A5), ("A6 日志行", A6)):
    print("  %-16s count=%d" % (nm, t.count(s)))

print("\n=== B. 局部变量名冲突检查 ===")
for nm in ("_fe_est", "_est_tol", "_fee_keep", "_fe_skip"):
    print("  %-12s count=%d" % (nm, t.count(nm)))

print("\n=== C. _round2 定义 ===")
for i, l in enumerate(L):
    if l.startswith("def _round2"):
        print("  L%d: %s" % (i + 1, l))
        break

print("\n=== D. VERSION 行 ===")
for i, l in enumerate(L):
    if l.startswith("VERSION = "):
        print("  L%d: %r" % (i + 1, l))
        break

print("\n=== E. _check_inv.py 相关断言 ===")
kt = open(K, "rb").read().decode("utf-8")
for i, l in enumerate(kt.split("\n")):
    if ("n_order" in l) or ("order_cnt" in l) or ("_fe_new" in l):
        print("  L%d: %s" % (i + 1, l.strip()[:150]))

print("\n=== F. 该校准段前后 L8450..L8500 (用于确认缩进层级) ===")
for i in range(8464, 8498):
    print("  L%d|%s" % (i + 1, L[i]))
