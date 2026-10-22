# -*- coding: utf-8 -*-
"""V2.6.156 实测: 费用按委托单归并

从母版 AST 抽出真实函数与真实 _G 容器执行, 不注桩。
核心用例: 2026-10-21 13:51:54 601595 上海电影 1张委托900股, 柜台拆成
         100+100+700 三笔成交回报(同一 OrderID), 券商实收 5.25 元。
"""
import ast
import math
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
src = open(P, "rb").read().decode("gbk")
tree = ast.parse(src)

WANT_CONST = {"FEE_ON", "FEE_COMMISSION_RATE", "FEE_COMMISSION_MIN",
              "FEE_STAMP_RATE", "FEE_TRANSFER_RATE", "FEE_PROFILE",
              "FEE_CBOND_SELL_RATE"}
WANT_FUNC = {"_round2", "_f", "_prod_of", "fee_profile", "_transfer_rate_for",
             "_order_fee_delta", "fee_buy", "fee_sell"}

segs, got_c, got_f, got_cls = [], set(), set(), set()
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "_G":
        segs.append(ast.get_source_segment(src, node))
        got_cls.add(node.name)
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

print("抽到常量: %s" % sorted(got_c))
print("抽到函数: %s" % sorted(got_f))
print("抽到容器: %s" % sorted(got_cls))
missing = (WANT_CONST - got_c) | (WANT_FUNC - got_f) | ({"_G"} - got_cls)
if missing:
    print("!! 缺失: %s" % sorted(missing))
    sys.exit(2)

ns = {"math": math, "time": time}
exec("\r\n\r\n".join(segs), ns)

G = ns["G"]
G.state = {}
G.today = "20261021"

FB, FS = ns["fee_buy"], ns["fee_sell"]
R2 = ns["_round2"]
ACC_KEY = "order_fee_acc"

checks = []


def chk(name, ok, extra=""):
    checks.append((name, bool(ok), extra))


def reset(day="20261021"):
    G.state = {}
    G.today = day


def old_way(amount, code, is_buy=True):
    """复刻旧版单笔口径(未归并), 用作对照"""
    p = ns["fee_profile"](code)
    tr = ns["_transfer_rate_for"](code) if ns["_prod_of"](code) == "stock" else p["transfer"]
    if is_buy:
        return R2(max(amount * p["rate"], p["min"]) + amount * tr)
    return R2(max(amount * p["rate"], p["min"]) + amount * p["stamp"] + amount * tr)


print()
print("=" * 74)
print("T1  核心场景: 601595.SH 1张委托900股@28.02 拆成 100+100+700 三笔")
print("=" * 74)
reset()
OID = "30938"
lots = [(100, 28.02), (100, 28.02), (700, 28.02)]
new_each, old_each = [], []
for v, px in lots:
    a = R2(px * v)
    new_each.append(FB(a, "601595.SH", order_id=OID))
    old_each.append(old_way(a, "601595.SH"))
    print("  %4d股 金额%9.2f   新版%6.2f   旧版%6.2f" %
          (v, a, new_each[-1], old_each[-1]))
new_tot, old_tot = R2(sum(new_each)), R2(sum(old_each))
print("  合计: 新版 %.2f 元   旧版 %.2f 元   券商实收 5.25 元" % (new_tot, old_tot))
chk("T1 新版合计 == 券商实收 5.25", abs(new_tot - 5.25) < 0.005, "实得 %.2f" % new_tot)
chk("T1 旧版确为 15.26(问题复现)", abs(old_tot - 15.26) < 0.005, "实得 %.2f" % old_tot)
chk("T1 省下 10.01 元", abs((old_tot - new_tot) - 10.01) < 0.02, "省 %.2f" % (old_tot - new_tot))
chk("T1 委托单表只 1 条", len(G.state.get(ACC_KEY) or {}) == 1, str(G.state.get(ACC_KEY)))

print()
print("=" * 74)
print("T2  分批建仓 3 张委托, 每张 900 股 -> 每张各收一次起收")
print("=" * 74)
reset()
tot = 0.0
for i, oid in enumerate(("A1", "A2", "A3")):
    f1 = FB(R2(28.02 * 300), "601595.SH", order_id=oid)
    f2 = FB(R2(28.02 * 300), "601595.SH", order_id=oid)
    f3 = FB(R2(28.02 * 300), "601595.SH", order_id=oid)
    s = R2(f1 + f2 + f3)
    tot += s
    print("  委托%s: %.2f + %.2f + %.2f = %.2f" % (oid, f1, f2, f3, s))
print("  三张委托合计 = %.2f 元" % R2(tot))
chk("T2 三张委托合计 15.75(每张 5.25)", abs(R2(tot) - 15.75) < 0.005, "实得 %.2f" % tot)
chk("T2 委托单表 3 条", len(G.state.get(ACC_KEY) or {}) == 3, str(len(G.state.get(ACC_KEY) or {})))

print()
print("=" * 74)
print("T3  单笔已过起收门槛: 600519.SH 1000股@100 = 10万拆两笔")
print("=" * 74)
reset()
a1, a2 = R2(100.0 * 500), R2(100.0 * 500)
one_shot = FB(R2(100.0 * 1000), "600519.SH")
n1 = FB(a1, "600519.SH", order_id="B1")
n2 = FB(a2, "600519.SH", order_id="B1")
o1, o2 = old_way(a1, "600519.SH"), old_way(a2, "600519.SH")
print("  一次成交(基准)      = %.2f" % one_shot)
print("  拆两笔 新版 %.2f + %.2f = %.2f" % (n1, n2, R2(n1 + n2)))
print("  拆两笔 旧版 %.2f + %.2f = %.2f" % (o1, o2, R2(o1 + o2)))
chk("T3 归并后与一次成交等值", abs(R2(n1 + n2) - one_shot) < 0.005,
    "%.2f vs %.2f" % (R2(n1 + n2), one_shot))
