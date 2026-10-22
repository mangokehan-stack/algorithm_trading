# -*- coding: utf-8 -*-
"""V2.6.157 实测: 存量持仓费用校准只修「真正的 0.15% 粗估」

从母版 AST 抽出真实函数 + 真实 _G 容器, 并把校准段原样抽出包装成函数执行。
核心用例: 2026-10-21 14:23:20 启动时 601595 上海电影两张委托累计 10.45 元,
        被 V2.6.156 按一张重算成 5.45(低估 5.00)。本版起不再二次改写。
"""
import ast
import math
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
src = open(P, "rb").read().decode("gbk")
tree = ast.parse(src)
L = src.split("\r\n")

WANT_CONST = {"FEE_ON", "FEE_COMMISSION_RATE", "FEE_COMMISSION_MIN",
              "FEE_STAMP_RATE", "FEE_TRANSFER_RATE", "FEE_PROFILE",
              "FEE_CBOND_SELL_RATE"}
WANT_FUNC = {"_round2", "_f", "_prod_of", "fee_profile", "_transfer_rate_for",
             "_order_fee_delta", "fee_buy", "fee_sell",
             "is_own_position", "pos_vol"}

segs, got_c, got_f = [], set(), set()
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "_G":
        segs.append(ast.get_source_segment(src, node))
    if isinstance(node, ast.Assign) and len(node.targets) == 1 \
            and isinstance(node.targets[0], ast.Name):
        nm = node.targets[0].id
        if nm in WANT_CONST:
            segs.append(ast.get_source_segment(src, node))
            got_c.add(nm)
        elif nm == "G":
            segs.append(ast.get_source_segment(src, node))
    if isinstance(node, ast.FunctionDef) and node.name in WANT_FUNC:
        segs.append(ast.get_source_segment(src, node))
        got_f.add(node.name)

print("抽到常量: %d 个 | 函数: %s" % (len(got_c), sorted(got_f)))
missing = (WANT_CONST - got_c) | (WANT_FUNC - got_f)
if missing:
    print("!! 缺失: %s" % sorted(missing))
    sys.exit(2)

# ---- 抽出校准段(原样, 只去掉外层 4 个空格缩进) ----
i_start = i_end = -1
for i, l in enumerate(L):
    if l == "        _fee_fixed = []":
        i_start = i
    if i_start >= 0 and l.startswith("        # 方向A2: 在途买单补录"):
        i_end = i
        break
if i_start < 0 or i_end < 0:
    print("!! 校准段定位失败 start=%d end=%d" % (i_start, i_end))
    sys.exit(2)

block = []
for l in L[i_start:i_end]:
    if l.startswith("    "):
        block.append(l[4:])
    elif l.strip() == "":
        block.append("")
    else:
        print("!! 段内出现缩进异常行: %r" % l[:80])
        sys.exit(2)

LOGS = []


def _log(msg):
    LOGS.append(msg)


WRAP = (
    "def _run_calib(hold):\r\n"
    "    _recon_changed = False\r\n"
    + "\r\n".join(block) + "\r\n"
    "    return {'fixed': _fee_fixed, 'keep': _fee_keep,"
    " 'changed': _recon_changed, 'sum': _fee_fix_sum}\r\n"
)

ns = {"math": math, "time": time, "log": _log}
exec("\r\n\r\n".join(segs), ns)
try:
    exec(WRAP, ns)
except Exception:
    print("!! 校准段包装失败")
    import traceback
    traceback.print_exc()
    sys.exit(2)

G = ns["G"]
G.state = {}
G.today = "20261021"
CALIB = ns["_run_calib"]
FB = ns["fee_buy"]
R2 = ns["_round2"]

print("校准段: L%d..L%d (%d 行)" % (i_start + 1, i_end, len(block)))
print()

checks = []


def chk(name, ok, extra=""):
    checks.append((name, bool(ok), extra))


