# -*- coding: utf-8 -*-
"""诊断：F2 大盘过滤取数为何"经常误报数据未就绪"。

用真实交付件里的 _get_index_closes_yday / _idx_fetch_with_fallback / _get_hist，
只替换行情接口（fake C），逐个还原真实 QMT 可能返回的形态。
"""
import io
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")

src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")
M = type(sys)("mod")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)
tmp = tempfile.mkdtemp(prefix="_idxdiag_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp

# 停掉真实补下载与告警写盘
M._try_download_hist = lambda code, force=False: False
LOGS = []
M.log = lambda m: LOGS.append(str(m))

BASE_PX = 4480.0


class DF(object):
    def __init__(self, vals, last_key=""):
        self._v = list(vals)
        self.columns = ["close"]
        self.index = ["2026-10-%02d" % ((i % 28) + 1) for i in range(len(self._v))]
        if last_key and self.index:
            self.index[-1] = last_key

    def __len__(self):
        return len(self._v)

    def __getitem__(self, k):
        return self._v


class FakeC(object):
    """可配置两个接口各返回多少根、是否带当日 bar、老接口是否拿到个股数据。"""

    def __init__(self, n_ex=70, n_old=70, ex_ok=True, old_ok=True,
                 old_is_stock=False, ex_has_today=True, ex_fill_zero=0):
        self.n_ex, self.n_old = n_ex, n_old
        self.ex_ok, self.old_ok = ex_ok, old_ok
        self.old_is_stock = old_is_stock
        self.ex_has_today = ex_has_today
        self.ex_fill_zero = ex_fill_zero

    def get_market_data_ex(self, fields, codes, period="1d", count=0,
                           dividend_type=None, fill_data=False):
        code = codes[0]
        if not self.ex_ok:
            return {}
        n = min(int(count), self.n_ex)
        vals = [BASE_PX + i for i in range(n)]
        if self.ex_fill_zero and fill_data:
            vals = [0.0] * self.ex_fill_zero + vals[:-self.ex_fill_zero] if self.ex_fill_zero < len(vals) else vals
        last_key = "20261019" if self.ex_has_today else "20261016"
        return {code: DF(vals, last_key)}

    def get_history_data(self, n, period, field, dividend_type=None):
        if not self.old_ok:
            return []
        n = min(int(n), self.n_old)
        px = 20.0 if self.old_is_stock else BASE_PX
        return [px + i * 0.1 for i in range(n)]


def run(label, **kw):
    M._MARKET_IDX_CACHE.update({"ts": 0.0, "closes": None, "diag": ""})
    M._IDX_ALERT.update({"fail": 0, "last_warn_ts": 0.0, "suppress_dl_until": 0.0})
    M._IDX_LASTDATE.update({"day": "", "bar": ""})
    del LOGS[:]
    C = FakeC(**kw)
    closes, diag = M._get_index_closes_yday(C, 60)
    ok = closes is not None and len(closes) >= 60
    ma20 = M._ma_of(closes, 20) if closes else None
    ma60 = M._ma_of(closes, 60) if closes else None
    verdict = "放行" if ok else "拦截(误报?)"
    print("%-46s -> %s" % (label, verdict))
    print("      返回根数=%s  diag=%s" % (len(closes) if closes else 0, diag))
    if ma20 is not None:
        print("      MA20=%.2f MA60=%.2f" % (ma20, ma60))
    if LOGS:
        for l in LOGS[:3]:
            print("      日志: %s" % l[:110])
    print("")


print("=" * 90)
print("模拟真实 QMT 各种返回形态 —— 看哪些会误报『数据未就绪』")
print("=" * 90)
print("")

run("S0 基准：新接口 70 根，含当日 bar（理想态）", n_ex=70, n_old=70)
run("S1 新接口 70 根，但盘中不含当日 bar", n_ex=70, n_old=70, ex_has_today=False)
run("S2 新接口 66 根（本地只存 66 根）", n_ex=66, n_old=66)
run("S3 新接口 65 根（本地只存 65 根）", n_ex=65, n_old=65)
run("S4 新接口 65 根，老接口能拿 70 根", n_ex=65, n_old=70)
run("S5 新接口 3 根，老接口能拿 70 根", n_ex=3, n_old=70)
run("S6 新接口空，老接口 70 根", n_ex=0, n_old=70, ex_ok=False)
run("S7 新接口空，老接口返回个股序列", n_ex=0, n_old=70, ex_ok=False, old_is_stock=True)
run("S8 新接口 fill 补 5 个 0 值", n_ex=65, n_old=65, ex_fill_zero=5)
run("S9 新接口 65 根 + fill 补 5 个 0", n_ex=60, n_old=60, ex_fill_zero=5)


print("=" * 90)
print("数据门视角：本地 65 根时还会不会弹「数据未就绪」")
print("=" * 90)
M._try_download_hist = lambda code, force=False: False
for _n in (65, 60, 66):
    M._MARKET_IDX_CACHE.update({"ts": 0.0, "closes": None, "diag": ""})
    M._IDX_LASTDATE.update({"day": "", "bar": ""})
    M._IDX_ALERT.update({"fail": 0, "last_warn_ts": 0.0, "suppress_dl_until": 0.0})
    _items = M._data_gate_index_items(FakeC(n_ex=_n, n_old=_n))
    print("  本地 %2d 根 -> 缺失项 %d 个 %s" % (_n, len(_items), _items if _items else "(放行)"))
