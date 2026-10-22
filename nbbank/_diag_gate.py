# -*- coding: utf-8 -*-
"""AUD26 诊断：个股数据门 + fetch_hist_fields 的新门槛实测。

回答两个问题：
  1. 本地 N 根时，数据门放不放行？
  2. 数据门放行后，指标取数环节会不会又拦？（末根为当日 / 非当日 两种）
"""
import io
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")

M = type(sys)("mod26")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)

tmp = tempfile.mkdtemp(prefix="_a26_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp

ISSUES = []
M.log = lambda m: None
M._log_hist_issue = lambda code, msg, force=False: ISSUES.append(msg)

OUT = []
OUT.append("版本 %s | ma_long=%d | 数据门请求=%d 判定=%d"
           % (M.STRATEGY_VERSION, M.PARAMS.get("ma_long"),
              M.PARAMS.get("ma_long") + 10, M.PARAMS.get("ma_long")))
OUT.append("")

# ================= 1. 个股数据门 =================
OUT.append("=" * 76)
OUT.append("1) 个股数据门 _data_gate_symbol_items")
OUT.append("=" * 76)
OUT.append("%-8s %-6s %s" % ("本地根数", "结果", "文案"))
OUT.append("-" * 76)
for n in (55, 59, 60, 62, 64, 65, 70, 120):
    M._get_hist = (lambda nn: (lambda C, code, field, n=120, old_require_code=False:
                               ([10.0 + i * 0.01 for i in range(min(nn, n))], "ex/f/ratio", None)))(n)
    items = M._data_gate_symbol_items(None, "002142.SZ")
    OUT.append("%-10d %-8s %s" % (n, "拦截" if items else "放行",
                                  items[0][2] if items else "—"))

# ================= 2. fetch_hist_fields =================
OUT.append("")
OUT.append("=" * 76)
OUT.append("2) 指标取数 fetch_hist_fields（含末根口径）")
OUT.append("=" * 76)
OUT.append("%-10s %-12s %-8s %s" % ("本地根数", "末根", "结果", "说明"))
OUT.append("-" * 76)


def make_hist4(nn, last_key):
    def _f(C, code, n, div, use_fill):
        k = min(nn, n)
        base = 10.0
        return ([base + i * 0.01 for i in range(k)],
                [base + i * 0.01 + 0.05 for i in range(k)],
                [base + i * 0.01 - 0.05 for i in range(k)],
                [1000.0] * k, last_key)
    return _f


TODAY = "20261019"
YDAY = "20261016"
for nn, lk, label in ((59, YDAY, "昨日"), (60, TODAY, "当日"), (60, YDAY, "昨日"),
                      (61, TODAY, "当日"), (64, TODAY, "当日"), (65, YDAY, "昨日")):
    ISSUES.clear()
    M._hist4_from_ex = make_hist4(nn, lk)
    M._hist4_from_old = lambda *a, **k: None
    M._HIST_CACHE.pop("002142.SZ", None)
    M._HIST_FAIL_CACHE.pop("002142.SZ", None)
    M._HIST_DL_LAST.pop("002142.SZ", None)
    M._HIST_DL_CNT.pop("002142.SZ", None)
    M._try_download_hist = lambda code, force=False: False
    r = M.fetch_hist_fields(None, "002142.SZ", M.PARAMS)
    res = "放行" if r is not None else "拦截"
    note = ("closes=%d flag=%s" % (len(r[0]), r[4])) if r is not None else (ISSUES[0] if ISSUES else "无说明")
    OUT.append("%-12d %-14s %-10s %s" % (nn, label, res, note))

io.open("_a26b_out.txt", "w", encoding="utf-8", newline="").write("\n".join(OUT))
print("ok")
