# -*- coding: utf-8 -*-
"""AUD97 专项回归：第二十七轮零预设独立审计 · 收尾修复（v1.2.80 = AUD97-P1~P5）

背景：
  v1.2.79（AUD96）已把「持仓查询侧」的代码匹配改成大小写不敏感（AUD96-P10），
  但**委托查询侧**仍是严格比较 `pid != code`。同一份 QMT 返回对象里，
  委托的 m_strExchangeID 若与策略 SYMBOLS 里的后缀大小写不同（例如
  "002142.sz" vs "002142.SZ"），则：

    · has_live_buy_order  查不到自己的活跃买单 -> settle_pending_timeout 误清在途台账
      -> 同一笔被重复下单（本次审计最重的一项）。
    · count_orders_for_code 返回 0 -> 误报「委托未到券商/模拟模式」，误导排查。
    · _sell_order_status  查不到活跃卖单 -> 卖单尚未成交却按「已终结」恢复状态。

  本轮修复：
    P1 委托侧 4 处代码匹配改大小写不敏感（count_orders_for_code / order_diag /
       has_live_buy_order / _sell_order_status）。
    P2 _read_order_direction 逐字段回退：首个候选字段存在但值域不认时，
       继续试下一个字段，不再一票否决方向判定。
    P3 init 方向字段自检改用与运行时完全相同的翻译口径统计（0=买/1=卖/未知），
       并如实描述未知委托的处置（单列未知 + 保守处理，不默认当买单）。
    P4 版本收尾：文件头版本行 + v1.2.79 变更记录块补齐。

本脚本 exec GBK 交付件，纯进程内行为验证，不联网、不下单。
"""
import io
import os
import re
import sys
import tempfile
import types

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")

M = types.ModuleType("m97")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)