def mk(fv, fs, fee, ct=None, cnt=None, managed=True):
    h = {"fill_vol": fv, "fill_sum": fs, "fee": fee, "managed": managed}
    h["cost_total"] = ct if ct is not None else R2(fs + fee)
    if cnt is not None:
        h["order_cnt"] = cnt
    return h


def run(hold):
    del LOGS[:]
    return CALIB(hold)


print("=" * 78)
print("用例1 ★ 601595 真实状态: fill_sum=44910 fee=5.45(已被V2.6.156改低) order_cnt缺失")
hold = {"601595.SH": mk(1600, 44910.0, 5.45)}
r = run(hold)
h = hold["601595.SH"]
chk("不改 fee(仍是5.45)", abs(h["fee"] - 5.45) < 1e-9, "实际=%.2f" % h["fee"])
chk("不改 cost_total", abs(h["cost_total"] - 44915.45) < 1e-9, "实际=%.2f" % h["cost_total"])
chk("记入跳过名单", len(r["keep"]) == 1, "keep=%r" % (r["keep"],))
chk("未记入修正名单", len(r["fixed"]) == 0, "fixed=%r" % (r["fixed"],))
chk("跳过说明含粗估值", "67.3" in (r["keep"][0] if r["keep"] else ""),
    r["keep"][0] if r["keep"] else "")
chk("粗估值口径 = _round2(fill_sum x 0.0015)",
    abs(R2(44910.0 * 0.0015) - float(r["keep"][0].split("应为")[1].split(",")[0])) < 1e-9
    if r["keep"] else False, "keep=%r" % (r["keep"],))
print("   keep = %s" % (r["keep"][0] if r["keep"] else ""))
print("   日志: %s" % (LOGS[-1][:100] if LOGS else "(无)"))

print("\n" + "=" * 78)
print("用例2 ★ 002226 真实状态: fill_sum=11535 fee=5.00(真实值) order_cnt缺失")
hold = {"002226.SZ": mk(2200, 11535.0, 5.0)}
r = run(hold)
h = hold["002226.SZ"]
chk("不改 fee(仍是5.00)", abs(h["fee"] - 5.0) < 1e-9, "实际=%.2f" % h["fee"])
chk("记入跳过名单", len(r["keep"]) == 1)

print("\n" + "=" * 78)
print("用例3 ★ V2.6.71 前的老记录(粗估形态): 沪市 fill_sum=12000 fee=18.00 = 12000x0.0015")
hold = {"600519.SH": mk(100, 12000.0, 18.0)}
r = run(hold)
h = hold["600519.SH"]
exp = FB(12000.0, "600519.SH", n_order=1)
chk("已校准为真实值 %.2f" % exp, abs(h["fee"] - exp) < 1e-9, "实际=%.2f" % h["fee"])
chk("cost_total 同步", abs(h["cost_total"] - R2(12000.0 + exp)) < 1e-9,
    "实际=%.2f" % h["cost_total"])
chk("记入修正名单", len(r["fixed"]) == 1, "fixed=%r" % (r["fixed"],))
chk("未记入跳过名单", len(r["keep"]) == 0)
chk("成本下降(修正方向正确)", h["cost_total"] < 12018.0, "实际=%.2f" % h["cost_total"])
print("   %s -> %.2f (原 %.2f)" % ("fee", h["fee"], 18.0))
print("   日志: %s" % (LOGS[-1][:110] if LOGS else "(无)"))

print("\n" + "=" * 78)
print("用例4 深市老记录(粗估形态): fill_sum=12000 fee=18.00")
hold = {"002226.SZ": mk(2200, 12000.0, 18.0)}
r = run(hold)
h = hold["002226.SZ"]
exp = FB(12000.0, "002226.SZ", n_order=1)
chk("深市校准为 %.2f(无过户费)" % exp, abs(h["fee"] - exp) < 1e-9, "实际=%.2f" % h["fee"])
chk("深市费用低于沪市", h["fee"] < 5.12, "实际=%.2f" % h["fee"])

