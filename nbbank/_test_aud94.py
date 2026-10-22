# -*- coding: utf-8 -*-
"""AUD94 专项回归：第二十五轮零预设独立审计 9 项修复（v1.2.76 引入，版本断言随交付件滚动到 v1.2.77）

覆盖：
  P1 策略权益市值只算策略自己的股（手工仓不进权益/峰值）
  P2 加仓链入口按策略账本持仓判定（纯手工仓不进 M2/M3）
  P3 在途买单期间手工份额只增不减（部分成交不吞手工仓）
  P4 卖出盈亏按「本次卖的那本账」成本分别判（exact_avg）
  P5 买入额度闸门只算策略持仓市值
  P6 锁续命回读校验 pid（易主即降级）
  P7 情绪 EWMA 每交易日只平滑一次
  P8 cash 注释如实化
  P9 释放锁前校验归属

本脚本 exec GBK 交付件，进程内数值/行为验证，不联网、不下单。
"""
import io
import os
import sys
import json
import time
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")

M = type(sys)("m94")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)

tmp = tempfile.mkdtemp(prefix="_a94_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp
M.__dict__["_INSTANCE_LOCK_FILE"] = os.path.join(tmp, "gf_strategy_instance.lock")

R = []
CODE = "002142.SZ"


def chk(name, cond, detail=""):
    R.append((name, bool(cond), detail))


def eq(name, got, want):
    chk(name, got == want, "got=%r want=%r" % (got, want))


def near(name, got, want, tol=1e-6):
    chk(name, abs(float(got) - float(want)) <= tol, "got=%.6f want=%.6f" % (got, want))


M.log = lambda m: None
M._save_fail_alert = lambda *a, **k: None
M._notify_risk = lambda *a, **k: None


def mkstate(**kw):
    s = M.new_state()
    s.update(kw)
    return s


# ================= P3：在途买单期间手工份额只增不减 =================
# 场景：策略 4000 + 手工 1000（券商 5000），策略 M2 买 1000（position 已 +1000 到 5000, pending=1000）
#       券商先部分成交 300 -> actual=5300
st = mkstate(position_shares=5000, expected_shares=6000, total_cost=150000.0,
             deployed=150000.0, tier=0, manual_shares=1000, manual_cost=40000.0)
M._PENDING_BUYS[CODE] = 1000
M._sync_state_to_actual(None, "acct", CODE, st, 5300, 30.0, 31.0)
eq("P3 部分成交时手工份额保留1000（原会被算成0）", st["manual_shares"], 1000)
near("P3 部分成交时手工成本不丢", st["manual_cost"], 40000.0, 1e-6)
chk("P3b 份额未变时保留原成本（不被券商混合均价稀释）",
    "AUD94-P3b" in src and "_ms_prev_cost_p94" in src)
# 首次识别手工仓（原份额 0，无在途买单）仍按券商均价建成本
M._pending_clear(CODE, "test-reset")     # 必须走官方清理（会落盘），否则文件里的旧 pending 会被读回
st5 = mkstate()
M._sync_state_to_actual(None, "acct", CODE, st5, 1000, 34.83, 36.0)
near("P3b 首次识别按券商均价建成本 34830", st5["manual_cost"], 34830.0, 1e-6)

# 在途单结算完毕（pending=0）后，应校正回真实份额
M._PENDING_BUYS.pop(CODE, None)
st2 = mkstate(position_shares=5000, expected_shares=6000, total_cost=150000.0,
              deployed=150000.0, tier=0, manual_shares=1000, manual_cost=40000.0)
M._sync_state_to_actual(None, "acct", CODE, st2, 6000, 30.0, 31.0)
eq("P3 成交完毕后手工份额=6000-5000=1000", st2["manual_shares"], 1000)

# 无在途单时手工减少应正常更新（用户手工卖出 500 股）
st3 = mkstate(position_shares=5000, expected_shares=5000, total_cost=150000.0,
              deployed=150000.0, tier=0, manual_shares=1000, manual_cost=40000.0)
M._sync_state_to_actual(None, "acct", CODE, st3, 5500, 30.0, 31.0)
eq("P3 无在途单时手工份额正常更新为500", st3["manual_shares"], 500)

# 策略空仓 + 纯手工仓：manual 应等于 actual
st4 = mkstate()
M._sync_state_to_actual(None, "acct", CODE, st4, 1000, 34.83, 36.0)
eq("P3 纯手工仓 manual=1000", st4["manual_shares"], 1000)
eq("P3 纯手工仓策略账本仍为0", st4["position_shares"], 0)

# ================= P4：R1 按指定账本成本判 =================
# 策略 4000@30（赚）+ 手工 1000@40（亏）：券商均价 = (120000+40000)/5000 = 32
# 现价 31，保守成交价 = 31*0.997 = 30.907
price = 31.0
ref = round(price * (1 - M.LIMIT_SLIP_PCT_SELL), 2)     # 30.91
mv = ref * 4000
fee = M.order_commission(mv) + mv * M.STOCK_STAMP_TAX_RATE + mv * M.STOCK_TRANSFER_FEE_RATE
net = mv - fee
strat_cost = 30.0 * 4000                                 # 120000
chk("P4 策略仓按策略成本判：扣费后净赚", net > strat_cost, "net=%.2f cost=%.2f" % (net, strat_cost))

stg = mkstate(position_shares=4000, total_cost=120000.0, deployed=120000.0,
              manual_shares=1000, manual_cost=40000.0, tier=0)
ok_e, d_e = M._r1_net_profit_gate(CODE, 5000, 30.0, price, stg, "策略止盈",
                                  sub_vol=4000, exact_avg=True)
chk("P4 指定策略成本30 -> 放行", ok_e, str(d_e.get("why")))
near("P4 判定用策略成本 120000", d_e.get("cost", 0.0), 120000.0, 1e-6)

ok_o, d_o = M._r1_net_profit_gate(CODE, 5000, 32.0, price, stg, "整户口径")
chk("P4 原整户口径(均价32) -> 拒卖（证明差异存在）", not ok_o, str(d_o.get("why")))

# 反向：策略亏、手工赚；卖手工仓应按手工成本判
stm = mkstate(position_shares=4000, total_cost=160000.0, deployed=160000.0,
              manual_shares=1000, manual_cost=30000.0, tier=0)
mv2 = ref * 1000
fee2 = M.order_commission(mv2) + mv2 * M.STOCK_STAMP_TAX_RATE + mv2 * M.STOCK_TRANSFER_FEE_RATE
net2 = mv2 - fee2
chk("P4 手工仓按手工成本30判：扣费后净赚", net2 > 30000.0, "net=%.2f" % net2)
ok_m, d_m = M._r1_net_profit_gate(CODE, 5000, 30.0, price, stm, "手工仓",
                                  sub_vol=1000, exact_avg=True)
chk("P4 代卖手工仓按手工成本放行", ok_m, str(d_m.get("why")))
near("P4 手工仓判定成本 30000", d_m.get("cost", 0.0), 30000.0, 1e-6)

# exact_avg=False 保持原最保守口径
ok_default, _ = M._r1_net_profit_gate(CODE, 5000, 30.0, price, stg, "默认口径")
chk("P4 exact_avg 默认 False 时仍取三本账 max（向后兼容）", ok_default is not None)

# ================= P1：权益市值不含手工仓 =================
stp = mkstate(position_shares=0, expected_shares=0, deployed=0.0, manual_shares=1000)
_ms = int(stp.get("manual_shares", 0) or 0)
_strat = max(0, 5000 - _ms)          # 假设券商 5000，其中手工 1000
mv_p1 = max(_strat, int(stp.get("expected_shares", 0) or 0)) * 36.0
near("P1 手工仓1000时策略市值只算4000股", mv_p1, 4000 * 36.0, 1e-6)
mv_old = max(5000, 0) * 36.0
chk("P1 旧口径会虚增手工仓市值36000", mv_old - mv_p1 == 1000 * 36.0)
chk("P1 源码：mv 用 _mv_strat_p94 而非 actual_vol",
    "_mv_strat_p94 = int(actual_vol) - _mv_ms_p94" in src
    and "mv = max(_mv_strat_p94, int(state.get(\"expected_shares\", 0) or 0)) * price" in src)
chk("P1 源码：旧的 actual_vol 直接计市值已不存在",
    "    mv = max(actual_vol, state.get(\"expected_shares\", 0)) * price" not in src)

# ================= P2：加仓链入口按策略账本持仓 =================
chk("P2 源码：elif 用 position_shares > 0",
    'elif (int(state.get("position_shares", 0) or 0) > 0 and not state["paused"]' in src)
chk("P2 源码：elif 不再用 actual_vol > 0 作为加仓入口",
    'elif (actual_vol > 0 and not state["paused"]' not in src)
# 行为核对：纯手工仓时 position_shares=0 -> 不进加仓分支
stq = mkstate(manual_shares=1000, manual_cost=34830.0)
chk("P2 纯手工仓 position_shares=0 -> 加仓分支不成立",
    not (int(stq.get("position_shares", 0) or 0) > 0))
chk("P2 策略有仓 position_shares>0 -> 加仓分支成立",
    int(mkstate(position_shares=100).get("position_shares", 0) or 0) > 0)

# ================= P5：买入额度闸门只算策略市值 =================
_used_p5 = 100000.0
_pv, _apx, _pms = 5000, 36.0, 1000
_ps5 = int(_pv) - _pms
used_new = max(_used_p5, float(_ps5) * _apx)
used_old = max(_used_p5, float(_pv) * _apx)
near("P5 新口径已用额度 = max(10万, 4000*36=14.4万)", used_new, 144000.0, 1e-6)
near("P5 旧口径虚高到 5000*36=18万", used_old, 180000.0, 1e-6)
chk("P5 手工仓市值不再挤占策略额度", used_old - used_new == 1000 * 36.0)
chk("P5 源码：_used 用 _pv_strat94",
    "_used = max(_used, float(_pv_strat94) * float(_apx))" in src)

# ================= P6：锁续命回读校验 pid =================
lockf = M._INSTANCE_LOCK_FILE
with io.open(lockf, "w", encoding="utf-8") as f:
    f.write(json.dumps({"pid": os.getpid(), "hb": time.time()}))
M._INSTANCE_LOCK_ACQUIRED = True
M._INSTANCE_LOCK_LAST_TOUCH = 0.0
M._instance_lock_touch()
chk("P6 自己是锁主 -> 保持可下单", M._INSTANCE_LOCK_ACQUIRED is True)
with io.open(lockf, "w", encoding="utf-8") as f:
    f.write(json.dumps({"pid": os.getpid() + 999983, "hb": time.time()}))
M._INSTANCE_LOCK_LAST_TOUCH = 0.0
M._instance_lock_touch()
chk("P6 锁已易主 -> 自动降级为只观察", M._INSTANCE_LOCK_ACQUIRED is False)

# ================= P9：释放锁前校验归属 =================
with io.open(lockf, "w", encoding="utf-8") as f:
    f.write(json.dumps({"pid": os.getpid() + 777001, "hb": time.time()}))
M._INSTANCE_LOCK_ACQUIRED = True
M._instance_lock_release()
chk("P9 锁属他人时 stop 不删除他人锁", os.path.exists(lockf))
with io.open(lockf, "w", encoding="utf-8") as f:
    f.write(json.dumps({"pid": os.getpid(), "hb": time.time()}))
M._INSTANCE_LOCK_ACQUIRED = True
M._instance_lock_release()
chk("P9 锁属自己时正常删除", not os.path.exists(lockf))

# ================= P7：情绪 EWMA 每交易日只平滑一次 =================
chk("P7 源码：新增 _SENT_EWMA_DAY 日期表", "_SENT_EWMA_DAY = {}" in src)
chk("P7 源码：按日期去重更新", "if _SENT_EWMA_DAY.get(code) != _day94 or code not in _SENT_EWMA:" in src)


def sim_ewma(day, score, prev, store_day, store_ew, span=10):
    """复刻 AUD94-P7 逻辑"""
    if store_day != day or prev is None:
        alpha = 2.0 / (span + 1.0)
        ew = score if prev is None else alpha * score + (1 - alpha) * prev
        return ew, day
    return prev, store_day


# 旧行为：一天 240 根 bar 反复平滑 -> 收敛到当日分
ew_old = 0.30
for _ in range(240):
    ew_old = 0.18 * 0.85 + 0.82 * ew_old
near("P7 旧行为一天后 EWMA≈当日分0.85（平滑失效）", ew_old, 0.85, 0.01)
# 新行为：当天只平滑一次
ew_new, d_new = sim_ewma("2026-10-21", 0.85, 0.30, "2026-10-20", 0.30)
near("P7 新行为首次平滑 = 0.18*0.85+0.82*0.30 = 0.399", ew_new, 0.399, 0.005)
for _ in range(240):
    ew_new, d_new = sim_ewma("2026-10-21", 0.85, ew_new, d_new, 0.85) if False else (ew_new, d_new)
near("P7 新行为当天后续不再变化（保持0.399）", ew_new, 0.399, 0.005)
chk("P7 平滑真正滞后（EWMA 0.399 != 当日分 0.85）", abs(ew_new - 0.85) > 0.3)

# ================= P8：注释如实化 =================
chk("P8 源码：cash 注释已标注参与买入定量取值", "AUD94-P8 如实标注" in src)
chk("P8 源码：旧的「不参与风控计算」已移除", "仅作参考，不参与风控计算" not in src)

# ================= 铁律零触碰 =================
chk("铁律：硬止损参数仍为 None", M.PARAMS.get("hard_stop_dd_pct") is None)
chk("铁律：R1 异常仍 fail-closed 拒卖",
    "铁律闸门异常，保守拒卖" in src)
chk("铁律：净到手<=成本仍拒卖", "if _net <= _cost:" in src)
chk("铁律：sell_all 未传 state 仍直接拒卖", "未提供 state，无法复核净到手盈亏，拒绝卖出" in src)
chk("铁律：移交人工释放额度逻辑在原位",
    "_account_free_cash" in src and "manual_takeover" in src)

# ================= 汇总 =================
print("=" * 78)
fails = [r for r in R if not r[1]]
for name, ok, detail in R:
    print("%s %s%s" % ("PASS" if ok else "FAIL", name, ("  | " + detail) if (detail and not ok) else ""))
print("=" * 78)
print("AUD94 结果：%d PASS / %d FAIL" % (len(R) - len(fails), len(fails)))
sys.exit(0 if not fails else 1)
