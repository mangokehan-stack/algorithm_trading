# -*- coding: utf-8 -*-
"""v1.2.58 行为级回归测试：直接 exec GBK 原件（QMT 内置函数桩注入），
验证 P1/P2/P3 的实际数值行为，以及止盈/铁律核心判定未被破坏。
"""
import sys, types, math

P = r"E:\桌面\666666\nbbank\gf_qmt_native_multi_gbk.py"
txt = open(P, "rb").read().decode("gbk")

# ---- 注入 QMT 框架桩 ----
CALLS = {"passorder": [], "log": []}


def passorder(op, ot, acct, code, pt, price, vol, tag, quick, strat, C):
    CALLS["passorder"].append(dict(op=op, price=price, vol=vol, tag=tag))
    return 12345


G = {
    "passorder": passorder,
    "ContextInfo": object,
    "get_full_tick": lambda C, *a, **k: {},
    "get_trade_detail_data": lambda *a, **k: None,
    "get_instrument_detail": lambda *a, **k: None,
    "get_market_data_ex": lambda *a, **k: None,
    "account": "8973786",
    "SYMBOL": "002142.SZ",
}
for k, v in G.items():
    setattr(types, k, v) if False else None
import builtins
for k, v in G.items():
    setattr(builtins, k, v)

ns = {"__name__": "gf_test"}
exec(compile(txt, "gf", "exec"), ns)

PARAMS = ns["PARAMS"]
STOCK_COMMISSION_RATE = ns["STOCK_COMMISSION_RATE"]
STOCK_COMMISSION_MIN = ns["STOCK_COMMISSION_MIN"]
STOCK_STAMP_TAX_RATE = ns["STOCK_STAMP_TAX_RATE"]
STOCK_TRANSFER_FEE_RATE = ns["STOCK_TRANSFER_FEE_RATE"]
LIMIT_SLIP_PCT_SELL = ns["LIMIT_SLIP_PCT_SELL"]

print("=" * 74)
print("v1.2.58 行为级回归测试")
print("=" * 74)
print("  参数指纹 = %s" % ns.get("_PARAM_FP", "?")[:16])
print("  固定止盈=%.0f%% 移动止盈=激活%.0f%%/回撤%.0f%% max_position_pct=%.0f%%" % (
    PARAMS["take_profit_pct"] * 100,
    PARAMS["trailing_activate_pct"] * 100,
    PARAMS["trailing_dd_pct"] * 100,
    PARAMS["max_position_pct"] * 100))
print("  hard_stop_dd_pct=%s  max_drawdown_pct=%.0f%%" % (
    PARAMS.get("hard_stop_dd_pct"), PARAMS["max_drawdown_pct"] * 100))

fails = []


def eq(label, got, want, tol=1e-9):
    okk = abs(got - want) <= tol if isinstance(want, float) else got == want
    print("  [%s] %-46s got=%s want=%s" % ("PASS" if okk else "FAIL", label, got, want))
    if not okk:
        fails.append(label)


# ================= P3 移动止盈口径 =================
print()
print("【P3】移动止盈 peak/回撤口径（应等于保守成交价口径）")
stp = ns["should_take_profit"]


def net_pnl_pct(shares, cost, px):
    ref = round(px * (1 - LIMIT_SLIP_PCT_SELL), 2)
    mv = shares * ref
    net = (mv - max(mv * STOCK_COMMISSION_RATE, STOCK_COMMISSION_MIN)
           - mv * STOCK_STAMP_TAX_RATE - mv * STOCK_TRANSFER_FEE_RATE)
    return (net - cost) / cost * 100.0, ref


# 场景A：浮盈 3.0~3.9%（不触发固定止盈4%）-> peak 应被记录为保守成交价
shares, cost, px = 1000, 9900.0, 10.30
p, ref = net_pnl_pct(shares, cost, px)
stA = ns["new_state"]()
stA["position_shares"] = shares
stA["total_cost"] = cost
stA["trailing_peak"] = 0.0
okA, whyA = stp(stA, px, PARAMS)
print("  A 净浮盈=%.2f%% 保守价=%.2f -> ok=%s peak=%.4f" % (p, ref, okA, stA["trailing_peak"]))
eq("A 不触发固定止盈(浮盈<4%)", okA, False)
eq("A peak == 保守成交价(非实时价)", round(stA["trailing_peak"], 4), round(ref, 4))

# 场景B：peak 已记录后回落，按保守价口径回撤触发
stB = ns["new_state"]()
stB["position_shares"] = shares
stB["total_cost"] = cost
stB["trailing_peak"] = stA["trailing_peak"]        # 10.27（保守价口径记录的 peak）
pxB = 10.06
pB, refB = net_pnl_pct(shares, cost, pxB)
dd_real = (stA["trailing_peak"] - pxB) / stA["trailing_peak"] * 100
dd_ref = (stA["trailing_peak"] - refB) / stA["trailing_peak"] * 100
okB, whyB = stp(stB, pxB, PARAMS)
print("  B 净浮盈=%.2f%% | 回撤 实时价=%.2f%% 保守价=%.2f%% (阈值2%%) -> ok=%s %s"
      % (pB, dd_real, dd_ref, okB, whyB))
