# -*- coding: utf-8 -*-
"""
情绪模块调优 / Walk-forward 回测脚本
====================================
用途
----
1. 用真实日线（沪深300指数 + 002142 宁波银行）重放策略 §5.6 情绪引擎，
   逐日计算 7 个硬指标 -> 滚动分位 -> 复合加权 -> EWMA -> 五档状态；
2. 输出 sentiment_hist.csv 供 Excel/Python 二次分析；
3. 控制台给出分档分布、IC（情绪分与未来收益的秩相关）、Walk-forward 切分建议。

与实盘公式一致性
----------------
- 直接 exec 实盘 GBK 文件，逐日调用实盘 `_sentiment_eval` 本身（而非重写公式），
  指标、分位、加权、平滑、分档与策略逐字一致，不存在"两套公式"漂移。
- 指数序列按策略口径"剔除当日 bar"：对第 t 日传入 0..t+1 根已收盘 bar，
  策略内部剔除最后一根(视为当日)，信号落在 t 日，仅依赖 t 日之前信息（无前视）。
- EWMA 链保留在 _SENT_EWMA[code] 跨日延续（与实盘一致），仅绕过 2s 结果缓存。
- 未来收益 fwd5/fwd20 仅用于统计评估，实盘不回看。

用法
----
    python _tune_sentiment.py [--days 1200] [--out sentiment_hist.csv]

依赖
----
- 可选 akshare（联网拉数）；缺失或网络失败时自动进入 demo 模式，
  使用合成序列完成全流程演示，并在输出中明确标注 demo_mode=True。

输出
----
- sentiment_hist.csv：date/ix_close/stk_close + score/ewma/regime +
  fwd5/fwd20（未来5/20交易日个股收益，评估用）
- 控制台统计：分档分布、各档未来收益均值/胜率、Spearman IC、
  walk-forward 样本内外切分对照
"""
import io, os, sys, math, datetime, argparse, statistics, contextlib, collections


BASE = os.path.dirname(os.path.abspath(__file__))
GBK_PATH = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")


class FakeDF:
    """模拟行情DataFrame：__getitem__ 返回列(list)，__len__ 返回行数。"""
    def __init__(self, **kw):
        self._d = kw

    def __getitem__(self, k):
        return self._d[k]

    def __len__(self):
        return len(self._d["close"])


class FakeC:
    """模拟QMT C对象：仅实现情绪模块用到的 get_market_data_ex。"""
    def __init__(self, closes, vols):
        self.closes, self.vols = closes, vols

    def get_market_data_ex(self, fields, codes, **kw):
        return {codes[0]: FakeDF(close=self.closes, volume=self.vols)}


def load_strategy_internals():
    """exec 实盘 GBK 文件，复用与实盘一致的函数与参数。"""
    with io.open(GBK_PATH, "rb") as f:
        src = f.read().decode("gbk").replace("\r\n", "\n")
    ns = {"__name__": "__tune__"}
    exec(compile(src, GBK_PATH, "exec"), ns)
    return ns


