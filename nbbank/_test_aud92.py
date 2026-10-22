# -*- coding: utf-8 -*-
"""AUD92 专项回归：状态落盘误拦修复（v1.2.74）

覆盖 v1.2.74 的三项修复：
  P1：截断写防护读回校验改 _read_file_bytes 三通道——读不出来不再误判为坏 JSON
      （实盘 13:45:30 复现：沙箱/安全软件拦读 tmp -> 状态写不进磁盘）
  P2：守卫放弃替换时 save_state 如实报失败并进入持久化降级（不再谎报成功）
  P3：情绪日志显示生效缩放值（狂热单态下 1.00/1.00 并标注）

本脚本 exec GBK 交付件，进程内行为级验证，不联网、不下单。
"""
import io
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")

M = type(sys)("m92")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)

import tempfile
tmp = tempfile.mkdtemp(prefix="_a92_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp

R = []
CODE = "002142.SZ"


def chk(name, cond, detail=""):
    R.append((name, bool(cond), detail))


def eq(name, got, want):
    chk(name, got == want, "got=%r want=%r" % (got, want))


LOG = []
M.log = lambda m: LOG.append(m)
ALERTS = []
M._save_fail_alert = lambda tag, path, err: ALERTS.append((tag, str(err)))

# ---------------- 1) 源码级 ----------------
chk("A1 P1 读回校验改三通道 _read_file_bytes",
    "_t_blob, _t_err = _read_file_bytes(tmp)" in src)
chk("A2 P1 不再用普通 open 读 tmp",
    'with open(tmp, "rb") as _tf:' not in src)
chk("A3 P1 读不出来=无法校验不否决（blob None 分支）",
    "if _t_blob is not None:" in src)
chk("A4 P1 真坏 JSON 仍拦截告警",
    "tmp JSON 解析失败，已放弃替换(保留原文件)" in src)
chk("A5 P2 登记字典定义", "_LW_STATUS = {}" in src)
chk("A6 P2 成功登记 ok / 放弃登记 skip",
    '_LW_STATUS[path] = "ok"' in src and src.count('_LW_STATUS[path] = "skip"') == 2)
chk("A7 P2 save_state 见 skip 如实抛错",
    'if _LW_STATUS.get(STATE_FILE) == "skip":' in src
    and "状态写入被守卫放弃" in src)
chk("A8 P3 情绪日志按模式显示生效缩放",
    'if cfg.get("block_euphoric_only") and not SENTIMENT_ENABLED:' in src
    and "狂热单态·不缩放" in src)

# ---------------- 2) 行为级 P1：写盘守卫矩阵 ----------------
import json as _json


def write_case(name, path, payload, expect_replaced, expect_status, expect_alert=None):
    """payload: bytes 写入 tmp 的内容；None 表示 write_fn 什么都不写（空 tmp）。
    expect_replaced: 目标文件内容是否被替换为 payload。"""
    ALERTS[:] = []
    # 准备非空目标
    with io.open(path, "wb") as f:
        f.write(b'{"old": 1}')
    before = io.open(path, "rb").read()

    def _w(fp):
        if payload is not None:
            fp.write(payload)

    M._LW_STATUS.pop(path, None)
    M._lock_and_write(path, _w)
    after = io.open(path, "rb").read()
    chk(name + " | 替换判定", after == (payload if expect_replaced else before),
        "replaced=%s" % (after != before))
    eq(name + " | 状态登记", M._LW_STATUS.get(path), expect_status)
    if expect_alert is None:
        eq(name + " | 无告警", len(ALERTS), 0)
    else:
        eq(name + " | 告警标签", [a[0] for a in ALERTS], [expect_alert])


J = os.path.join(tmp, "unit_state.json")

# T1 合法 JSON -> 正常替换
write_case("T1 合法JSON替换", J, b'{"a": 1}', True, "ok")
# T2 半截 JSON -> 放弃替换 + 告警（原保护保留）
write_case("T2 半截JSON拦截", J, b'{"a": 1', False, "skip", "json_truncate")
# T3 非 JSON 后缀不做校验（日志类照旧替换）
L = os.path.join(tmp, "unit.log")
write_case("T3 非JSON直写", L, b"plain log line", True, "ok")
# T4 空 tmp（内容未变跳过）-> 放弃替换，登记 skip（save_state 侧由 skip 标志兜住）
write_case("T4 空tmp放弃", J, None, False, "skip")
# T5 模拟沙箱拦读：_read_file_bytes 返回 None -> 不做否决，照旧替换
_orig_rf = M._read_file_bytes
M._read_file_bytes = lambda p, *a, **kw: (None, "blocked(open|os.open|ctypes)")
try:
    write_case("T5 沙箱拦读不否决", J, b'{"b": 2}', True, "ok")
finally:
    M._read_file_bytes = _orig_rf
# T6 沙箱拦读 + 真·半截内容也拦不住（读不出来就是无法校验，按原行为替换）
M._read_file_bytes = lambda p, *a, **kw: (None, "blocked")
try:
    write_case("T6 拦读下半截也放行", J, b'{"c": 1', True, "ok")
finally:
    M._read_file_bytes = _orig_rf

# ---------------- 3) 行为级 P2：save_state 如实降级与恢复 ----------------
st = M.new_state()
st["position_shares"] = 0
M._STATE_WRITTEN.pop(CODE, None)
M._STATE_PERSIST_OK = True

# T7 守卫放弃 -> save_state 返回 False 且进入持久化降级
_real_lw = M._lock_and_write
M._lock_and_write = lambda path, fn, retry=2: M._LW_STATUS.__setitem__(path, "skip")
try:
    ok = M.save_state(CODE, st)
    eq("T7 守卫放弃时 save_state 返回 False", ok, False)
    eq("T7 持久化降级置位", M._STATE_PERSIST_OK, False)
    eq("T7 失败告警发出", [a[0] for a in ALERTS][-1:], ["save_state"])
finally:
    M._lock_and_write = _real_lw

# T8 恢复：真实写盘成功 -> 退出持久化降级
ALERTS[:] = []
ok = M.save_state(CODE, st)
eq("T8 恢复后 save_state 返回 True", ok, True)
eq("T8 持久化降级复位", M._STATE_PERSIST_OK, True)
eq("T8 无新增告警", len(ALERTS), 0)
chk("T8 状态文件真实落盘", os.path.exists(M.STATE_FILE)
    and os.path.getsize(M.STATE_FILE) > 0)

# ---------------- 输出 ----------------
npass = sum(1 for _, c, _ in R if c)
print("=" * 70)
for name, c, d in R:
    print("  [%s] %s %s" % ("PASS" if c else "FAIL", name, d))
print("=" * 70)
print("AUD92 专项：通过 %d / %d" % (npass, len(R)))
sys.exit(0 if npass == len(R) else 1)