eq("B 保守价口径下回撤超阈触发卖出", okB, True)
eq("B 触发时净浮盈仍>0(铁律不亏钱才卖)", pB > 0, True)
if okB:
    eq("B 触发原因标注为移动止盈", "移动止盈" in whyB, True)
    eq("B 日志文案用保守价", "保守价" in whyB, True)

# ================= 铁律：亏损不卖 =================
print()
print("【铁律】扣费后不赚钱绝不卖")
st4 = ns["new_state"]()
st4["position_shares"] = 1000
st4["total_cost"] = 10000.0   # 成本 10.000，现价 10.00 -> 净到手扣费后 < 成本
ok4, why4 = stp(st4, 10.00, PARAMS)
eq("浮盈0(扣费后为负)不触发止盈", ok4, False)

# ================= can_invest 硬顶 =================
print()
print("【风控】can_invest 单标的硬顶 20万×90%+300")
ci = ns["can_invest"]
cap = 200000.0
o1, r1 = ci(cap, 179000.0, 1000.0)     # 179000+1000 < 180300 -> 放行
eq("17.9万+1000元 放行", o1, True)
o2, r2 = ci(cap, 180000.0, 1000.0)     # 180000+1000 > 180300 -> 拦截
eq("18.0万+1000元 拦截", o2, False)
print("       拦截原因: %s" % r2[:60])

# ================= calc_shares 严格模式 =================
print()
print("【仓位】calc_shares 严格模式（不足1手返回0，不超预算）")
cs = ns["calc_shares"]
eq("5000元@35.00 -> 100股(142股向下取整到整手)", cs(5000, 35.00, 100, 999999), 100)
eq("3000元@35.00 -> 0股(不足1手)", cs(3000, 35.00, 100, 999999), 0)
eq("3600元@35.00 -> 100股", cs(3600, 35.00, 100, 999999), 100)
eq("受cash封顶: amount=100000 cash=3600 -> 100股", cs(100000, 35.00, 100, 3600), 100)

# ================= 费率 =================
print()
print("【费率】券商真实费率（万0.841/5元起、印花万5、过户万1）")
eq("佣金率 = 0.0000841", STOCK_COMMISSION_RATE, 0.0000841)
eq("佣金最低 = 5.0", STOCK_COMMISSION_MIN, 5.0)
eq("印花税率 = 0.0005", STOCK_STAMP_TAX_RATE, 0.0005)
eq("过户费率 = 0.00001", STOCK_TRANSFER_FEE_RATE, 0.00001)
cbc = ns["compute_buy_cost"]
cost = cbc(10000, 10.00)   # 10万元
eq("买入10万成本(含费)", round(cost, 2), round(100000 + 8.41 + 1.00, 2))

# ================= 人工接管额度 =================
print()
print("【人工接管】额度释放逻辑")
mt = ns["manual_takeover_codes"]()
# AUD27(2026-10-20)：002142.SZ 已按用户拍板置 manual_takeover=True（手工仓不占额度），
# 故此处不再断言「无接管标的」，改为断言「接管集合与实际配置一致」。
eq("接管集合与实际配置一致",
   set(mt), set(s["code"] for s in ns["SYMBOLS"]
                if s.get("enabled") and s.get("manual_takeover")))
afc = ns["_account_free_cash"]
eq("_account_free_cash(无其他标的占用)", afc("002142.SZ", 500000.0), 500000.0)
# 模拟：另一标的已部署 10 万
ns["STATES"]["999999.SZ"] = {"deployed": 100000.0}
eq("其他标的部署10万后可动用=40万", afc("002142.SZ", 500000.0), 400000.0)
# 人工接管后应被跳过
# 把「占用资金的 999999」加入 SYMBOLS 并标记人工接管 -> 其 deployed 应被跳过
ns["SYMBOLS"].append({"code": "999999.SZ", "name": "测试标的",
                      "capital_cap": 100000.0, "enabled": True, "manual_takeover": True})
eq("人工接管标的集合含 999999",
   "999999.SZ" in ns["manual_takeover_codes"](), True)
eq("其 deployed 不再占用现金池(额度已释放)", afc("002142.SZ", 500000.0), 500000.0)
ns["SYMBOLS"].pop()
eq("取消接管后重新占用(恢复 40 万)", afc("002142.SZ", 500000.0), 400000.0)
del ns["STATES"]["999999.SZ"]

# ================= 交易日 =================
print()
print("【交易日】is_trade_day 返回值必须是元组（P0/AUD74 回归）")
itsd = ns["is_trade_day"]()
print("  is_trade_day() -> %r" % (itsd,))
eq("返回二元组", isinstance(itsd, tuple) and len(itsd) == 2, True)
ptd = ns["previous_trading_day"]("2026-10-19")
print("  previous_trading_day('2026-10-19') -> %r" % (ptd,))

print()
print("=" * 74)
if fails:
    print("失败 %d 项: %s" % (len(fails), fails))
    sys.exit(1)
print("全部行为级回归测试通过")
print("=" * 74)
