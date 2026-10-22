# -*- coding: utf-8 -*-
"""AUD27 专项回归：手工仓不占策略名额/额度 + 卖出铁律（亏损不卖、扣费后赚钱才卖）。

用法：python -u _test_manual_aud27.py
全部通过退出码 0，有失败退出码 1。
"""
import io, os, sys, types, tempfile

sys.stdout.reconfigure(encoding="utf-8")

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk")

fails = []
passes = [0]


def eq(name, got, want, tol=1e-9):
    ok = (abs(got - want) <= tol) if isinstance(got, (int, float)) and isinstance(want, (int, float)) \
        and not isinstance(got, bool) else (got == want)
    if ok:
        passes[0] += 1
        print("  [PASS] %-52s got=%r" % (name, got))
    else:
        fails.append(name)
        print("  [FAIL] %-52s got=%r want=%r" % (name, got, want))


def truthy(name, got):
    if got:
        passes[0] += 1
        print("  [PASS] %-52s got=%r" % (name, got))
    else:
        fails.append(name)
        print("  [FAIL] %-52s got=%r want=truthy" % (name, got))


# ---------------- 构造沙箱命名空间：重定向所有落盘路径 ----------------
TMP = tempfile.mkdtemp(prefix="aud27_")
ns = {"__name__": "aud27mod", "__file__": P, "__doc__": None, "__builtins__": __builtins__}

# 替换所有 *_FILE 常量为临时目录（在 exec 前给一个假的 os.path 行为不可行，
# 故 exec 后再覆盖；exec 本身不落盘——模块顶层无写盘调用）
exec(compile(src, P, "exec"), ns)

for k in list(ns.keys()):
    if k.endswith("_FILE") and isinstance(ns[k], str):
        ns[k] = os.path.join(TMP, os.path.basename(ns[k]))
ns["_mirror_copy"] = lambda *a, **k: None
ns["_mirror_copy_trade_logs"] = lambda *a, **k: None
ns["_mirror_restore_all"] = lambda *a, **k: None

gate = ns["_r1_net_profit_gate"]
nsym = ns["new_state"]
mkt_on = ns["_manual_takeover_on"]
mcfg = ns["_manual_cfg"]

print("=" * 78)
print("AUD27 专项回归：手工仓分离 + 卖出铁律")
print("=" * 78)

# ============================================================ 1 手工仓分离（源码级）
print()
print("【1】_sync_state_to_actual 手工仓分离（源码断言）")
body = src[src.index("def _sync_state_to_actual("):src.index("def verify_position_before_order(")]
# 去掉注释行：AUD27 在注释里保留了「原实现长什么样」的说明，直接 grep 会误判
body_code = "\n".join(l for l in body.split("\n")
                      if not l.strip().startswith("#"))
truthy("不再把券商持仓写进 state['total_cost']",
       'state["total_cost"] = actual_vol * broker_avg' not in body_code)
truthy("不再把券商持仓写进 state['deployed']",
       'state["deployed"] = state["total_cost"]' not in body)
truthy("不再把券商均价写成 last_add_price 基准",
       'state["last_add_price"] = broker_avg if broker_avg > 0 else price' not in body)
truthy("写入 manual_shares（AUD35-P1 扣除策略账本与在途买单口径）",
       'state["manual_shares"] = _ms_new_a35' in body
       and '_ms_new_a35 = int(actual_vol) - _strat_reach_a35' in body)
truthy("写入 manual_cost", 'state["manual_cost"] = _mkt_cost' in body)
truthy("deployed 只反映策略账本", 'state["deployed"] = float(state.get("total_cost", 0.0) or 0.0)' in body)
truthy("tier 只在策略有仓时保留", 'state["tier"] = state.get("tier", -1)' in body)

# ============================================================ 2 铁律闸门
print()
print("【2】_r1_net_profit_gate 铁律：亏损不卖 / 扣费后赚钱才卖")
st = nsym()
st["manual_shares"] = 1000
st["manual_cost"] = 34830.0

# 2.1 成本 34.83，现价 34.83 -> 扣费后必亏 -> 拒卖
ok, d = gate("002142.SZ", 1000, 34.83, 34.83, st, "test")
eq("成本价卖出被拒(扣费后亏)", ok, False)
truthy("拒卖原因含「不赚钱不卖」", "不赚钱不卖" in d.get("why", ""))
truthy("扣费后盈亏为负", d.get("pct", 0) < 0)

# 2.2 现价 34.90（+0.2%）-> 仅覆盖手续费，仍不赚 -> 拒卖
ok, d = gate("002142.SZ", 1000, 34.83, 34.90, st, "test")
eq("微涨0.2%仍被拒(未覆盖税费)", ok, False)

# 2.3 现价 36.60（+5%）-> 扣费后净赚 -> 放行
ok, d = gate("002142.SZ", 1000, 34.83, 36.60, st, "test")
eq("涨5%扣费后净赚放行", ok, True)
truthy("放行原因含净赚金额", "净赚" in d.get("why", ""))
truthy("保守成交价 < 现价(卖出滑点)", d.get("ref_px", 0) < 36.60)

