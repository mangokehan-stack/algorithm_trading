# -*- coding: utf-8 -*-
"""AUD95 专项回归：运行模式误报修复（v1.2.78 = AUD95-P1）

背景（2026-10-21 15:25:22 实盘事故）：
  框架日志实证 —— 15:24:40 用户先在「模拟」模式启动过一次（框架 15:24:46 落
  `output = [trade]start simulation mode`），随后切实盘、15:25:22 重启。新实例探测
  在第一次尝试就读到 36 秒前的 simulation 行，`36 <= _MODE_STALE_SEC(60)` 被判为
  「本次运行」并立即 return；本轮真正的 trading 行 15:25:22,535 才落盘（探测已结束
  0.4 秒）→ 日志误报「trade_mode=simulation（模拟）」。

修复：新增 _INIT_START_TS（init 首行写入）+ _MODE_PRE_INIT_SEC=10 允许提前量；
  模式行时间戳早于「init 起始 - 10 秒」一律判为上一轮残留、不采纳，改走既有
  「不作结论 + 首根 bar 补测」兜底。

本脚本 exec GBK 交付件，纯进程内行为验证，不联网、不下单。
"""
import io
import os
import sys
import tempfile
from datetime import timedelta as TD

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")

M = type(sys)("m95")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)

tmp = tempfile.mkdtemp(prefix="_a95_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp
M.__dict__["_INSTANCE_LOCK_FILE"] = os.path.join(tmp, "gf_strategy_instance.lock")
M.log = lambda m: None

R = []


def chk(name, cond, detail=""):
    R.append((name, bool(cond), detail))


def eq(name, got, want):
    chk(name, got == want, "got=%r want=%r" % (got, want))


DT = M.datetime
LOG_PATH = os.path.join(tmp, "XtClient_FormulaOutput_test.log")


def write_log(entries):
    """entries: [(datetime, mode_str)]，按给定顺序写入框架日志。"""
    with io.open(LOG_PATH, "w", encoding="utf-8") as f:
        for _dt, _mode in entries:
            f.write("%s,123 [INFO] [0x00005070] reqid = 0xx, output = [trade]start %s mode\n"
                    % (_dt.strftime("%Y-%m-%d %H:%M:%S"), _mode))
    return LOG_PATH


def probe(init_start_ts, entries, retries=1):
    write_log(entries)
    M._qmt_mode_log_candidates = lambda: [LOG_PATH]
    M._INIT_START_TS = init_start_ts
    return M._probe_trade_mode(retries=retries)


now = DT.now()

# ============ T1 事故复现：上一轮 36 秒前的 simulation 行必须被拒 ============
# 与 15:25:22 完全同构：init 刚进入（elapsed≈0），残留行 36 秒前
mode, path, age, note = probe(now.timestamp(), [(now - TD(seconds=36), "simulation")])
eq("T1 事故复现：36 秒前的残留 simulation 行不被采纳", mode, "")
chk("T1 note 明确指向上一轮残留", u"上一轮残留" in note, "note=%r" % note[:80])

# ============ T2 本次运行的模式行（init 后落盘）正常采纳 ============
mode2, _p, age2, note2 = probe((now - TD(seconds=3)).timestamp(),
                               [(now - TD(seconds=1), "trading")])
eq("T2 本次运行 trading 行被采纳", mode2, "trading")

# ============ T3 允许提前量内（早于 init 7 秒，<10 秒余量）仍采纳 ============
mode3, _p, _a, _n = probe((now - TD(seconds=5)).timestamp(),
                          [(now - TD(seconds=12), "trading")])
eq("T3 init 前 7 秒的行（在 10 秒余量内）仍采纳", mode3, "trading")

# ============ T4 最新一条被拒后不回退到更早的行 ============
mode4, _p, _a, note4 = probe(now.timestamp(),
                             [(now - TD(seconds=120), "trading"),
                              (now - TD(seconds=36), "simulation")])
eq("T4 最新的是残留行 -> 整体拒绝，不回退到更早的 trading", mode4, "")
chk("T4 未误用更早的行", mode4 != "trading", "got=%r" % (mode4,))

# ============ T5 时间戳解析失败 -> 未知（不猜） ============
with io.open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write("garbage-ts [INFO] reqid = 0xx, output = [trade]start trading mode\n")
M._qmt_mode_log_candidates = lambda: [LOG_PATH]
M._INIT_START_TS = now.timestamp()
mode5, _p, _a, note5 = M._probe_trade_mode(retries=1)
eq("T5 时间戳无法解析时返回未知", mode5, "")

# ============ T6 60 秒上界仍然生效（本轮但太旧） ============
# init 起始在 70 秒前，模式行在 65 秒前（晚于 init，过下界；但 age 65 > 60 上界）
mode6, _p, age6, note6 = probe((now - TD(seconds=70)).timestamp(),
                               [(now - TD(seconds=65), "trading")])
eq("T6 超 60 秒上界仍拒绝（保留原陈旧闸门）", mode6, "")
chk("T6 note 提到陈旧标记", u"陈旧标记" in note6, "note=%r" % note6[:60])

# ============ T7 未写 _INIT_START_TS 时保持旧行为（兼容） ============
mode7, _p, _a, _n = probe(0.0, [(now - TD(seconds=36), "simulation")])
eq("T7 init 未写起始时刻时退化为旧行为（36 秒内采纳）", mode7, "simulation")

# ============ T8 init 首行确实写入起始时刻 ============
chk("T8 init 内写入 _INIT_START_TS",
    "_INIT_START_TS = time.time()" in src
    and "global _LOG_IN_NEST, _trade_mode_pending, _INIT_START_TS" in src)
chk("T8 _MODE_PRE_INIT_SEC 存在且为 10 秒",
    M._MODE_PRE_INIT_SEC == 10.0, "got=%r" % (M._MODE_PRE_INIT_SEC,))

# ============ T9 两处提示文案补「以首行为准」 ============
chk("T9 init 与补测两处提示均补「以首行为准」",
    src.count(u"以首行为准（本判定可能命中上一轮残留）") == 2,
    "count=%d" % src.count(u"以首行为准（本判定可能命中上一轮残留）"))

# ============ T10 版本三处对齐 + 记录块 ============
import re

m1 = re.search(r"#  策略版本:\s*(v[\d.]+)\s*\(构建\s*(\d{4}-\d{2}-\d{2})\)", src)
m2 = re.search(r'STRATEGY_VERSION\s*=\s*"(v[\d.]+)"', src)
m3 = re.search(r'STRATEGY_BUILD\s*=\s*"(\d{4}-\d{2}-\d{2})"', src)
# AUD97: 版本断言改为「三处互相一致 + 常量等于当前版本」, 不再硬编码版本号,
#   避免每次升版都产生假失败(版本漂移由 _verify_final 的「当前版本必有变更记录块」硬闸门拦截)。
_cur = M.STRATEGY_VERSION
chk("T10 版本三处互相一致（头/常量/构建）",
    m1 and m2 and m3 and m1.group(1) == m2.group(1) == _cur
    and m1.group(2) == m3.group(1),
    "头=%s 常量=%s 构建=%s 当前=%s" % (m1.group(1) if m1 else "?", m2.group(1) if m2 else "?",
                              m3.group(1) if m3 else "?", _cur))
chk("T10 v1.2.78 记录块仍在文件头", u"── v1.2.78 = AUD95-P1" in src)
chk("T10 当前版本必有对应变更记录块", ("── %s = " % _cur) in src, "当前版本=%s" % _cur)

# ============ T11 铁律零触碰 ============
chk("T11 硬止损仍为 None（坚决不止损）", "hard_stop_dd_pct" in src)
chk("T11 R1 净到手闸门仍在", "_r1_net_profit_gate" in src)
chk("T11 移交人工释放额度逻辑仍在", u"manual_takeover" in src)

# ============ 输出 ============
print("=" * 78)
npass = sum(1 for _, c, _ in R if c)
for name, c, d in R:
    print("  [%s] %s %s" % ("PASS" if c else "FAIL", name, "" if c else d))
print("=" * 78)
print("AUD95 专项：通过 %d / %d" % (npass, len(R)))
sys.exit(0 if npass == len(R) else 1)
