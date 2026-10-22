# -*- coding: utf-8 -*-
"""
============================================================================
 框架级降回撤方案对比（不动母版，纯回测研究）
============================================================================
 背景：C 组止盈（4%/3+2/6）已把最差回撤压到 27.65%，但仍远超躺平线 8%。
       要再压必须动框架 —— 本脚本量化四个方向（均不触碰「亏损不卖」红线）：
   F 熊市过滤加严：F1 熊市冻结 M2/M3 加仓（现状只挡首仓）；F2 首仓加大盘过滤；
                  F4 躺平线 8% -> 6%（只停买，绝不卖）
   W 首仓降重    ：pyramid[0] 50% -> 35%（可选加仓间距 2% -> 3%）
   T 分批减仓    ：仅盈利侧 —— 浮盈达标先卖一部分落袋，余仓继续让利润奔跑
   G 组合        ：F+W / F+W+T
 方法：与 _tune_roll.py 完全同口径 —— 6 个月滚动窗口（约 33 个，步长 1 个月）
       + 4 个年度区间；数据 2023-01-01 ~ 2026-08-26（与止盈选型轮同一份，
       保证与「C 组 6.00% / 27.65%」可比）。
 基线校验：第 0 号臂 = 现状（C 组，不带任何新开关），其结果必须复现
       止盈选型轮的 C 组数字，否则说明内核被改坏，本表作废。
 输出：_tune_frame.json（供方案文档引用）
============================================================================
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import backtest_optimize as B          # noqa: E402

B.M3_LEVELS = [(0.025, 6000.0)]
B.M3_CUM_CAP = 30000.0
B.M3_MAX_TRIGGERS_PER_DAY = 1

BASE = dict(B.BASE_PARAMS)
BASE.update({"init_capital": 200000.0, "max_invest": 200000.0,
             "pyramid": [0.50, 0.25, 0.10, 0.05], "add_step_pct": 0.02,
             # C 组止盈（2026-09-28 在役参数）
             "take_profit_pct": 0.04,
             "trailing_activate_pct": 0.03, "trailing_dd_pct": 0.02})
OPTS = {"cooldown_days": 3, "daily_add_cap": 90000.0}

TIERS = [(0.03, 1 / 3.0), (0.04, 1 / 3.0), (0.06, 1.0)]
W_PYM = [0.35, 0.25, 0.10, 0.05]

ARMS = [
    ("0 基线 C组(现状)",        {}),
    ("F1 熊市冻结加仓",         {"bear_adds_freeze": True}),
    ("F2 首仓加大盘过滤",       {"market_filter": True}),
    ("F3 F1+首仓大盘过滤",      {"bear_adds_freeze": True, "market_filter": True}),
    ("F4 躺平线 8%->6%",       {"_p": {"max_drawdown_pct": 0.06}}),
    ("W1 首仓 50%->35%",       {"_p": {"pyramid": W_PYM}}),
    ("W2 首仓35%+间距2->3%",    {"_p": {"pyramid": W_PYM, "add_step_pct": 0.03}}),
    ("W3 W2+熊市冻结加仓",      {"bear_adds_freeze": True,
                                "_p": {"pyramid": W_PYM, "add_step_pct": 0.03}}),
    ("T1 浮盈3%先减半(余仓续持)", {"profit_trim": (0.03, 0.5)}),
    ("T2 浮盈2.5%先减1/3",      {"profit_trim": (0.025, 1 / 3.0)}),
    ("T3 阶梯止盈 3/4/6 清仓",   {"tp_tiers": TIERS}),
    ("G1 F3+W2",              {"bear_adds_freeze": True, "market_filter": True,
                               "_p": {"pyramid": W_PYM, "add_step_pct": 0.03}}),
    ("G2 F3+W2+T1",           {"bear_adds_freeze": True, "market_filter": True,
                               "profit_trim": (0.03, 0.5),
                               "_p": {"pyramid": W_PYM, "add_step_pct": 0.03}}),
    ("G3 F3+W2+T3",           {"bear_adds_freeze": True, "market_filter": True,
                               "tp_tiers": TIERS,
                               "_p": {"pyramid": W_PYM, "add_step_pct": 0.03}}),
    ("G4 F1+W2+T1",           {"bear_adds_freeze": True, "profit_trim": (0.03, 0.5),
                               "_p": {"pyramid": W_PYM, "add_step_pct": 0.03}}),
]

YEARS = [("2023H2", "2023-07-01", "2023-12-31"),
         ("2024", "2024-01-01", "2024-12-31"),
         ("2025", "2025-01-01", "2025-12-31"),
         ("2026", "2026-01-01", "2026-12-31")]


def data():
    sr = B.fetch_rows(B.STOCK_SECID, qfq=True)
    ir = B.fetch_rows(B.INDEX_SECID, qfq=False)
    m = {r["date"]: r["close"] for r in ir}
    ic, prev = [], next(iter(m.values()))
    for r in sr:
        c = m.get(r["date"])
        if c is None:
            c = prev
        else:
            prev = c
        ic.append(c)
    return sr, ic


def run_arm(rows, ic, arm, ps, pe):
    P = dict(BASE)
    P.update(dict(arm.get("_p") or {}))
    o = dict(OPTS)
    for k, v in arm.items():
        if k != "_p":
            o[k] = v
    return B.run_backtest(rows, ic, P, o, ps, pe)


def avg(v):
    return sum(v) / len(v) if v else 0.0


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    rows, ic = data()
    dates = [r["date"] for r in rows]
    print("数据 %d 根  %s ~ %s" % (len(rows), dates[0], dates[-1]))

    wins = []
    i0 = next(i for i, d in enumerate(dates) if d >= "2023-07-01")
    STEP, WLEN = 20, 122
    while i0 + WLEN < len(rows):
        wins.append((dates[i0], dates[min(i0 + WLEN, len(rows) - 1)]))
        i0 += STEP
    print("滚动窗口 %d 个（6 个月窗 / 步长 1 个月）\n" % len(wins))

    out = {"windows": len(wins), "data_range": [dates[0], dates[-1]], "arms": {}}

    # ---- ① 年度区间 ----
    print("=" * 116)
    print("① 年度区间表现")
    print("=" * 116)
    hdr = (" %-26s" % "方案" + "".join("%10s" % p for p, _, _ in YEARS)
           + "%10s%10s%10s" % ("年均", "均回撤", "最差"))
    print(hdr)
    print("-" * 116)
    year_tbl = {}
    for name, arm in ARMS:
        rets, dds, cells = [], [], []
        for _, ps, pe in YEARS:
            r = run_arm(rows, ic, arm, ps, pe)
            rets.append(r["return_pct"]); dds.append(r["max_drawdown_pct"])
            cells.append("%+9.2f%%" % r["return_pct"])
        year_tbl[name] = (rets, dds)
        print(" %-26s%s%+9.2f%%%9.2f%%%9.2f%%"
              % (name, "".join(cells), avg(rets), avg(dds), max(dds)))
    print()

    # ---- ② 滚动窗口（主判据）----
    print("=" * 116)
    print("② 滚动窗口表现（稳健性主判据）")
    print("=" * 116)
    print(" %-26s %9s %9s %9s %9s %8s %8s %8s" % (
        "方案", "均收益", "中位收益", "平均回撤", "最差回撤", "Calmar",
        "正收益窗", "回撤>20%"))
    print("-" * 116)
    roll = {}
    for name, arm in ARMS:
        rets, dds, buys, sells = [], [], [], []
        for ps, pe in wins:
            r = run_arm(rows, ic, arm, ps, pe)
            rets.append(r["return_pct"]); dds.append(r["max_drawdown_pct"])
            buys.append(r["buy_cnt"]); sells.append(r["sell_cnt"])
        pos = sum(1 for x in rets if x > 0)
        bad = sum(1 for x in dds if x > 20.0)
        calmar = avg(rets) / max(dds) if max(dds) > 0 else 0
        roll[name] = {"rets": rets, "dds": dds,
                      "avg_ret": avg(rets), "med_ret": median(rets),
                      "avg_dd": avg(dds), "max_dd": max(dds),
                      "calmar": calmar, "pos": pos, "bad": bad,
                      "avg_buy": avg(buys), "avg_sell": avg(sells)}
        print(" %-26s %+8.2f%% %+8.2f%% %8.2f%% %8.2f%% %8.3f %5d/%d %6d"
              % (name, avg(rets), median(rets), avg(dds), max(dds),
                 calmar, pos, len(wins), bad))
    print()

    # ---- ③ 逐窗口胜负（以基线为基准）----
    print("=" * 116)
    print("③ 逐窗口胜负（基准 = 0 基线 C组，窗口数 %d）" % len(wins))
    print("=" * 116)
    base = roll[ARMS[0][0]]
    for name, _ in ARMS[1:]:
        rr, dd = roll[name]["rets"], roll[name]["dds"]
        rw = sum(1 for x, y in zip(rr, base["rets"]) if x > y + 1e-9)
        rl = sum(1 for x, y in zip(rr, base["rets"]) if x < y - 1e-9)
        dw = sum(1 for x, y in zip(dd, base["dds"]) if x < y - 1e-9)
        dl = sum(1 for x, y in zip(dd, base["dds"]) if x > y + 1e-9)
        print("  %-26s 收益 胜%2d/平%2d/负%2d   回撤 改善%2d/持平%2d/恶化%2d"
              % (name, rw, len(wins) - rw - rl, rl,
                 dw, len(wins) - dw - dl, dl))
    print()

    # ---- ④ 决策摘要 ----
    print("=" * 116)
    print("④ 决策摘要")
    print("=" * 116)
    bmax = base["max_dd"]
    cand = [(n, roll[n]) for n, _ in ARMS[1:]]
    print("  基线：均收益 %+.2f%% / 最差回撤 %.2f%% / Calmar %.3f"
          % (base["avg_ret"], bmax, base["calmar"]))
    lo_dd = min(cand, key=lambda c: c[1]["max_dd"])
    hi_cal = max(cand, key=lambda c: c[1]["calmar"])
    print("  最差回撤最小 : %-26s %.2f%%（较基线 %+.2fpp，均收益 %+.2f%%）"
          % (lo_dd[0], lo_dd[1]["max_dd"], lo_dd[1]["max_dd"] - bmax, lo_dd[1]["avg_ret"]))
    print("  Calmar 最高  : %-26s %.3f（均收益 %+.2f%% / 最差回撤 %.2f%%）"
          % (hi_cal[0], hi_cal[1]["calmar"], hi_cal[1]["avg_ret"], hi_cal[1]["max_dd"]))
    both = [c for c in cand if c[1]["max_dd"] < bmax - 1e-9
            and c[1]["avg_ret"] > base["avg_ret"] - 1e-9]
    if both:
        print("  【收益不降且回撤改善】：%s" % "、".join(c[0] for c in both))
    else:
        print("  【收益不降且回撤改善】：无 —— 所有降回撤方案都有收益代价，需权衡")

    out["year"] = {n: {"rets": year_tbl[n][0], "dds": year_tbl[n][1]}
                   for n, _ in ARMS}
    out["roll"] = {n: {k: v for k, v in roll[n].items()} for n, _ in ARMS}
    with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "_tune_frame.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n已输出 _tune_frame.json")


if __name__ == "__main__":
    main()