chk("T3 旧版确实多算", R2(o1 + o2) > one_shot + 0.5, "%.2f" % R2(o1 + o2))

print()
print("=" * 74)
print("T4  order_id 缺失 -> 必须与旧版逐字一致, 且不写归并表")
print("=" * 74)
reset()
for c in ("601595.SH", "000001.SZ", "300750.SZ"):
    a = R2(28.02 * 900)
    nb, ob = FB(a, c), old_way(a, c)
    nsx, osx = FS(a, c), old_way(a, c, is_buy=False)
    print("  %-11s 买入 新%.2f/旧%.2f   卖出 新%.2f/旧%.2f" % (c, nb, ob, nsx, osx))
    chk("T4 买入一致 %s" % c, abs(nb - ob) < 0.005)
    chk("T4 卖出一致 %s" % c, abs(nsx - osx) < 0.005)
chk("T4 空 order_id 不写表", not (G.state.get(ACC_KEY) or {}), str(G.state.get(ACC_KEY)))

print()
print("=" * 74)
print("T5  卖出侧同样归并: 601595.SH 900股@28.30 拆 300+600")
print("=" * 74)
reset()
a1 = R2(28.30 * 300)
a2 = R2(28.30 * 600)
s1 = FS(a1, "601595.SH", order_id="S9")
s2 = FS(a2, "601595.SH", order_id="S9")
one = FS(R2(28.30 * 900), "601595.SH")
o1 = old_way(a1, "601595.SH", is_buy=False)
o2 = old_way(a2, "601595.SH", is_buy=False)
print("  一次卖(基准)      = %.2f" % one)
print("  拆两笔 新版 %.2f + %.2f = %.2f" % (s1, s2, R2(s1 + s2)))
print("  拆两笔 旧版 %.2f + %.2f = %.2f" % (o1, o2, R2(o1 + o2)))
chk("T5 卖出归并后与一次卖出等值", abs(R2(s1 + s2) - one) < 0.005,
    "%.2f vs %.2f" % (R2(s1 + s2), one))
chk("T5 卖出含印花税(大于买入)", one > FB(R2(28.30 * 900), "601595.SH"),
    "%.2f" % one)

print()
print("=" * 74)
print("T6  n_order 口径(供存量持仓校准): 601595 买入总额 25218 元")
print("=" * 74)
reset()
for n in (1, 2, 3):
    v = FB(25218.0, "601595.SH", n_order=n)
    print("  n_order=%d -> %.2f 元" % (n, v))
chk("T6 n_order=1 与旧版一致", abs(FB(25218.0, "601595.SH", n_order=1) - old_way(25218.0, "601595.SH")) < 0.005)
chk("T6 n_order=3 = 15.25", abs(FB(25218.0, "601595.SH", n_order=3) - 15.25) < 0.005,
    "实得 %.2f" % FB(25218.0, "601595.SH", n_order=3))

print()
print("=" * 74)
print("T7  跨日隔离 + 表容量清理")
print("=" * 74)
reset()
FB(R2(28.02 * 900), "601595.SH", order_id="X1")
G.today = "20261022"
same = FB(R2(28.02 * 900), "601595.SH", order_id="X1")
print("  次日同 order_id 单笔费用 = %.2f (应等于一次成交 %.2f)" %
      (same, FB(R2(28.02 * 900), "601595.SH")))
chk("T7 跨日不复用旧累计", abs(same - FB(R2(28.02 * 900), "601595.SH")) < 0.005)
chk("T7 跨日后表 2 条", len(G.state.get(ACC_KEY) or {}) == 2, str(len(G.state.get(ACC_KEY) or {})))

reset()
for i in range(2100):
    ns["_order_fee_delta"]("Z%d" % i, 1000.0, lambda a: FB(a, "601595.SH"))
print("  塞入 2100 张委托后表内条数 = %d (应 <=2000)" % len(G.state.get(ACC_KEY) or {}))
chk("T7 表容量受控 <= 2000", len(G.state.get(ACC_KEY) or {}) <= 2000,
    str(len(G.state.get(ACC_KEY) or {})))

print()
print("=" * 74)
print("T8  真实持仓口径: 江南化工 002226 2200股@5.243 (深市, 无过户费)")
print("=" * 74)
reset()
amt = R2(5.243 * 2200)
print("  买入一次: %.2f 元 (佣金 max(%.3f, 5) = 5.00, 过户 0)" %
      (FB(amt, "002226.SZ"), amt * ns["FEE_COMMISSION_RATE"]))
chk("T8 深市无过户费", abs(FB(amt, "002226.SZ") - 5.0) < 0.005, "%.2f" % FB(amt, "002226.SZ"))

ok = sum(1 for _, r, _ in checks if r)
bad = len(checks) - ok
print()
for name, r, extra in checks:
    if not r:
        print("FAIL %s  | %s" % (name, extra))
print("结果: %d PASS / %d FAIL" % (ok, bad))
sys.exit(0 if bad == 0 else 2)
