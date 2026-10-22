# -*- coding: utf-8 -*-
"""
============================================================================
 框架方案第二阶段：以 F2（首仓加沪深300 大盘过滤）为底的组合搜索
============================================================================
 第一阶段结论（_tune_frame.py）：F2 单独 = 均收益 +7.00%、最差回撤 9.45%、
   Calmar 0.740、回撤>20% 窗口 0 —— 唯一「收益升 + 回撤大降」的杠杆。
 本脚本回答：F2 之上还要不要再叠 W（首仓降重）/ T（盈利减仓）/ 斜率门？
 方法与数据同 _tune_frame.py（33 滚动窗口 + 4 年度，2023-01-01~2026-08-26）。
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
             "take_profit_pct": 0.04,
             "trailing_activate_pct": 0.03, "trailing_dd_pct": 0.02})
OPTS = {"cooldown_days": 3, "daily_add_cap": 90000.0}

TIERS = [(0.03, 1 / 3.0), (0.04, 1 / 3.0), (0.06, 1.0)]
W_PYM = [0.35, 0.25, 0.10, 0.05]
F2 = {"market_filter": True}

ARMS = [
    ("0 基线 C组(现状)",            {}),
    ("F2 大盘过滤",                F2),
    ("F2+W1 首仓35%",              dict(F2, _p={"pyramid": W_PYM})),
    ("F2+W2 首仓35+间距3%",         dict(F2, _p={"pyramid": W_PYM, "add_step_pct": 0.03})),
    ("F2+T1 浮盈3%减半",            dict(F2, profit_trim=(0.03, 0.5))),
    ("F2+T3 阶梯止盈3/4/6",         dict(F2, tp_tiers=TIERS)),
    ("F2+O12 MA20斜率门",           dict(F2, bull_slope_gate=True)),
    ("F2+W2+T1",                 dict(F2, profit_trim=(0.03, 0.5),
                                      _p={"pyramid": W_PYM, "add_step_pct": 0.03})),
    ("F2+W1+T3",                 dict(F2, tp_tiers=TIERS, _p={"pyramid": W_PYM})),
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
    wins = []
    i0 = next(i for i, d in enumerate(dates) if d >= "2023-07-01")
    STEP, WLEN = 20, 122
    while i0 + WLEN < len(rows):
        wins.append((dates[i0], dates[min(i0 + WLEN, len(rows) - 1)]))
        i0 += STEP
    print("数据 %d 根 | 滚动窗口 %d 个\n" % (len(rows), len(wins)))

    out = {"windows": len(wins), "arms": {}}

    print("=" * 116)
    print("① 年度区间")
    print("=" * 116)
    print(" %-26s" % "方案" + "".join("%10s" % p for p, _, _ in YEARS)
          + "%10s%10s%10s" % ("年均", "均回撤", "最差"))
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

    print("=" * 116)
    print("② 滚动窗口（主判据）")
    print("=" * 116)
    print(" %-26s %9s %9s %9s %9s %8s %8s %8s %9s" % (
        "方案", "均收益", "中位收益", "平均回撤", "最差回撤", "Calmar",
        "正收益窗", "回撤>20%", "买卖次数"))
    print("-" * 116)
    roll = {}
    for name, arm in ARMS:
        rets, dds = [], []
        nbuy = nsell = 0
        for ps, pe in wins:
            r = run_arm(rows, ic, arm, ps, pe)
            rets.append(r["return_pct"]); dds.append(r["max_drawdown_pct"])
            nbuy += r["buy_cnt"]; nsell += r["sell_cnt"]
        pos = sum(1 for x in rets if x > 0)
        bad = sum(1 for x in dds if x > 20.0)
        calmar = avg(rets) / max(dds) if max(dds) > 0 else 0
        roll[name] = {"rets": rets, "dds": dds, "avg_ret": avg(rets),
                      "med_ret": median(rets), "avg_dd": avg(dds),
                      "max_dd": max(dds), "calmar": calmar, "pos": pos,
                      "bad": bad, "avg_buy": nbuy / len(wins),
                      "avg_sell": nsell / len(wins)}
        print(" %-26s %+8.2f%% %+8.2f%% %8.2f%% %8.2f%% %8.3f %5d/%d %6d %4.1f/%4.1f"
              % (name, avg(rets), median(rets), avg(dds), max(dds), calmar,
                 pos, len(wins), bad, nbuy / len(wins), nsell / len(wins)))
    print()

    print("=" * 116)
    print("③ 逐窗口胜负（基准 = F2）")
    print("=" * 116)
    f2 = roll["F2 大盘过滤"]
    for name, _ in ARMS:
        if name.startswith("F2 "):
            continue
        rr, dd = roll[name]["rets"], roll[name]["dds"]
        rw = sum(1 for x, y in zip(rr, f2["rets"]) if x > y + 1e-9)
        rl = sum(1 for x, y in zip(rr, f2["rets"]) if x < y - 1e-9)
        dw = sum(1 for x, y in zip(dd, f2["dds"]) if x < y - 1e-9)
        dl = sum(1 for x, y in zip(dd, f2["dds"]) if x > y + 1e-9)
        print("  %-26s 收益 胜%2d/平%2d/负%2d   回撤 改善%2d/持平%2d/恶化%2d"
              % (name, rw, len(wins) - rw - rl, rl,
                 dw, len(wins) - dw - dl, dl))

    out["year"] = {n: {"rets": year_tbl[n][0], "dds": year_tbl[n][1]} for n, _ in ARMS}
    out["roll"] = roll
    with io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "_tune_frame2.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\n已输出 _tune_frame2.json")


if __name__ == "__main__":
    main()
