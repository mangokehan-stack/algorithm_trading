# -*- coding: utf-8 -*-
# 复现：状态文件/M3文件/风险日志 文件「不存在」时, AUD96 的读失败保护是否误伤正常首次写盘
import os, sys, tempfile, json
d = tempfile.mkdtemp()
P = r"E:/桌面/666666/nbbank/gf_qmt_native_multi_gbk.py"
src = open(P, "rb").read().decode("gb18030")
ns = {"__name__": "M"}
exec(compile(src, P, "exec"), ns)
ns["BASE_DIR"] = d
for k in ("STATE_FILE", "M3_STATE_FILE", "RISK_EVENT_LOG"):
    if k in ns:
        ns[k] = os.path.join(d, os.path.basename(ns[k]))
print("STATE_FILE =", ns.get("STATE_FILE"))
print("M3_STATE_FILE =", ns.get("M3_STATE_FILE"))
print("RISK_EVENT_LOG =", ns.get("RISK_EVENT_LOG"))
print("exists before:", [os.path.exists(ns[k]) for k in ("STATE_FILE","M3_STATE_FILE","RISK_EVENT_LOG")])

st = ns["new_state"]() if "new_state" in ns else {}
# 1) save_state 到一个不存在的状态文件
try:
    ok = ns["save_state"]("002142.SZ", st)
    print("save_state(文件不存在) ->", ok, "| 文件已生成:", os.path.exists(ns["STATE_FILE"]))
except Exception as e:
    print("save_state raised:", e)
# 2) save_m3
try:
    ok = ns["save_m3"]("002142.SZ", {"date":"2026-10-22","triggered":[],"used":0.0,"m2_used":0.0})
    print("save_m3(文件不存在) ->", ok, "| 文件已生成:", os.path.exists(ns["M3_STATE_FILE"]))
except Exception as e:
    print("save_m3 raised:", e)
# 3) _notify_risk
try:
    ns["_notify_risk"]("probe", "测试")
    print("_notify_risk(文件不存在) -> 调用完成, 文件已生成:", os.path.exists(ns["RISK_EVENT_LOG"]))
except Exception as e:
    print("_notify_risk raised:", type(e).__name__, e)
print("_STATE_PERSIST_OK =", ns.get("_STATE_PERSIST_OK"), "_M3_PERSIST_OK =", ns.get("_M3_PERSIST_OK"))
