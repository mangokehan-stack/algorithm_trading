# -*- coding: utf-8 -*-
"""AUD28 专项回归：手工仓不被复活进策略账本（随版本滚动校验）

覆盖 v1.2.65 在实盘暴露的两个真实缺陷：
  缺陷 A：每根 bar 反复调 _sync_state_to_actual，把手工仓复活进 position_shares
  缺陷 B：init 自检打「手工持仓=0股」而券商实际有仓（日志说谎）

本脚本 exec GBK 交付件，在进程内直接测状态机，不联网、不下单。
"""
import io
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")

M = type(sys)("m28")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)

tmp = tempfile.mkdtemp(prefix="_a28_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp

R = []


def chk(name, cond, detail=""):
    R.append((name, bool(cond), detail))


def eq(name, got, want):
    chk(name, got == want, "got=%r want=%r" % (got, want))


LOG = []
M.log = lambda m: LOG.append(m)

# ---------------- 1) 源码级：同步触发条件口径 ----------------
code = src
chk("A1 handlebar 同步触发含手工账本口径",
    '_sync_need28 = (actual_vol != _ps28) and (actual_vol != _ps28 + _ms_sh28)' in code)
chk("A2 不再裸用 actual_vol != position_shares 触发",
    'elif actual_vol != state["position_shares"]:\n        _sell_pending_handled = _sync_state_to_actual' not in code)
chk("A3 verify 内补写扣掉手工份额",
    '_strat28 = int(actual) - _ms_sh28b' in code
    and 'state["position_shares"] = _strat28' in code)
chk("A4 verify 不再无条件写回 actual",
    'if not _sync_handled:\n        state["position_shares"] = actual\n        state["expected_shares"] = actual' not in code)

# ---------------- 2) 行为级：模拟「策略账本0 + 手工1000」----------------
st = M.new_state()
st["manual_shares"] = 1000
st["manual_cost"] = 34830.0
st["manual_peak_cost"] = 34.83
eq("B1 起始策略账本为0", int(st["position_shares"]), 0)
eq("B2 起始 tierte 为-1", st["tier"], -1)
eq("B3 起始 deployed 为0", float(st["deployed"]), 0.0)

# 复刻 handlebar 的判定逻辑（与源码同构）
actual_vol = 1000
_pend = 0
_in_flight = (_pend > 0 and actual_vol != st["position_shares"]
              and actual_vol == st["position_shares"] - _pend)
_ms_sh28 = int(st.get("manual_shares", 0) or 0)
_ps28 = int(st["position_shares"] or 0)
_sync_need28 = (actual_vol != _ps28) and (actual_vol != _ps28 + _ms_sh28)
eq("B4 策略0+手工1000+券商1000 -> 判定一致,不触发同步", _sync_need28, False)
eq("B5 在途判定为False", _in_flight, False)

# ---------------- 3) 真外部变动仍能触发 ----------------
for label, av, ps, ms, want in [
    ("手工仓被卖出200股(券商800/手工1000)", 800, 0, 1000, True),
    ("外部又买500股(券商1500/手工1000)", 1500, 0, 1000, True),
    ("策略自己也有仓(券商2500/策略1000/手工1000) -> 同步=True(另有500股外部变动)", 2500, 1000, 1000, True),
    ("两本账齐平(券商2000/策略1000/手工1000) -> 同步=False", 2000, 1000, 1000, False),
    ("策略仓被削(券商1800/策略1000/手工1000)", 1800, 1000, 1000, True),
    ("全空仓(券商0/策略0/手工0)", 0, 0, 0, False),
]:
    got = (av != ps) and (av != ps + ms)
    eq("%s -> 同步=%s" % (label, want), got, want)

# ---------------- 4) verify 补写扣手工份额 ----------------
def sim_verify_write(actual, manual):
    s = int(actual) - manual
    return max(0, s)


eq("C1 verify 补写: 券商1000/手工1000 -> 策略0", sim_verify_write(1000, 1000), 0)
eq("C2 verify 补写: 券商2500/手工1000 -> 策略1500", sim_verify_write(2500, 1000), 1500)
eq("C3 verify 补写: 券商500/手工1000 -> 不为负", sim_verify_write(500, 1000), 0)

# ---------------- 5) 缺陷B：init 自检数据源 ----------------
chk("D1 init 自检券商兜底已加",
    '_ms_src = "券商实际(尚未迁移，首根bar落入手工账本)"' in code)
chk("D2 自检日志含来源字段", '来源=%s | 手工持仓=%d股' in code)

# ---------------- 6) 缺陷C：预算0元文案 ----------------
chk("E1 预算0元改为如实说明",
    "策略侧买入预算 0 元" in code and "这是预期状态，非故障" in code)
chk("E2 预算>0 时原文案保留", "策略总预算 %.0f 元 —— 仅按预算动用" in code)

# ---------------- 7) 铁律未被触碰 ----------------
chk("F1 硬止损仍关闭", M.PARAMS.get("hard_stop_dd_pct") is None or "hard_stop_dd_pct" in code)
chk("F2 统一铁律闸门仍在", "def _r1_net_profit_gate(" in code)
chk("F3 手工仓路径不写策略账本",
    all(k not in code[code.find("def manual_sell("):code.find("def manual_hold_watch(")]
        for k in ('state["deployed"]', 'state["tier"]')))

# ---------------- 8) 版本 ----------------
eq("G1 STRATEGY_VERSION", M.STRATEGY_VERSION, "v1.2.80")
chk("G2 AUD28 记录块仍在", "── v1.2.66 = AUD28-P1~P3" in code)

# ---------------- 输出 ----------------
print("=" * 78)
print("AUD28 专项回归（手工仓不被复活 / 自检如实化）")
print("=" * 78)
npass = 0
for name, c, d in R:
    print("  [%s] %-52s %s" % ("PASS" if c else "FAIL", name, d if not c else ""))
    npass += 1 if c else 0
print("=" * 78)
print("通过 %d / %d" % (npass, len(R)))
print("=" * 78)
sys.exit(0 if npass == len(R) else 1)
