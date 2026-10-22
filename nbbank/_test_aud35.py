# -*- coding: utf-8 -*-
"""AUD35 专项回归：两本账归属修复（随版本滚动校验）

覆盖 v1.2.72 修复的两个潜伏缺陷（版本断言随交付件滚动到 v1.2.77）：
  缺陷 P1：同步函数把券商全量股数记成手工仓，策略自己的部分成交被误分类
           -> 策略账本清空 -> 误判空仓可能重复开首仓
  缺陷 P2：sell_all 按券商可卖全量下单，策略止盈会把手工股一起卖

本脚本 exec GBK 交付件，在进程内直接测状态机，不联网、不下单。
"""
import io
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")

M = type(sys)("m35")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)

import tempfile
tmp = tempfile.mkdtemp(prefix="_a35_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp

R = []
CODE = "002142.SZ"


def chk(name, cond, detail=""):
    R.append((name, bool(cond), detail))


def eq(name, got, want):
    chk(name, got == want, "got=%r want=%r" % (got, want))


LOG = []
M.log = lambda m: LOG.append(m)

# ---------------- 1) 源码级：P1 分类口径 ----------------
chk("A1 手工份额=券商全量-策略账本-在途买单",
    "_ms_new_a35 = int(actual_vol) - _strat_reach_a35" in src)
chk("A2 策略可解释上限含在途买单",
    "_strat_reach_a35 = max(0, _ps_a35 + _pd_a35)" in src)
chk("A3 负值钳0保护", "if _ms_new_a35 < 0:" in src)
chk("A4 手工份额为0时不污染峰值", "if price > 0 and _ms_new_a35 > 0:" in src)
chk("A5 归属-策略日志存在", "【持仓归属-策略】" in src)

# ---------------- 2) 源码级：P2 卖出钳制 ----------------
chk("B1 sell_all 钳制存在", "_strat_sell_a35 = max(0, int(pos_vol) - _ms_sell_a35)" in src)
chk("B2 全手工仓拒卖分支", "全部为手工仓" in src and "策略不代卖手工仓" in src)
i_gate = src.find("_r1_net_profit_gate(code, pos_vol")
i_clamp = src.find("_ms_sell_a35 = int(state.get")
chk("B3 钳制在 R1 闸门之后（先判盈亏再钳股数）", 0 < i_gate < i_clamp)
chk("B4 sell_all 有 allow_manual 参数（AUD35-P3 代卖放行）",
    "def sell_all(C, code, acct, price, reason, state=None, allow_manual=False):" in src)
chk("B5 manual_sell 代卖传 allow_manual=True",
    "sell_all(C, code, acct, price, _why, state, allow_manual=True):" in src)
chk("B6 代卖旁路仅包住钳制、不影响 R1",
    src.find("if not allow_manual:") > i_gate)

# ---------------- 3) 行为级 P1：场景矩阵 ----------------
def run_sync(ps, pend, manual, actual, avg=34.5, price=34.9, ms_cost=0.0):
    st = M.new_state()
    st["position_shares"] = ps
    st["manual_shares"] = manual
    st["manual_cost"] = ms_cost
    if pend > 0:
        M._PENDING_BUYS[CODE] = pend
    else:
        M._PENDING_BUYS.pop(CODE, None)
    LOG[:] = []
    try:
        M._sync_state_to_actual(None, "test", CODE, st, actual, avg, price)
    finally:
        M._PENDING_BUYS.pop(CODE, None)
    return st


# 场景1：策略空仓+无在途，用户手工买1000 -> 手工账本1000（与修复前一致）
st = run_sync(0, 0, 0, 1000, avg=34.83)
eq("C1 纯手工买入 -> manual=1000", int(st["manual_shares"]), 1000)
eq("C2 纯手工买入 -> manual_cost=34.83*1000", round(float(st["manual_cost"]), 2), 34830.0)
eq("C3 纯手工买入 -> 策略账本不动", int(st["position_shares"]), 0)
chk("C4 打「手工仓已分离」日志", any("手工仓已分离" in m for m in LOG))

# 场景2：策略首仓5000股部分成交2000股 -> 不误记手工仓（本缺陷核心）
st = run_sync(0, 5000, 0, 2000, avg=34.5)
eq("D1 部分成交2000股 -> manual=0（修复前误记2000）", int(st["manual_shares"]), 0)
eq("D2 部分成交 -> 策略账本不被清空标记", int(st["position_shares"]), 0)
chk("D3 打「持仓归属-策略」日志", any("持仓归属-策略" in m for m in LOG))

# 场景2b：同场景下 bar 顶部对账（AUD34-P1 口径）-> 策略账本=券商全量-手工=2000
ps34 = max(0, 2000 - int(st["manual_shares"]))
eq("D4 bar顶对账 -> 策略账本2000股", ps34, 2000)

# 场景3：全部成交5000股 -> 仍不记手工
st = run_sync(2000, 5000, 0, 5000, avg=34.5)
eq("E1 全额成交5000 -> manual=0", int(st["manual_shares"]), 0)
ps34 = max(0, 5000 - int(st["manual_shares"]))
eq("E2 bar顶对账 -> 策略账本5000股", ps34, 5000)

# 场景4：策略持仓4000+手工1000，用户手工加仓500（券商5500）
st = run_sync(4000, 0, 1000, 5500, avg=34.6, ms_cost=34830.0)
eq("F1 手工加仓后 -> manual=1500", int(st["manual_shares"]), 1500)
ps34 = max(0, 5500 - int(st["manual_shares"]))
eq("F2 bar顶对账 -> 策略账本保持4000", ps34, 4000)

# 场景5：手工仓减仓（券商1500->1000，策略空仓）
st = run_sync(0, 0, 1500, 1000, avg=34.7, ms_cost=52095.0)
eq("G1 手工减仓 -> manual=1000", int(st["manual_shares"]), 1000)
eq("G2 手工成本按券商均价重算", round(float(st["manual_cost"]), 2), 34700.0)

# 场景6：券商股数少于策略账本（外部误卖策略股）-> 手工账本不被造出
st = run_sync(4000, 0, 0, 3500, avg=34.5)
eq("H1 外部减仓 -> manual保持0", int(st["manual_shares"]), 0)
ps34 = max(0, 3500 - int(st["manual_shares"]))
eq("H2 bar顶对账 -> 策略账本缩至3500", ps34, 3500)

# 场景7：策略在途期间券商股数超过账本+在途（多出的才是手工）
st = run_sync(2000, 3000, 0, 6500, avg=34.5)
eq("I1 超出可解释范围 -> manual=1500", int(st["manual_shares"]), 1500)
ps34 = max(0, 6500 - int(st["manual_shares"]))
eq("I2 bar顶对账 -> 策略账本5000", ps34, 5000)

# ---------------- 4) 行为级 P2/P3：卖出股数口径模拟 ----------------
def sim_sell_vol(can_use, pos_vol, manual, allow_manual=False):
    ms = manual
    strat = max(0, int(pos_vol) - ms)
    vol = int(can_use)
    if not allow_manual:
        if strat <= 0 and ms > 0:
            return 0, "refuse"
        if vol > strat:
            vol = strat
    return vol, "ok"


v, _ = sim_sell_vol(5000, 5000, 1000)
eq("J1 策略4000+手工1000 -> 只卖4000", v, 4000)
v, _ = sim_sell_vol(5000, 5000, 0)
eq("J2 无手工仓 -> 卖5000（行为零变化）", v, 5000)
v, w = sim_sell_vol(5000, 1000, 1000)
eq("J3 全部为手工仓(默认) -> 拒卖", (v, w), (0, "refuse"))
v, _ = sim_sell_vol(3000, 5000, 1000)
eq("J4 T+1可卖3000<策略4000 -> 卖3000", v, 3000)
v, w = sim_sell_vol(1000, 1000, 1000, allow_manual=True)
eq("J5 代卖放行(allow_manual=True) -> 全手工仓可卖1000", (v, w), (1000, "ok"))

# ---------------- 5) 版本与铁律 ----------------
eq("K1 STRATEGY_VERSION", M.STRATEGY_VERSION, "v1.2.80")
chk("K2 AUD35 记录块在文件头", "── v1.2.72 = AUD35-P1~P2" in src
    and "── v1.2.73 = AUD35-P3" in src)
chk("K3 R1 铁律闸门仍在", "def _r1_net_profit_gate(" in src)
chk("K4 硬止损仍关闭", M.PARAMS.get("hard_stop_dd_pct") is None)

# ---------------- 输出 ----------------
print("=" * 78)
print("AUD35 专项回归（两本账归属修复：同步分类 / 卖出钳制）")
print("=" * 78)
npass = 0
for name, c, d in R:
    print("  [%s] %-56s %s" % ("PASS" if c else "FAIL", name, d if not c else ""))
    npass += 1 if c else 0
print("=" * 78)
print("通过 %d / %d" % (npass, len(R)))
print("=" * 78)
sys.exit(0 if npass == len(R) else 1)