# 2.4 临界点：反解「刚好扣费后不亏」的价格，应该仍未通过（净到手<=成本）
ref = 34.83 * 1000
# 解 1000*p*(1-0.0005-0.00001)-max(...,5) = 34830
# 反解的是「挂单价」ref = p*(1-滑点)，故 p_star = ref / (1-滑点)
_ref_star = (34830.0 + 5.0) / (1000 * (1 - 0.0005 - 0.00001 - 0.0000841))
p_star = _ref_star / (1 - ns["LIMIT_SLIP_PCT_SELL"])
# 注意：保守成交价会被 round 到 2 位小数，向上进位后净到手可能略高于成本
# （本例 34.8557 -> 34.86，净到手 34837.22 > 成本 34830，正 7.22 元）。
# 故按「反解价下一位」严格测临界：把 ref 往下压 0.01 元，净到手必低于成本 -> 必须拒卖。
ok, d = gate("002142.SZ", 1000, 34.83, p_star - 0.01, st, "test")
eq("临界价-0.01元 -> 净到手<成本 -> 拒卖", ok, False)
truthy("拒卖且净到手<=成本", d.get("net", 1e9) <= d.get("cost", 0) + 1e-6)
ok2, d2 = gate("002142.SZ", 1000, 34.83, p_star * 1.02, st, "test")
eq("临界价+2%放行", ok2, True)

# 2.5 空仓 -> 拒
ok, d = gate("002142.SZ", 0, 0.0, 36.0, st, "test")
eq("券商0股直接拒卖", ok, False)

# 2.6 券商均价缺失时以策略账本/手工账本兜底（取更保守的大值）
st2 = nsym()
st2["manual_shares"] = 1000
st2["manual_cost"] = 40000.0     # 均价 40，高于券商 34.83
ok, d = gate("002142.SZ", 1000, 34.83, 36.60, st2, "test")
eq("成本取max(券商,手工账本)时按40判 -> 拒卖", ok, False)
eq("判定用成本=40000", round(d.get("cost", 0), 2), 40000.0)

# 2.7 子仓卖出（只卖手工仓那一份）成本按比例折算
st3 = nsym()
st3["position_shares"] = 500
st3["total_cost"] = 500 * 30.0        # 均价 30
ok, d = gate("002142.SZ", 1500, 34.83, 36.60, st3, "test", sub_vol=1000)
eq("子仓卖出用1000股算成本", round(d.get("cost", 0), 2), round(3483.0 * 10, 2) if False else
   round(max(34.83, 30.0) * 1000, 2))

# ============================================================ 3 manual_sell 接线
print()
print("【3】manual_sell 路径完整性（源码断言）")
truthy("manual_sell 已定义", "def manual_sell(" in src)
truthy("handlebar 调用 manual_sell", "if manual_sell(C, code, _ms_acct, _ms_px, state," in src)
truthy("手工仓卖单在途冻结字段", '"manual_sell_pending_until"' in src)
truthy("manual_hold_watch 观察日志", "def manual_hold_watch(" in src)
truthy("清仓时手工账本归零", 'state["manual_shares"] = 0' in src)
truthy("Sell 路径不再依赖 position_shares 判 R1",
       "_gate_ok, _gd = _r1_net_profit_gate(code, pos_vol, _gavg94, price, state, reason," in src)
ms_body = src[src.index("def manual_sell("):src.index("def manual_hold_watch(")]
truthy("manual_sell 内先过铁律闸门", "_r1_net_profit_gate(code, _mvol, _avg, price, state," in ms_body)
truthy("manual_sell 不写 tier", '"tier"' not in ms_body)
truthy("manual_sell 不写 deployed", "deployed" not in ms_body)
truthy("两本账并存时让位策略止盈", 'state.get("position_shares", 0) or 0) > 0' in ms_body)
truthy("无止损语义（不含 stop_loss 调用）", "stop_loss" not in ms_body)

# ============================================================ 4 配置
print()
print("【4】SYMBOLS 配置")
eq("002142.SZ manual_takeover(AUD33 用户拍板恢复正常交易)", mkt_on("002142.SZ"), False)
eq("manual_* 参数保留可复用", mcfg("002142.SZ", "manual_takeover_tp_pct", None), 0.04)
eq("手工仓止盈阈值", mcfg("002142.SZ", "manual_takeover_tp_pct", None), 0.04)
eq("移动止盈开关", mcfg("002142.SZ", "manual_takeover_trailing", None), True)
eq("移动止盈激活线", mcfg("002142.SZ", "manual_takeover_trailing_activate_pct", None), 0.03)
eq("移动止盈回撤", mcfg("002142.SZ", "manual_takeover_trailing_dd_pct", None), 0.02)

# ============================================================ 5 状态字段
print()
print("【5】new_state 手工仓字段")
s = nsym()
eq("manual_shares 默认0", s.get("manual_shares"), 0)
eq("manual_cost 默认0", s.get("manual_cost"), 0.0)
eq("manual_peak_cost 默认0", s.get("manual_peak_cost"), 0.0)
eq("manual_sell_pending_until 默认0", s.get("manual_sell_pending_until"), 0.0)
eq("position_shares 仍为0(策略账本独立)", s.get("position_shares"), 0)
eq("tier 仍为-1(未被手工仓推进)", s.get("tier"), -1)
eq("deployed 仍为0(不占额度)", s.get("deployed"), 0.0)

# ============================================================ 6 版本
print()
print("【6】版本自检")
eq("STRATEGY_VERSION", ns["STRATEGY_VERSION"], "v1.2.80")
truthy("文件头版本行同步", "#  策略版本: v1.2.80" in src)

print()
print("=" * 78)
if fails:
    print("失败 %d 项 / 通过 %d 项：%s" % (len(fails), passes[0], fails))
    sys.exit(1)
print("全部 %d 项通过（AUD27 手工仓分离 + 卖出铁律）" % passes[0])
print("=" * 78)