def fetch_akshare(days):
    """拉取沪深300日线与宁波银行前复权日线，按日期内连接对齐。"""
    import akshare as ak
    end = datetime.date.today()
    start = end - datetime.timedelta(days=int(days * 1.6) + 400)
    s, e = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    ix = ak.index_zh_a_hist(symbol="000300", period="daily", start_date=s, end_date=e)
    stk = ak.stock_zh_a_hist(symbol="002142", period="daily", start_date=s, end_date=e, adjust="qfq")
    ix = ix[["日期", "收盘", "成交量"]].rename(columns={"日期": "date", "收盘": "ix_c", "成交量": "ix_v"})
    stk = stk[["日期", "收盘", "成交量"]].rename(columns={"日期": "date", "收盘": "stk_c", "成交量": "stk_v"})
    df = ix.merge(stk, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if len(df) < 80:
        raise RuntimeError("akshare 对齐后数据不足 %d 根" % len(df))
    return df.tail(days).to_dict("records"), False


def fetch_demo(days):
    """无 akshare / 网络失败时的合成演示数据（明确标注 demo）。"""
    import random
    random.seed(42)
    n = max(days, 120)
    rows = []
    d = datetime.date.today() - datetime.timedelta(days=n)
    p_ix, p_stk, v_ix, v_stk = 3000.0, 30.0, 100.0, 50.0
    i = 0
    while len(rows) < n:
        d += datetime.timedelta(days=1)
        if d.weekday() >= 5:
            continue
        drift_ix = 0.0004
        if 30 <= i % 180 < 60:
            drift_ix = -0.006   # 周期内穿插"恐慌段"
        elif 120 <= i % 180 < 150:
            drift_ix = 0.008    # 穿插"狂热段"
        p_ix *= (1 + drift_ix + random.gauss(0, 0.008))
        p_stk *= (1 + drift_ix + random.gauss(0, 0.012))
        v_ix = v_ix * (1.05 if 30 <= i % 180 < 60 or 120 <= i % 180 < 150 else 0.98) + random.uniform(0, 5)
        v_stk = v_stk * (1.04 if 120 <= i % 180 < 150 else 0.98) + random.uniform(0, 2)
        rows.append({"date": d.strftime("%Y-%m-%d"), "ix_c": round(p_ix, 3),
                     "ix_v": round(v_ix, 2), "stk_c": round(p_stk, 3), "stk_v": round(v_stk, 2)})
        i += 1
    return rows, True


def spearman(xs, ys):
    """秩相关系数（无第三方依赖）。"""
    if len(xs) < 10:
        return 0.0

    def rank(v):
        idx = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(idx):
            r[i] = pos + 1
        return r

    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    sx = math.sqrt(sum((x - mx) ** 2 for x in rx))
    sy = math.sqrt(sum((y - my) ** 2 for y in ry))
    return cov / (sx * sy) if sx and sy else 0.0


def replay(ns, rows):
    """逐日调用实盘 _sentiment_eval 重放情绪引擎（EWMA 链保留、绕过2s缓存）。"""
    full_stk = [r["stk_c"] for r in rows]
    n = len(rows)
    status = ns["_SENT_TS"] = {}
    ns["_SENT_EWMA"] = {}
    ns["_SENT_ALERT_TS"] = {}
    ns["_SENT_IDX_CACHE"]["ts"] = 0.0
    ns["_SENT_IDX_CACHE"]["closes"] = None
    ns["_SENT_IDX_CACHE"]["vols"] = None
    out = []
    start = int(ns["SENTIMENT_CFG"]["lookback"]) + 10
    for t in range(start, n - 1):
        window = rows[:t + 2]                       # 传 0..t+1，函数剔除最后1根 => 信号落在 t
        ix_c = [r["ix_c"] for r in window]
        ix_v = [r["ix_v"] for r in window]
        stk_c = [r["stk_c"] for r in window]
        stk_v = [r["stk_v"] for r in window]
        ns["_SENT_IDX_CACHE"]["ts"] = 0.0
        ns["_SENT_IDX_CACHE"]["closes"] = None
        ns["_SENT_IDX_CACHE"]["vols"] = None
        status.clear()                               # 绕过2s结果缓存，但 EWMA 链保留
        C = FakeC(ix_c, ix_v)
        with contextlib.redirect_stdout(io.StringIO()):   # 抑制逐日日志
            base = dict(ns["_sentiment_eval"](C, "002142.SZ", stk_c, stk_v, ns["PARAMS"]))
        if not base.get("ok"):
            continue
        f5 = full_stk[t + 5] / full_stk[t] - 1.0 if t + 5 < n else ""
        f20 = full_stk[t + 20] / full_stk[t] - 1.0 if t + 20 < n else ""
        out.append({"date": rows[t]["date"], "ix_close": ix_c[-2], "stk_close": stk_c[-2],
                    "score": round(base["score"], 4), "ewma": round(base["ew"], 4),
                    "regime": base["regime"], "fwd5": round(f5, 6) if f5 != "" else "",
                    "fwd20": round(f20, 6) if f20 != "" else ""})
    return out


def stats(out):
    n = len(out)
    print("\n==== 分档分布（EWMA 五档）====")
    cnt = collections.Counter(r["regime"] for r in out)
    order = ["panic", "cautious", "neutral", "optimistic", "euphoric"]
    for k in order:
        v = cnt.get(k, 0)
        print("  %-10s %5d  %5.1f%%" % (k, v, 100.0 * v / n if n else 0))
    print("\n==== 各档未来收益（个股） ====")
    print("  %-10s %9s %8s %9s %8s" % ("regime", "fwd5均值", "fwd5胜率", "fwd20均值", "fwd20胜率"))
    for k in order:
        if not cnt.get(k):
            continue
        f5 = [x["fwd5"] for x in out if x["regime"] == k and x["fwd5"] != ""]
        f20 = [x["fwd20"] for x in out if x["regime"] == k and x["fwd20"] != ""]
        m5 = statistics.mean(f5) if f5 else float("nan")
        w5 = sum(1 for v in f5 if v > 0) / len(f5) if f5 else float("nan")
        m20 = statistics.mean(f20) if f20 else float("nan")
        w20 = sum(1 for v in f20 if v > 0) / len(f20) if f20 else float("nan")
        print("  %-10s %9.4f %7.1f%% %9.4f %7.1f%%" % (k, m5, 100 * w5, m20, 100 * w20))
    f5s = [(x["score"], x["fwd5"]) for x in out if x["fwd5"] != ""]
    f20s = [(x["score"], x["fwd20"]) for x in out if x["fwd20"] != ""]
    ic5 = spearman([a for a, _ in f5s], [b for _, b in f5s])
    ic20 = spearman([a for a, _ in f20s], [b for _, b in f20s])
    print("\n==== IC（情绪分与未来收益的秩相关） ====")
    print("  Spearman(score, fwd5)  = %.4f  (样本 %d)" % (ic5, len(f5s)))
    print("  Spearman(score, fwd20) = %.4f  (样本 %d)" % (ic20, len(f20s)))

    print("\n==== Walk-forward 切分建议 ====")
    print("  预热后共 %d 个可评估样本。" % n)
    mid = int(n * 0.7)
    for nm, seg in (("样本内(前70%)", out[:mid]), ("样本外(后30%)", out[mid:])):
        if len(seg) < 30:
            print("  %s 样本不足，跳过" % nm)
            continue
        valid = [x for x in seg if x["fwd5"] != ""]
        ic = spearman([x["score"] for x in valid], [x["fwd5"] for x in valid]) if valid else 0.0
        print("  %s: n=%d IC5=%.4f 分布=%s" % (nm, len(seg), ic, dict(collections.Counter(x["regime"] for x in seg))))
    print("  建议：每 60~120 个交易日滚动重估 IC 与档位阈值，保持 2/8 训练/验证切分；")
    print("  参数只应通过本脚本验证后，再改 SENTIMENT_CFG（不碰 PARAMS，避免触发参数变更告警）。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1200, help="重放交易日数量")
    ap.add_argument("--out", default=os.path.join(BASE, "sentiment_hist.csv"))
    args = ap.parse_args()
    ns = load_strategy_internals()
    demo = False
    try:
        rows, demo = fetch_akshare(args.days)
    except Exception as ex:  # noqa: BLE001
        print("[warn] akshare 拉数失败(%s)，进入 demo 合成数据模式。" % ex)
        rows, demo = fetch_demo(args.days)
    out = replay(ns, rows)
    if not out:
        print("无有效样本，退出。"); return 1
    with io.open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        cols = ["date", "ix_close", "stk_close", "score", "ewma", "regime", "fwd5", "fwd20"]
        f.write(",".join(cols) + "\n")
        for r in out:
            f.write(",".join(str(r.get(c, "")) for c in cols) + "\n")
    print("已输出: %s (%d 行, demo_mode=%s)" % (args.out, len(out), demo))
    stats(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())