# -*- coding: utf-8 -*-
"""
============================================================================
 候选方案滚动窗口对比 —— 止盈/追涨参数最终选型
============================================================================
 方法：6 个月滚动窗口、步长 1 个月（约 30 个窗口，窗口间有重叠，仅用于
       稳健性比较，不作为独立样本做统计检验）+ 4 个年度区间。
 输出：均收益 / 中位收益 / 平均回撤 / 最差窗口回撤 / Calmar / 回撤>20% 窗口数
============================================================================
"""
import io
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
             "pyramid": [0.50, 0.25, 0.10, 0.05], "add_step_pct": 0.02})
OPTS = {"cooldown_days": 3, "daily_add_cap": 90000.0}

CANDS = [
    ("A 现状 8%/5+3/6%",      0.08, (0.05, 0.03), 0.06),
    ("B 备忘 6%/4+4/20%",     0.06, (0.04, 0.04), 0.20),
    ("C 4%/3+2/6%(低回撤)",   0.04, (0.03, 0.02), 0.06),
    ("D 10%/5+3/6%",          0.10, (0.05, 0.03), 0.06),
    ("E 8%/3+2/6%(紧移动)",   0.08, (0.03, 0.02), 0.06),
    ("F 6%/5+3/6%",           0.06, (0.05, 0.03), 0.06),
    ("G 12%/5+3/6%",          0.12, (0.05, 0.03), 0.06),
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


def run(rows, ic, tp, tr, ma, ps, pe):
    P = dict(BASE)
    P["take_profit_pct"] = tp
    P["trailing_activate_pct"] = tr[0]
    P["trailing_dd_pct"] = tr[1]
    P["trend_max_above_pct"] = ma
    return B.run_backtest(rows, ic, P, dict(OPTS), ps, pe)


def avg(v):
    return sum(v) / len(v) if v else 0.0


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    rows, ic = data()
    dates = [r["date"] for r in rows]
    print("数据 %d 根  %s ~ %s\n" % (len(rows), dates[0], dates[-1]))

    # 6 个月窗口，步长 1 个月
    wins = []
    i0 = next(i for i, d in enumerate(dates) if d >= "2023-07-01")
    STEP = 20          # 约 1 个月交易日
    WLEN = 122         # 约 6 个月交易日
    while i0 + WLEN < len(rows):
        wins.append((dates[i0], dates[min(i0 + WLEN, len(rows) - 1)]))
        i0 += STEP
    print("滚动窗口 %d 个（6 个月窗 / 步长 1 个月）\n" % len(wins))

    hdr = (" %-24s" % "候选方案" + "".join("%9s" % p for p, _, _ in YEARS)
           + "%9s%9s%9s" % ("年均", "均回撤", "最差"))
    print("=" * 104)
    print("① 年度区间表现")
    print("=" * 104)
    print(hdr)
    print("-" * 104)

    year_tbl = {}
    for name, tp, tr, ma in CANDS:
        rets, dds = [], []
        cells = []
        for _, ps, pe in YEARS:
            r = run(rows, ic, tp, tr, ma, ps, pe)
            rets.append(r["return_pct"]); dds.append(r["max_drawdown_pct"])
            cells.append("%+8.2f%%" % r["return_pct"])
        year_tbl[name] = (rets, dds)
        print(" %-24s%s%+8.2f%%%8.2f%%%8.2f%%"
              % (name, "".join(cells), avg(rets), avg(dds), max(dds)))
    print()

    print("=" * 104)
    print("② 滚动窗口表现（稳健性主判据）")
    print("=" * 104)
    print(" %-24s %9s %9s %9s %9s %9s %9s %s"
          % ("候选方案", "均收益", "中位收益", "平均回撤", "最差回撤", "Calmar",
             "正收益窗", "回撤>20%窗"))
    print("-" * 104)
    roll = {}
    for name, tp, tr, ma in CANDS:
        rets, dds = [], []
        for ps, pe in wins:
            r = run(rows, ic, tp, tr, ma, ps, pe)
            rets.append(r["return_pct"]); dds.append(r["max_drawdown_pct"])
        pos = sum(1 for x in rets if x > 0)
        bad = sum(1 for x in dds if x > 20.0)
        calmar = avg(rets) / max(dds) if max(dds) > 0 else 0
        roll[name] = (rets, dds)
        print(" %-24s %+8.2f%% %+8.2f%% %8.2f%% %8.2f%% %8.3f %6d/%d %7d"
              % (name, avg(rets), median(rets), avg(dds), max(dds), calmar, pos, len(wins), bad))
    print()

    # 两两对比（A 为基准）
    print("=" * 104)
    print("③ 以 A 为基准的逐窗口胜负（窗口数 %d）" % len(wins))
    print("=" * 104)
    a_rets = roll[CANDS[0][0]][0]
    a_dds = roll[CANDS[0][0]][1]
    for name, _, _, _ in CANDS[1:]:
        for tag, arr in (("收益", roll[name][0]), ("回撤(越小越好)", roll[name][1])):
            base = a_rets if tag == "收益" else a_dds
            if tag == "收益":
                w = sum(1 for x, y in zip(arr, base) if x > y + 1e-9)
                l = sum(1 for x, y in zip(arr, base) if x < y - 1e-9)
            else:
                w = sum(1 for x, y in zip(arr, base) if x < y - 1e-9)
                l = sum(1 for x, y in zip(arr, base) if x > y + 1e-9)
            t = len(wins) - w - l
            print("  %-24s %-16s  该方案胜 %2d / 平 %2d / A胜 %2d" % (name, tag, w, t, l))
    print()

    print("=" * 104)
    print("④ 决策摘要")
    print("=" * 104)
    best_ret = max(CANDS, key=lambda c: avg(roll[c[0]][0]))
    best_cal = max(CANDS, key=lambda c: (avg(roll[c[0]][0]) / max(roll[c[0]][1])
                                         if max(roll[c[0]][1]) > 0 else 0))
    best_dd = min(CANDS, key=lambda c: max(roll[c[0]][1]))
    print("  滚动均收益最高 : %s  (%+.2f%%)" % (best_ret[0], avg(roll[best_ret[0]][0])))
    print("  Calmar 最高    : %s  (%.3f)" % (best_cal[0],
                                     avg(roll[best_cal[0]][0]) / max(roll[best_cal[0]][1])))
    print("  最差回撤最小   : %s  (%.2f%%)" % (best_dd[0], max(roll[best_dd[0]][1])))


if __name__ == "__main__":
    main()
