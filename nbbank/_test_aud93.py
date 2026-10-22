# -*- coding: utf-8 -*-
"""AUD93 专项回归：佣金按「每张委托单 5 元起」全量对齐（v1.2.75 引入，版本断言随交付件滚动到 v1.2.77）

覆盖：
  P1：order_commission 逐单 5 元底（含多单各一次底）；9 处费用点统一走它；
      shrink_for_fee 下单前按含费成本预留（防「刚好够」废单）
  P2：手工仓「距止盈线需现价」反推含 5 元底（原纯费率偏乐观）

本脚本 exec GBK 交付件，进程内数值/行为验证，不联网、不下单。
"""
import io
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")

M = type(sys)("m93")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)

import tempfile
tmp = tempfile.mkdtemp(prefix="_a93_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp

R = []
CODE = "002142.SZ"


def chk(name, cond, detail=""):
    R.append((name, bool(cond), detail))


def near(name, got, want, tol=1e-6):
    chk(name, abs(float(got) - float(want)) <= tol, "got=%.6f want=%.6f" % (got, want))


M.log = lambda m: None
M._save_fail_alert = lambda *a, **k: None

# ---------------- 1) 佣金逐单 5 元底 ----------------
near("A1 6000元单 -> 佣金5元（触发起收）", M.order_commission(6000), 5.0)
near("A2 10万元单 -> 佣金8.41元（费率占优）", M.order_commission(100000),
     100000 * M.STOCK_COMMISSION_RATE)
near("A3 6000元拆3张单 -> 3x5=15元（每单各一个底）",
     M.order_commission(6000, n_orders=3), 15.0)
near("A4 30万元拆3张单 -> 按单均分取底",
     M.order_commission(300000, n_orders=3),
     3 * max(100000 * M.STOCK_COMMISSION_RATE, 5.0))
near("A5 金额0 -> 佣金0", M.order_commission(0), 0.0)
near("A6 负金额 -> 佣金0", M.order_commission(-100), 0.0)
near("A7 自定义费率/起收（回测口径兼容）",
     M.order_commission(10000, 1, 0.00025, 5.0), 5.0)
near("A8 自定义费率大额（回测口径兼容）",
     M.order_commission(100000, 1, 0.00025, 5.0), 25.0)
near("A9 n_orders 非法值按1张处理", M.order_commission(6000, n_orders=0), 5.0)

# ---------------- 2) 买入成本含费口径 ----------------
amt = 100 * 34.9
near("B1 compute_buy_cost = 金额+佣金5元+过户万1",
     M.compute_buy_cost(100, 34.9),
     amt + 5.0 + amt * M.STOCK_TRANSFER_FEE_RATE)
near("B2 大额买入佣金按费率（不被5元底拉低）",
     M.compute_buy_cost(3000, 34.9),
     3000 * 34.9 + 3000 * 34.9 * M.STOCK_COMMISSION_RATE
     + 3000 * 34.9 * M.STOCK_TRANSFER_FEE_RATE)

# ---------------- 3) 下单前含费预留 ----------------
chk("C1 正常现金（远超含费成本）不缩量",
    M.shrink_for_fee(1100, 34.9, 4000000.0) == 1100)
chk("C2 现金刚好覆盖含费成本 -> 保留",
    M.shrink_for_fee(1100, 34.9, M.compute_buy_cost(1100, 34.9)) == 1100)
chk("C3 现金差几元不够费用 -> 按整手收缩",
    M.shrink_for_fee(1100, 34.9, M.compute_buy_cost(1100, 34.9) - 1.0) == 1000)
chk("C4 只够名义额、不够费用 -> 收缩到0（不废单）",
    M.shrink_for_fee(100, 34.9, 3493.0) == 0)
chk("C5 非法入参安全返回", M.shrink_for_fee(0, 34.9, 1000.0) == 0
    and M.shrink_for_fee(100, 0.0, 1000.0) == 100)

# ---------------- 4) R1 铁律闸门按逐单底计费 ----------------
st = M.new_state()
st["position_shares"] = 0
st["total_cost"] = 0.0
ok, det = M._r1_net_profit_gate(CODE, 100, 34.80, 36.00, st, "测试")
_mv = round(36.00 * (1 - M.LIMIT_SLIP_PCT_SELL), 2) * 100
_fee_want = (max(_mv * M.STOCK_COMMISSION_RATE, M.STOCK_COMMISSION_MIN)
             + _mv * M.STOCK_STAMP_TAX_RATE + _mv * M.STOCK_TRANSFER_FEE_RATE)
near("D1 闸门费用=佣金5元底+印花+过户", det.get("fee", -1), _fee_want, 1e-6)
chk("D2 赚钱时放行", ok is True)
ok2, det2 = M._r1_net_profit_gate(CODE, 100, 35.99, 36.00, st, "测试")
chk("D3 不赚钱时拒卖（铁律不变）", ok2 is False, str(det2.get("why")))

# ---------------- 5) 反推含 5 元底（P2） ----------------
_mvol, _cost = 1000, 34835.10
_tp = 0.04
_target = _cost * (1.0 + _tp)
# 旧口径（纯费率，无 5 元底）
_px_old = _target / _mvol / (1.0 - M.STOCK_STAMP_TAX_RATE
                             - M.STOCK_TRANSFER_FEE_RATE - M.STOCK_COMMISSION_RATE)
# 新口径（与代码同款：3 次迭代）
_px_new = _px_old
for _ in range(3):
    _mv_t = _px_new * _mvol
    _fee_t = (M.order_commission(_mv_t) + _mv_t * M.STOCK_STAMP_TAX_RATE
              + _mv_t * M.STOCK_TRANSFER_FEE_RATE)
    _px_new = (_target + _fee_t) / _mvol
gain_old = _px_old * _mvol - (M.order_commission(_px_old * _mvol)
                              + _px_old * _mvol * M.STOCK_STAMP_TAX_RATE
                              + _px_old * _mvol * M.STOCK_TRANSFER_FEE_RATE)
gain_new = _px_new * _mvol - (M.order_commission(_px_new * _mvol)
                              + _px_new * _mvol * M.STOCK_STAMP_TAX_RATE
                              + _px_new * _mvol * M.STOCK_TRANSFER_FEE_RATE)
chk("E1 新反推价高于旧价（补上5元底后需更高价才够止盈）", _px_new > _px_old,
    "old=%.4f new=%.4f" % (_px_old, _px_new))
chk("E2 旧口径在旧价上达不到止盈目标（证明原先显示偏低）", gain_old < _target - 1e-6,
    "gain_old=%.4f target=%.4f" % (gain_old, _target))
chk("E3 新口径在新价上刚好达标（误差<0.5元）", abs(gain_new - _target) < 0.5,
    "gain_new=%.4f target=%.4f" % (gain_new, _target))

# ---------------- 6) 源码级：收口与生效位置 ----------------
import re
chk("F1 无残留内联 max(金额x费率,5元)",
    len(re.findall(r"max\(\w+ \* STOCK_COMMISSION_RATE, STOCK_COMMISSION_MIN\)", src)) == 0)
chk("F2 9 处费用点统一走 order_commission", src.count("order_commission(") >= 12)
chk("F3 四处下单定量点按含费成本预留", src.count("shrink_for_fee(vol, price,") == 5)
chk("F4 印花/过户无起收概念，仍按金额另算",
    "STOCK_STAMP_TAX_RATE" in src and "STOCK_TRANSFER_FEE_RATE" in src)

# ---------------- 输出 ----------------
npass = sum(1 for _, c, _ in R if c)
print("=" * 70)
for name, c, d in R:
    print("  [%s] %s %s" % ("PASS" if c else "FAIL", name, d))
print("=" * 70)
print("AUD93 专项：通过 %d / %d" % (npass, len(R)))
sys.exit(0 if npass == len(R) else 1)
