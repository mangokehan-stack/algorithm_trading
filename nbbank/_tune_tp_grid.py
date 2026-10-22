# -*- coding: utf-8 -*-
"""
============================================================================
 止盈 / 移动止盈 / 追涨上限 —— 参数网格寻优（20 万口径）
============================================================================
 目的：回答「止盈 6%/移动 4%+4%/追涨 20%」vs「止盈 8%/移动 5%+3%/追涨 6%」
       哪一组「收益更高且回撤更小」，用回测证据代替猜测。

 口径与实盘一致：
   · 资金 20 万（init_capital=max_invest=200000）
   · M3 单档 6000 元 / 累计上限 3 万（B.M3_LEVELS / B.M3_CUM_CAP 覆盖）
   · 共享单日加仓额度 9 万、卖出冷却 3 天（与实盘 P0 口径一致）
   · 金字塔 [0.50,0.25,0.10,0.05]、每跌 2%
   · 佣金万2.5+过户费万0.1+印花税万5、涨停不买跌停不卖、前复权

 网格：
   take_profit_pct          ∈ TP_LIST
   (trailing_activate, dd)  ∈ TR_LIST
   trend_max_above_pct      ∈ MA_LIST

 区间：2023H2 / 2024 / 2025 / 2026(至行情末端)
   ▸ 样本内(IS) = 2023H2 + 2024；样本外(OS) = 2025 + 2026
     先用 IS 选优、再看 OS 是否站得住 —— 防止网格搜索过拟合。

 输出：_tune_tp_grid.json + 控制台排名表
============================================================================
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import backtest_optimize as B          # noqa: E402

# ---------------- 20 万口径覆盖（必须与实盘一致）----------------
B.M3_LEVELS = [(0.025, 6000.0)]
B.M3_CUM_CAP = 30000.0
B.M3_MAX_TRIGGERS_PER_DAY = 1

BASE = dict(B.BASE_PARAMS)
BASE.update({
    "init_capital": 200000.0,
    "max_invest": 200000.0,
    "pyramid": [0.50, 0.25, 0.10, 0.05],
    "add_step_pct": 0.02,
})
OPTS = {"cooldown_days": 3, "daily_add_cap": 90000.0}

# ---------------- 区间 ----------------
PERIODS = [
    ("2023H2", "2023-07-01", "2023-12-31"),
    ("2024",   "2024-01-01", "2024-12-31"),
    ("2025",   "2025-01-01", "2025-12-31"),
    ("2026",   "2026-01-01", "2026-12-31"),
]
IS_KEYS = ("2023H2", "2024")          # 样本内
OS_KEYS = ("2025", "2026")            # 样本外

# ---------------- 网格 ----------------
TP_LIST = [0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.12]
TR_LIST = [(0.03, 0.02), (0.03, 0.03), (0.04, 0.02), (0.04, 0.03),
           (0.04, 0.04), (0.05, 0.03), (0.05, 0.04), (0.06, 0.04)]
MA_LIST = [0.06, 0.08, 0.10, 0.15, 0.20, 0.25]

FOCUS = {
    "现状A(8%/5%+3%/6%)":  (0.08, (0.05, 0.03), 0.06),
    "备忘B(6%/4%+4%/20%)": (0.06, (0.04, 0.04), 0.20),
}


def build_data():
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


def run_one(rows, ic, tp, tr, ma, pstart, pend):
    P = dict(BASE)
    P["take_profit_pct"] = tp
    P["trailing_activate_pct"] = tr[0]
    P["trailing_dd_pct"] = tr[1]
    P["trend_max_above_pct"] = ma
    O = dict(OPTS)
    return B.run_backtest(rows, ic, P, O, pstart, pend)


def avg(vals):
    return sum(vals) / len(vals) if vals else 0.0


def main():
    t0 = time.time()
    print("拉取行情 ...")
    rows, ic = build_data()
    print("股票 %d 根  %s ~ %s" % (len(rows), rows[0]["date"], rows[-1]["date"]))
    print("网格: TP %d x TR %d x MA %d = %d 组 x %d 区间\n"
          % (len(TP_LIST), len(TR_LIST), len(MA_LIST),
             len(TP_LIST) * len(TR_LIST) * len(MA_LIST), len(PERIODS)))

    results = []
    total = len(TP_LIST) * len(TR_LIST) * len(MA_LIST)
    done = 0
    for tp in TP_LIST:
        for tr in TR_LIST:
            for ma in MA_LIST:
                per = {}
                for pname, ps, pe in PERIODS:
                    r = run_one(rows, ic, tp, tr, ma, ps, pe)
                    per[pname] = {"ret": r["return_pct"],
                                  "dd": r["max_drawdown_pct"],
                                  "buy": r["buy_cnt"], "sell": r["sell_cnt"]}
                rets = [per[p]["ret"] for p in per]
                dds = [per[p]["dd"] for p in per]
                is_ret = avg([per[p]["ret"] for p in IS_KEYS])
                is_dd = max(per[p]["dd"] for p in IS_KEYS)
                os_ret = avg([per[p]["ret"] for p in OS_KEYS])
                os_dd = max(per[p]["dd"] for p in OS_KEYS)
                results.append({
                    "tp": tp, "tr_a": tr[0], "tr_d": tr[1], "ma": ma,
                    "per": per,
                    "avg_ret": avg(rets), "worst_dd": max(dds),
                    "is_ret": is_ret, "is_dd": is_dd,
                    "os_ret": os_ret, "os_dd": os_dd,
                    "calmar": (avg(rets) / max(dds)) if max(dds) > 0 else 0.0,
                    "is_calmar": (is_ret / is_dd) if is_dd > 0 else 0.0,
                    "os_calmar": (os_ret / os_dd) if os_dd > 0 else 0.0,
                    "buys": sum(per[p]["buy"] for p in per),
                    "sells": sum(per[p]["sell"] for p in per),
                })
                done += 1
    print("完成 %d 组，用时 %.1fs\n" % (done, time.time() - t0))

    def show(title, key, sub=None, n=15, rev=True):
        print("=" * 104)
        print(title)
        print("=" * 104)
        print(" %-6s %-11s %-6s | %8s %8s | %8s %8s | %8s | %s"
              % ("TP", "移动(激活/回撤)", "追涨", "全期均收益", "全期最大回撤",
                 "样本内", "样本内回撤", "样本外", "Calmar  买/卖"))
        print("-" * 104)
        srt = sorted(results, key=lambda x: x[key], reverse=rev)
        if sub:
            srt = [r for r in srt if sub(r)]
        for r in srt[:n]:
            print(" %-6.2f %-11s %-6.2f | %+7.2f%% %7.2f%% | %+7.2f%% %7.2f%% | %+7.2f%% | %6.3f  %d/%d"
                  % (r["tp"], "%.2f/%.2f" % (r["tr_a"], r["tr_d"]), r["ma"],
                     r["avg_ret"], r["worst_dd"], r["is_ret"], r["is_dd"],
                     r["os_ret"], r["calmar"], r["buys"], r["sells"]))
        print()

    show("【一】按全期 Calmar（收益/回撤 综合效率）降序 —— 主排序", "calmar")
    show("【二】按全期平均收益降序", "avg_ret")
    show("【三】按全期最大回撤升序（越小越好）", "worst_dd", rev=False)

    print("=" * 104)
    print("【四】样本内选优 → 样本外检验（防过拟合）")
    print("=" * 104)
    is_best = sorted(results, key=lambda x: x["is_calmar"], reverse=True)[:8]
    print(" 样本内(2023H2+2024) Calmar 前 8，及其样本外(2025+2026)表现：")
    print(" %-6s %-11s %-6s | %8s %8s | %8s %8s" %
          ("TP", "移动", "追涨", "IS均收益", "IS最大回撤", "OS均收益", "OS最大回撤"))
    print("-" * 104)
    for r in is_best:
        print(" %-6.2f %-11s %-6.2f | %+7.2f%% %7.2f%% | %+7.2f%% %7.2f%%"
              % (r["tp"], "%.2f/%.2f" % (r["tr_a"], r["tr_d"]), r["ma"],
                 r["is_ret"], r["is_dd"], r["os_ret"], r["os_dd"]))
    print()

    print("=" * 104)
    print("【五】焦点方案直接对比")
    print("=" * 104)
    print(" %-22s %-6s %-11s %-6s | %8s %8s | %8s %8s | %8s %8s"
          % ("方案", "TP", "移动", "追涨", "23H2", "2024", "2025", "2026",
             "全期均", "最大回撤"))
    print("-" * 104)
    focus_rows = {}
    for name, (tp, tr, ma) in FOCUS.items():
        hit = [r for r in results
               if abs(r["tp"] - tp) < 1e-9 and abs(r["tr_a"] - tr[0]) < 1e-9
               and abs(r["tr_d"] - tr[1]) < 1e-9 and abs(r["ma"] - ma) < 1e-9]
        if not hit:
            print(" %-22s 组合不在网格内" % name)
            continue
        r = hit[0]
        focus_rows[name] = r
        print(" %-22s %-6.2f %-11s %-6.2f | %+7.2f%% %+7.2f%% %+7.2f%% %+7.2f%% | %+7.2f%% %7.2f%%"
              % (name, r["tp"], "%.2f/%.2f" % (r["tr_a"], r["tr_d"]), r["ma"],
                 r["per"]["2023H2"]["ret"], r["per"]["2024"]["ret"],
                 r["per"]["2025"]["ret"], r["per"]["2026"]["ret"],
                 r["avg_ret"], r["worst_dd"]))
    print()

    # 稳健性：最优组合邻域（是否参数平原）
    best = sorted(results, key=lambda x: x["calmar"], reverse=True)[0]
    nb = [r for r in results
          if abs(r["tp"] - best["tp"]) <= 0.011 and abs(r["ma"] - best["ma"]) <= 0.021
          and abs(r["tr_a"] - best["tr_a"]) <= 0.011 and abs(r["tr_d"] - best["tr_d"]) <= 0.011]
    print("=" * 104)
    print("【六】最优组合邻域稳健性（参数平原检验）")
    print("=" * 104)
    print(" 最优: TP=%.2f  移动=%.2f/%.2f  追涨=%.2f  →  均收益 %+.2f%% / 最大回撤 %.2f%% / Calmar %.3f"
          % (best["tp"], best["tr_a"], best["tr_d"], best["ma"],
             best["avg_ret"], best["worst_dd"], best["calmar"]))
    if nb:
        print(" 邻域 %d 组：均收益 %.2f%%~%.2f%%（均值 %+.2f%%），最大回撤 %.2f%%~%.2f%%，Calmar 均值 %.3f"
              % (len(nb), min(x["avg_ret"] for x in nb), max(x["avg_ret"] for x in nb),
                 avg([x["avg_ret"] for x in nb]),
                 min(x["worst_dd"] for x in nb), max(x["worst_dd"] for x in nb),
                 avg([x["calmar"] for x in nb])))
    else:
        print(" 邻域无相同取值组（网格步长限制）")
    print()

    outp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tune_tp_grid.json")
    with io.open(outp, "w", encoding="utf-8") as f:
        json.dump({
            "note": "止盈/移动止盈/追涨上限 网格寻优（20万口径，日线回测）",
            "data_range": [rows[0]["date"], rows[-1]["date"]],
            "periods": [p[0] for p in PERIODS],
            "is_keys": list(IS_KEYS), "os_keys": list(OS_KEYS),
            "grid": {"tp": TP_LIST, "tr": TR_LIST, "ma": MA_LIST},
            "focus": {k: list(v[0:1]) + [list(v[1])] + [v[2]] for k, v in FOCUS.items()},
            "best_calmar": best,
            "focus_rows": focus_rows,
            "all": results,
        }, f, ensure_ascii=False, indent=1)
    print("已输出 %s（%d 组）" % (os.path.basename(outp), len(results)))


if __name__ == "__main__":
    main()
