# -*- coding: utf-8 -*-
"""验证 AUD24-P1：补下载接口注入链路。

修复前：_DL_FUNCS 恒为 None -> fn(*args) 抛 TypeError -> 日志「'NoneType' object is not callable」
修复后：init/handlebar/_try_download_hist 三处幂等注入；取不到就跳过并给明确说明。
"""
import io
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(BASE, "gf_qmt_native_multi_gbk.py")
src = io.open(P, "rb").read().decode("gbk").replace("\r\n", "\n")
M = type(sys)("mod24")
M.__dict__["__file__"] = P
exec(compile(src, P, "exec"), M.__dict__)
tmp = tempfile.mkdtemp(prefix="_p1_")
for k, v in list(M.__dict__.items()):
    if k.isupper() and isinstance(v, str) and v.lower().endswith((".log", ".json")):
        M.__dict__[k] = os.path.join(tmp, os.path.basename(v))
M.__dict__["_MIRROR_DIR"] = ""
M.__dict__["_BASE_DIR"] = tmp

PASS, FAIL = [], []


def ck(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print("  %-58s %s %s" % (name, "PASS" if cond else "FAIL", extra))


LOGS = []
M.log = lambda m: LOGS.append(str(m))
M._log_hist_issue = lambda code, msg, force=False: LOGS.append("[issue] " + msg)

print("=" * 80)
print("1) 初始状态：_DL_FUNCS 为空壳")
print("=" * 80)
ck("_DL_FUNCS 两项初始为 None",
   M._DL_FUNCS.get("download_history_data2") is None
   and M._DL_FUNCS.get("download_history_data") is None)

print()
print("=" * 80)
print("2) 环境不提供接口时：跳过空壳、不抛异常、给出明确说明")
print("=" * 80)
del LOGS[:]
M._HIST_DL_LAST.clear()
M._HIST_DL_DAY.clear()
M._HIST_DL_CNT.clear()
r = M._try_download_hist("000300.SH", force=True)
ck("返回 False（没下载成功）", r is False, "r=%r" % r)
ck("未抛 TypeError（原实盘故障）", True)
ck("日志明确写「未接入」而非 'NoneType' object is not callable",
   any("未接入" in x for x in LOGS), " | ".join(LOGS[-1:])[:90])
ck("日志不再出现 NoneType",
   not any("NoneType" in x for x in LOGS))

print()
print("=" * 80)
print("3) 环境提供接口时：能取到并真正调用")
print("=" * 80)
CALLED = []


def _fake_dl(code, period, start, end):
    CALLED.append((code, period, start, end))


M.__dict__["download_history_data"] = _fake_dl
del LOGS[:]
M._HIST_DL_LAST.clear()
M._HIST_DL_DAY.clear()
M._HIST_DL_CNT.clear()
M._DL_FUNCS["download_history_data"] = None      # 复位，验证 _inject 真能从 globals 取到
r2 = M._try_download_hist("000300.SH", force=True)
ck("注入后返回 True", r2 is True, "r=%r" % r2)
ck("补下载函数被真正调用", len(CALLED) == 1, str(CALLED))
ck("调用参数为 000300.SH / 1d", CALLED and CALLED[0][0] == "000300.SH" and CALLED[0][1] == "1d")
ck("_DL_FUNCS 已写入 callable", callable(M._DL_FUNCS.get("download_history_data")))

print()
print("=" * 80)
print("4) ContextInfo 上的方法也能被取到（第二路兜底）")
print("=" * 80)
C2_CALLED = []


class FakeCtx(object):
    def download_history_data2(self, code, period, s, e, cb):
        C2_CALLED.append(code)


M._DL_FUNCS["download_history_data"] = None
M._DL_FUNCS["download_history_data2"] = None
M.__dict__.pop("download_history_data", None)
M._inject_dl_funcs(FakeCtx())
ck("从 ContextInfo 取到 download_history_data2",
   callable(M._DL_FUNCS.get("download_history_data2")))
del LOGS[:]
M._HIST_DL_LAST.clear()
M._HIST_DL_CNT.clear()
M._try_download_hist("000300.SH", force=True)
ck("优先走 download_history_data2", C2_CALLED == ["000300.SH"], str(C2_CALLED))

print()
print("=" * 80)
print("5) 幂等：重复注入不重复赋值、不产生副作用")
print("=" * 80)
before = id(M._DL_FUNCS.get("download_history_data2"))
M._inject_dl_funcs(FakeCtx())
M._inject_dl_funcs()
ck("重复注入保持同一引用", id(M._DL_FUNCS.get("download_history_data2")) == before)

print()
print("=" * 80)
print("结果：%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
print("=" * 80)
if FAIL:
    for f in FAIL:
        print("  FAIL: " + f)
    sys.exit(1)
