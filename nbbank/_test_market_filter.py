# -*- coding: utf-8 -*-
"""
_test_market_filter.py  F2 大盘过滤 + 数据就绪拦截闸门 回归测试（2026-09-28）

背景：
    F2（首仓加沪深300 大盘过滤 MA20>=MA60）与数据就绪拦截闸门（指数/标的数据
    未就绪 -> 拦截交易 + 弹窗列清单 + 用户确认复查后放行）从母版落地到
    native 多标的交付件 / miniQMT / 聚宽版四方。

覆盖用例：
  1  _ma_of 均线计算（正常 / 数据不足）
  2  _get_index_closes_yday 剔除当日进行中 bar（昨日及以前口径，与回测 idx_bull[i-1] 一致）
  3  market_filter_ok 四分支：多头放行 / 空头拦截 / 数据未就绪拦截 / 开关关闭放行
  4  data_gate_ready 拦截-弹窗-确认-放行 全流程（弹窗节流、复查放行、恢复后再拦截）
  5  静态检查：四方源码均含 F2 钩子与闸门调用点（首仓条件 bull and mkt_ok 等）

用法: python _test_market_filter.py
"""
import importlib.util
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))

PASS, FAIL = [], []


def ck(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print("  %-64s %s %s" % (name, "PASS" if cond else "FAIL", extra))


def load_mod(path, name):
    """载入策略模块。GBK 交付件读字节流手工解码（importlib 不认 gbk 声明）。

    沙箱化：exec 后把所有 .log/.json 路径常量重定向到临时目录，
    避免测试写脏工程目录、并触发 QMT 镜像目录被安全中心拦截。
    """
    import tempfile
    full = os.path.join(BASE, path)
    src = io.open(full, "rb").read().decode("gbk").replace("\r\n", "\n")
    mod = type(sys)(name)
    mod.__dict__["__file__"] = full
    exec(compile(src, full, "exec"), mod.__dict__)
    tmp = tempfile.mkdtemp(prefix="_f2test_")
    for k, v in list(mod.__dict__.items()):
        if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
            mod.__dict__[k] = os.path.join(tmp, os.path.basename(v))
    mod.__dict__["_MIRROR_DIR"] = ""          # 关闭镜像
    mod.__dict__["_BASE_DIR"] = tmp
    return mod


# 2026-10-19恢复：UTF-8 母版已按用户要求删除，改直读 GBK 唯一交付件
M = load_mod("gf_qmt_native_multi_gbk.py", "nbbank_master_f2test")

print("=" * 80)
print("1) _ma_of 均线计算")
print("=" * 80)
ck("正常均线", abs(M._ma_of([1.0, 2.0, 3.0], 3) - 2.0) < 1e-9)
ck("末 n 根窗口", abs(M._ma_of([1.0, 2.0, 3.0, 4.0], 2) - 3.5) < 1e-9)
ck("数据不足返回 None", M._ma_of([1.0, 2.0], 3) is None)
ck("空序列返回 None", M._ma_of([], 3) is None)

print()
print("=" * 80)
print("2) _get_index_closes_yday 口径 + AUD24 误报回归")
print("=" * 80)
_calls = {}


# AUD24(2026-10-19)：入口签名变为 (C, idx, n, need=None)，n=请求根数、need=最低接收根数。
# 旧桩无 need 参数会直接 TypeError，故同步升级。
def _fake_idx_fetch(C, idx, n, need=None):
    _calls["code"] = idx
    _calls["n"] = n
    _calls["need"] = need
    return list(_SEQ["v"]), "test", None


_SEQ = {"v": []}


class _BarC(object):
    """只提供「末根日期」的最小上下文，供 _idx_last_bar_date 使用。"""

    def __init__(self, bar):
        self._bar = bar

    def get_market_data_ex(self, fields, codes, period="1d", count=0,
                           dividend_type=None, fill_data=False):
        bar = self._bar

        class _DF(object):
            def __init__(self, b):
                self.index = [b] if b else []
                self.columns = ["close"]

            def __len__(self):
                return len(self.index)

            def __getitem__(self, k):
                return [100.0]

        return {codes[0]: _DF(bar)}


import datetime as _dt

_TODAY = _dt.datetime.now().strftime("%Y%m%d")
M._idx_fetch_with_fallback = _fake_idx_fetch


def _reset_idx(seq):
    _SEQ["v"] = seq
    M._MARKET_IDX_CACHE.update({"ts": 0.0, "closes": None, "diag": ""})
    M._IDX_LASTDATE.update({"day": "", "bar": ""})


# 2a 末根 = 当日（盘中常态）：剔除
_reset_idx([100.0 + i for i in range(80)])
closes, diag = M._get_index_closes_yday(_BarC(_TODAY), 60)
ck("请求根数 = n+10", _calls["n"] == 70, "n=%s" % _calls["n"])
ck("最低接收根数 = n+1", _calls["need"] == 61, "need=%s" % _calls["need"])
ck("请求代码 = 沪深300", _calls["code"] == "000300.SH", _calls["code"])
ck("末根=当日 -> 剔除（末值=倒数第二根原始值）",
   closes[-1] == 178.0, "last=%.1f" % closes[-1])
ck("按 n 截取返回 60 根", len(closes) == 60, "len=%d" % len(closes))

# 2b 末根 = 上一交易日：不剔（AUD24-P4）
_reset_idx([100.0 + i for i in range(80)])
closes_b, _ = M._get_index_closes_yday(_BarC("20261016"), 60)
ck("末根非当日 -> 不剔（末值=原始末根）",
   closes_b[-1] == 179.0, "last=%.1f" % closes_b[-1])

# 2c 日期取不到：保守不剔
_reset_idx([100.0 + i for i in range(80)])
closes_n, _ = M._get_index_closes_yday(None, 60)
ck("日期未知 -> 不剔末根", closes_n[-1] == 179.0, "last=%.1f" % closes_n[-1])

# 2d AUD24-P2 核心回归：本地只有 65 根必须放行（修复前误报「不足65根(实得64)」）
_reset_idx([100.0 + i for i in range(65)])
closes65, diag65 = M._get_index_closes_yday(_BarC(_TODAY), 60)
ck("本地 65 根 -> 放行（AUD24-P2 误报已修）",
   closes65 is not None and len(closes65) == 60, diag65 or "None")

# 2e 真不足：60 根且含当日 bar，剔后 59 < 60，应拦截
_reset_idx([100.0 + i for i in range(60)])
closes60, diag60 = M._get_index_closes_yday(_BarC(_TODAY), 60)
ck("真不足（60根含当日）-> 返回 None", closes60 is None)
ck("诊断信息含实得根数", "实得" in (diag60 or ""), diag60)

print()
print("=" * 80)
print("3) market_filter_ok 四分支")
print("=" * 80)
bull_closes = [100.0 + i * 0.5 for i in range(70)]          # 单调上行 -> MA20 > MA60
bear_closes = [200.0 - i * 0.5 for i in range(70)]          # 单调下行 -> MA20 < MA60
M._get_index_closes_yday = lambda C, n=65: (list(bull_closes), "ok")
ok, det = M.market_filter_ok(None)
ck("大盘多头 -> 放行", ok and "多头" in det, det)
M._get_index_closes_yday = lambda C, n=65: (list(bear_closes), "ok")
ok2, det2 = M.market_filter_ok(None)
ck("大盘空头 -> 拦截", (not ok2) and "空头" in det2, det2)
M._get_index_closes_yday = lambda C, n=65: (None, "不足65根(实得30)")
ok3, det3 = M.market_filter_ok(None)
ck("指数数据未就绪 -> 拦截(与回测语义一致)", (not ok3) and "未就绪" in det3, det3)
M.PARAMS["market_filter"] = False
ok4, det4 = M.market_filter_ok(None)
ck("开关关闭 -> 放行", ok4 and "关闭" in det4)
M.PARAMS["market_filter"] = True

print()
print("=" * 80)
print("4) data_gate_ready 拦截-弹窗-确认-放行")
print("=" * 80)
POPUPS = []
M._popup_data_gate = lambda items: POPUPS.append(list(items)) or 1
# AUD95 测试隔离：交互式模态弹窗会阻塞（ctypes MessageBoxW 无超时），
#   测试里必须一并打桩，否则整个脚本卡在等人点「确定」。策略侧不改。
M._popup_data_gate_interactive = lambda items: 1
M.DATA_GATE_ENABLED = True
M.DATA_GATE_POPUP = True
M.DATA_GATE_POPUP_GAP = 600.0
_ITEMS = {"v": []}
M._data_gate_missing_items = lambda C, codes: list(_ITEMS["v"])
M._DATA_GATE.update({"ok": None, "ts": 0.0, "last_popup": 0.0, "items": []})

_ITEMS["v"] = [("000300.SH（沪深300指数 日线）", "F2 大盘过滤", "不足65根(实得30)")]
r1 = M.data_gate_ready(None, ["002142.SZ"])
ck("数据缺失 -> 拦截", r1 is False)
ck("首次缺失即弹窗（1 次）", len(POPUPS) == 1)
ck("弹窗列出了缺失项", POPUPS and "000300.SH" in POPUPS[0][0][0])
r2 = M.data_gate_ready(None, ["002142.SZ"])
ck("节流窗口内重复检查 -> 仍拦截且不再弹窗", r2 is False and len(POPUPS) == 1)
# 用户补齐数据 -> 恢复放行
# 2026-10-19：策略已引入 DATA_GATE_FAIL_TTL(10s) 失败态负缓存，
# 上一步 r2 刚写入 ok=False/ts=now，此处须先失效负缓存才能触发重新探测。
M._DATA_GATE["ts"] = 0.0
_ITEMS["v"] = []
r3 = M.data_gate_ready(None, ["002142.SZ"])
ck("数据补齐 -> 放行", r3 is True)
r4 = M.data_gate_ready(None, ["002142.SZ"])
ck("缓存窗口内 -> 直接放行（不再取数）", r4 is True)
# 再次缺失（模拟数据故障复发）-> 重新拦截
M._DATA_GATE["ts"] = 0.0     # 失效缓存
M._DATA_GATE["ok"] = True
M._DATA_GATE["last_popup"] = 0.0   # 失效弹窗节流（测试内两步间隔<600s，生产中自然满足）
_ITEMS["v"] = [("000300.SH（沪深300指数 日线）", "F2 大盘过滤", "取数失败")]
r5 = M.data_gate_ready(None, ["002142.SZ"])
ck("故障复发 -> 重新拦截并再次弹窗", r5 is False and len(POPUPS) == 2, "popups=%d" % len(POPUPS))
# 弹窗后用户已补齐（复查通过）-> 本轮即放行
class _Once(object):
    """首次返回缺失项、之后返回空的清单（模拟弹窗确认期间用户补齐数据）。"""
    def __init__(self):
        self.n = 0
    def __call__(self, C, codes):
        self.n += 1
        return list(_ITEMS["v"]) if self.n == 1 else []


M._DATA_GATE.update({"ok": None, "ts": 0.0, "last_popup": 0.0, "items": []})
_once = _Once()
M._data_gate_missing_items = _once
r6 = M.data_gate_ready(None, ["002142.SZ"])
ck("弹窗确认后复查通过 -> 本根 bar 即放行", r6 is True and len(POPUPS) == 3)
M.DATA_GATE_ENABLED = False
ck("总开关关闭 -> 恒放行（可回滚）", M.data_gate_ready(None, ["002142.SZ"]) is True)
M.DATA_GATE_ENABLED = True

print()
print("=" * 80)
print("5) 四方源码静态检查（F2 钩子与闸门调用点）")
print("=" * 80)


def rd(fn, enc="utf-8"):
    return io.open(os.path.join(BASE, fn), "rb").read().decode(enc)


# 2026-10-19 恢复：UTF-8 母版/native多标的/miniQMT/聚宽版均已按用户要求删除，
# 现存唯一交付件为 GBK 版，故静态检查收敛为对 GBK 交付件单文件校验。
gbk_src = rd("gf_qmt_native_multi_gbk.py", "gbk")

ck("GBK交付件 含 F2 大盘过滤常量", ("MARKET_FILTER" in gbk_src and "True" in gbk_src)
   or "market_filter" in gbk_src.lower())
# 2026-10-19：首仓判定在 v1.2.x 已重构为 gate_ok / f2_exempt_on_strong，
# 原 "and bull and mkt_ok" 文本断言随之过时，改为语义等价的关键要素校验。
ck("GBK交付件 首仓 F2 判定含 mkt_ok", "mkt_ok" in gbk_src)
ck("GBK交付件 首仓 F2 豁免开关存在", "f2_exempt_on_strong" in gbk_src)
ck("GBK交付件 market_filter_ok 四分支函数存在", "def market_filter_ok" in gbk_src)
ck("GBK交付件 剔除当日口径 _get_index_closes_yday 存在",
   "def _get_index_closes_yday" in gbk_src)
ck("GBK交付件 bar 闸门调用 data_gate_ready", "data_gate_ready" in gbk_src)
ck("GBK交付件 init 数据就绪自检", "data_gate_ready" in gbk_src and "popup=True" in gbk_src)