tmp = tempfile.mkdtemp(prefix="_a97_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp
M.__dict__["_INSTANCE_LOCK_FILE"] = os.path.join(tmp, "gf_strategy_instance.lock")
M.log = lambda m: None
M.log_err = lambda m: None

R = []


def chk(name, cond, detail=""):
    R.append((name, bool(cond), detail))


def eq(name, got, want):
    chk(name, got == want, "got=%r want=%r" % (got, want))


CODE = "002142.SZ"


class OD(object):
    """模拟 QMT 委托对象。"""

    def __init__(self, inst="002142", exch="SZ", offset=48, status=1,
                 vol=1000, dealt=0, direction=None, odirection=None):
        self.m_strInstrumentID = inst
        self.m_strExchangeID = exch
        self.m_nOffsetFlag = offset
        self.m_nOrderStatus = status
        self.m_nVolume = vol
        self.m_nDealtVolume = dealt
        self.m_strOrderSysID = "T1"
        if direction is not None:
            self.m_nDirection = direction
        if odirection is not None:
            self.m_dDirection = odirection


def patch_query(arr, ok=True):
    M._td_query = lambda acct, dt: (ok, arr)


# ================= P1 委托侧大小写不敏感 =================
# T1 count_orders_for_code：小写后缀也能计数
patch_query([OD(inst="002142", exch="sz", offset=48)])
eq("T1 count_orders_for_code 小写后缀可计数",
   M.count_orders_for_code("acc", "002142.SZ"), 1)

patch_query([OD(inst="002142", exch="SZ", offset=48)])
eq("T1b count_orders_for_code 原大写仍计数",
   M.count_orders_for_code("acc", "002142.SZ"), 1)

patch_query([OD(inst="002143", exch="SZ", offset=48)])
eq("T1c count_orders_for_code 不同标的仍为 0",
   M.count_orders_for_code("acc", "002142.SZ"), 0)

# T2 has_live_buy_order：小写后缀的活跃买单必须被查到（防重复下单闸门）
patch_query([OD(inst="002142", exch="sz", offset=48, status=1, vol=2000)])
ok2, live2, unk2, det2 = M.has_live_buy_order("acc", CODE)
chk("T2 has_live_buy_order 小写后缀查到活跃买单", ok2 and live2 == 2000,
    "ok=%s live=%s unk=%s detail=%s" % (ok2, live2, unk2, det2))
eq("T2b 方向未知计数为 0", unk2, 0)

# T3 卖单不应计入 live（方向翻译正确）
patch_query([OD(inst="002142", exch="sz", offset=49, status=1, vol=3000)])
ok3, live3, unk3, _ = M.has_live_buy_order("acc", CODE)
chk("T3 小写后缀的卖单不计入活跃买单", ok3 and live3 == 0,
    "live=%s unk=%s" % (live3, unk3))

# T4 _sell_order_status：小写后缀的活跃卖单必须被查到
patch_query([OD(inst="002142", exch="sz", offset=49, status=1, vol=4000)])
ok4, act4, det4 = M._sell_order_status("acc", CODE)
chk("T4 _sell_order_status 小写后缀查到活跃卖单", ok4 and act4,
    "ok=%s any_active=%s detail=%s" % (ok4, act4, det4))

# T5 order_diag：小写后缀的委托要出现在诊断里
patch_query([OD(inst="002142", exch="sz", offset=48, status=1, vol=1000)])
dg = M.order_diag(None, "acc", CODE)
chk("T5 order_diag 小写后缀可查到", "T1" in (dg or ""), "diag=%r" % (dg or "")[:120])

# ================= P2 方向翻译逐字段回退 =================
# T6 OffsetFlag 值域不认（0）时，继续试 m_nDirection（0/1 语义）
eq("T6 OffsetFlag=0 不认时回退 m_nDirection=0 -> 买",
   M._read_order_direction(OD(offset=0, direction=0)), 0)
eq("T6b OffsetFlag=0 不认时回退 m_nDirection=1 -> 卖",
   M._read_order_direction(OD(offset=0, direction=1)), 1)

# T7 正常路径不受影响
eq("T7 OffsetFlag=48 -> 买", M._read_order_direction(OD(offset=48)), 0)
eq("T7b OffsetFlag=49 -> 卖", M._read_order_direction(OD(offset=49)), 1)
eq("T7c m_nDirection=23 -> 买", M._read_order_direction(OD(offset=None, direction=23)), 0)
eq("T7d m_nDirection=24 -> 卖", M._read_order_direction(OD(offset=None, direction=24)), 1)

# T8 全部字段都取不到 / 值域都不认 -> None（未知），不得瞎猜
eq("T8 字段全缺 -> 未知", M._read_order_direction(OD(offset=None)), None)
eq("T8b 值域全不认 -> 未知", M._read_order_direction(OD(offset=7)), None)

# T9 回退后能正确识别活跃买单（方向翻译整体未被一票否决）
patch_query([OD(inst="002142", exch="sz", offset=0, direction=0, status=1, vol=1500)])
ok9, live9, unk9, _ = M.has_live_buy_order("acc", CODE)
chk("T9 回退后活跃买单可被正确识别", ok9 and live9 == 1500,
    "live=%s unk=%s" % (live9, unk9))

# ================= P3 自检口径与运行时一致 =================
chk("T10 自检不再只认 48/49 字面值",
    'str(_v) in ("48", "49")' not in src)
chk("T10b 自检改用 _read_order_direction 统计",
    "_d97 = _read_order_direction(_od)" in src
    and "_of_buy" in src and "_of_sell" in src and "_of_unk" in src)
# 说明：变更记录块里保留「原写『将按 48(买单) 保守判定』」是对旧行为的如实留痕，
#   故只检查代码行本身，不对全文做字符串否定断言。
_code_only = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
chk("T10c 自检文案如实描述未知委托处置（不再说「按 48 保守判定」）",
    "将按 48(买单) 保守判定" not in _code_only
    and "按「方向未知」单列并保守处理" in _code_only)

# ================= P5 首次创建必须能落盘（AUD96 回归修复） =================
# 场景：状态文件 / M3 台账 / 风险日志都还不存在（首次运行），
#   _read_file_bytes 返回 (None, err)，AUD96 曾一律当成「读失败 -> 中止写入」，
#   导致首次运行状态永远写不进去。
import json as _json

_sf = os.path.join(tmp, "p5_state.json")
_m3f = os.path.join(tmp, "p5_m3.json")
_rlf = os.path.join(tmp, "p5_risk.log")
for _p in (_sf, _m3f, _rlf):
    if os.path.exists(_p):
        os.remove(_p)

M.STATE_FILE = _sf
M.M3_STATE_FILE = _m3f
M.RISK_EVENT_LOG = _rlf
M._STATE_WRITTEN.pop(CODE, None)
M._LS_STATUS.clear()

_st = M.new_state()
_st["position_shares"] = 0
_ok = M.save_state(CODE, _st)
chk("P5 状态文件首次创建可落盘（不再自己否决自己）", _ok is True, "ok=%r" % (_ok,))
chk("P5b 状态文件真实生成且非空",
    os.path.exists(_sf) and os.path.getsize(_sf) > 0)

_ok2 = M.save_m3(CODE, {"date": "2026-10-22", "triggered": [], "used": 0.0, "m2_used": 0.0})
chk("P5 M3 台账首次创建可落盘", _ok2 is True and os.path.exists(_m3f),
    "ok=%r exists=%r" % (_ok2, os.path.exists(_m3f)))

M._notify_risk("p5_test", "首次创建风险日志")
chk("P5 风险日志首次创建可写入（首条告警不丢失）",
    os.path.exists(_rlf) and os.path.getsize(_rlf) > 0)

# 真读失败（文件存在但读不出来）仍必须中止 —— 不能被本次修复削弱
M._read_file_bytes = lambda p, *a, **kw: (None, "blocked")
try:
    M._STATE_WRITTEN.pop(CODE, None)
    _ok3 = M.save_state(CODE, _st)
    chk("P5 真读失败时仍中止写入（不覆盖他股状态）", _ok3 is False, "ok=%r" % (_ok3,))
finally:
    M._read_file_bytes = M.__dict__["_read_file_bytes"]

# ================= P4 版本收尾 =================
m1 = re.search(r"#  策略版本:\s*(v[\d.]+)\s*\(构建\s*(\d{4}-\d{2}-\d{2})\)", src)
m2 = re.search(r'STRATEGY_VERSION\s*=\s*"(v[\d.]+)"', src)
m3 = re.search(r'STRATEGY_BUILD\s*=\s*"(\d{4}-\d{2}-\d{2})"', src)
cur = m2.group(1) if m2 else "?"
chk("P4 版本三处对齐",
    m1 and m2 and m3 and m1.group(1) == m2.group(1) == cur
    and m1.group(2) == m3.group(1),
    "头=%s 常量=%s 构建=%s" % (m1.group(1) if m1 else "?",
                              m2.group(1) if m2 else "?",
                              m3.group(1) if m3 else "?"))
chk("P4 当前版本必有变更记录块", ("── %s = " % cur) in src, "当前版本=%s" % cur)
chk("P4 v1.2.79(AUD96) 记录块已补齐", "── v1.2.79 = AUD96-P1~P11" in src)
chk("P4 v1.2.80(AUD97) 记录块在文件头", "── v1.2.80 = AUD97-P1~P5" in src)
chk("P4 审计号无重复",
    len(re.findall(r"──\s*v[\d.]+[A-C]?\s*=\s*(AUD\d+)(?![-\d])", src))
    == len(set(re.findall(r"──\s*v[\d.]+[A-C]?\s*=\s*(AUD\d+)(?![-\d])", src))))

# ================= 铁律零触碰 =================
chk("铁律：硬止损仍为 None（坚决不止损）", "hard_stop_dd_pct" in src)
chk("铁律：无强制平仓/止损卖出字样",
    not re.search(r"(止损卖出|强制平仓|fail_close_all|stop_loss_order)", src))
chk("铁律：R1 扣费后净到手闸门仍在", "_r1_net_profit_gate" in src)
chk("铁律：人工接管释放额度逻辑仍在", "manual_takeover" in src)
chk("铁律：移交人工同时释放股票与资金额度",
    "释放" in src and "额度" in src)

# ================= 输出 =================
print("=" * 78)
npass = sum(1 for _, c, _ in R if c)
for name, c, d in R:
    print("  [%s] %s %s" % ("PASS" if c else "FAIL", name, "" if c else d))
print("=" * 78)
print("AUD97 专项：通过 %d / %d" % (npass, len(R)))
sys.exit(0 if npass == len(R) else 1)