print("\n" + "=" * 78)
print("用例5 小金额粗估: fill_sum=1000 fee=1.50 = 1000x0.0015 (真实需5元起收)")
hold = {"600519.SH": mk(100, 1000.0, 1.50)}
r = run(hold)
h = hold["600519.SH"]
chk("已校准(费用上调到起收)", abs(h["fee"] - 5.01) < 0.02, "实际=%.2f" % h["fee"])
chk("费用上调", h["fee"] > 4.99, "实际=%.2f" % h["fee"])

print("\n" + "=" * 78)
print("用例6 真实值已正确(幂等): fill_sum=12000 fee 已是真实值")
exp = FB(12000.0, "600519.SH", n_order=1)
hold = {"600519.SH": mk(100, 12000.0, exp)}
r = run(hold)
chk("无任何改动(fixed=0 即幂等)", len(r["fixed"]) == 0, "fixed=%d" % len(r["fixed"]))
chk("fee 保持原值", abs(hold["600519.SH"]["fee"] - exp) < 1e-9,
    "实际=%.2f" % hold["600519.SH"]["fee"])
chk("cost_total 保持原值", abs(hold["600519.SH"]["cost_total"] - R2(12000.0 + exp)) < 1e-9)

print("\n" + "=" * 78)
print("用例7 多张委托的真实记录: fill_sum=44910 fee=10.45(2张各起收) —— 也不该被改")
hold = {"601595.SH": mk(1600, 44910.0, 10.45)}
r = run(hold)
h = hold["601595.SH"]
chk("不改 fee(仍是10.45)", abs(h["fee"] - 10.45) < 1e-9, "实际=%.2f" % h["fee"])
chk("记入跳过名单", len(r["keep"]) == 1)

print("\n" + "=" * 78)
print("用例8 两只混合: 一只粗估该修、一只真实该留")
hold = {"600519.SH": mk(100, 12000.0, 18.0), "601595.SH": mk(1600, 44910.0, 5.45)}
r = run(hold)
chk("修正 1 只", len(r["fixed"]) == 1, "fixed=%r" % (r["fixed"],))
chk("跳过 1 只", len(r["keep"]) == 1, "keep=%r" % (r["keep"],))
chk("两只日志都打了", len(LOGS) == 2, "日志数=%d" % len(LOGS))

print("\n" + "=" * 78)
print("用例9 边界: fill_sum=100 fee=0(完全没记账) —— 应被修正为起收5元(保守方向)")
hold = {"600519.SH": mk(100, 100.0, 0.0)}
r = run(hold)
h = hold["600519.SH"]
chk("fee 从 0 修正为起收", abs(h["fee"] - FB(100.0, "600519.SH", n_order=1)) < 1e-9,
    "实际=%.2f" % h["fee"])
chk("记入修正名单", len(r["fixed"]) == 1, "fixed=%d keep=%d" % (len(r["fixed"]), len(r["keep"])))
chk("修正方向保守(费用上调)", h["fee"] > 0.0)

print("\n" + "=" * 78)
print("用例10 容差边界: fill_sum=12000 粗估18.00, 记成 17.20(差0.80 < 容差1.0)")
hold = {"600519.SH": mk(100, 12000.0, 17.20)}
r = run(hold)
chk("容差内仍认定粗估 → 校准", len(r["fixed"]) == 1, "fixed=%d keep=%d" % (len(r["fixed"]), len(r["keep"])))

print("\n" + "=" * 78)
ok = sum(1 for x in checks if x[1])
for nm, good, extra in checks:
    print("  %s  %s%s" % ("PASS" if good else "FAIL", nm, ("   " + extra) if (extra and not good) else ""))
print("\n结果: %d PASS / %d FAIL" % (ok, len(checks) - ok))
sys.exit(0 if ok == len(checks) else 2)
