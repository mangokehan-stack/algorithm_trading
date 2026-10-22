# -*- coding: utf-8 -*-
"""V2.6.157 终态体检"""
import ast
import hashlib
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
out = []

raw = open(P, "rb").read()
t = raw.decode("gbk")
L = t.split("\r\n")

out.append("MD5      = %s" % hashlib.md5(raw).hexdigest())
out.append("字节     = %d" % len(raw))
out.append("段数     = %d (真实行数 %d)" % (len(L), len(L) - 1))
out.append("裸 LF    = %d" % sum(1 for i in range(len(raw))
                              if raw[i] == 10 and (i == 0 or raw[i - 1] != 13)))
out.append("裸 CR    = %d" % sum(1 for i in range(len(raw))
                              if raw[i] == 13 and (i + 1 >= len(raw) or raw[i + 1] != 10)))
out.append("BOM      = %s" % (raw[:3] == b"\xef\xbb\xbf"))
out.append("GBK往返  = %s" % (t.encode("gbk").decode("gbk") == t))

_tree = ast.parse(t)
_ver = None
for n in _tree.body:
    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
            and n.targets[0].id == "VERSION":
        _ver = n.value.value
out.append("VERSION  = %s" % _ver)
out.append("文件头L5 = %s" % L[4][:70])

# 模块级大写常量数(参数指纹口径)
_CONST = 0
for n in _tree.body:
    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
        nm = n.targets[0].id
        if nm.isupper() and not nm.startswith("_"):
            _CONST += 1
out.append("模块级大写常量(粗计) = %d" % _CONST)

_n_stop = sum(1 for n in ast.walk(_tree)
              if isinstance(n, ast.Attribute) and n.attr == ("stop" + "_order"))
out.append("硬止损AST节点 = %d" % _n_stop)

out.append("")
out.append("=== 改动点 1: 粗估判据 ===")
for i, l in enumerate(L):
    if "_fe_est = _round2(_fs * 0.0015)" in l:
        for j in range(i - 8, i + 5):
            out.append("L%d|%s" % (j + 1, L[j]))
        break

out.append("")
out.append("=== 改动点 2: 跳过日志 ===")
for i, l in enumerate(L):
    if "存量持仓费用校准跳过" in l:
        for j in range(i - 1, i + 3):
            out.append("L%d|%s" % (j + 1, L[j]))
        break

out.append("")
out.append("=== 校准段整体(确认 continue 真的跳过重算) ===")
_s = _e = -1
for i, l in enumerate(L):
    if l == "        _fee_fixed = []":
        _s = i
    if _s >= 0 and l.startswith("        # 方向A2: 在途买单补录"):
        _e = i
        break
for j in range(_s, min(_e, _s + 55)):
    out.append("L%d|%s" % (j + 1, L[j]))

io.open(r"E:\桌面\666666\dxgp\_verify_157_out.txt", "w", encoding="utf-8").write("\n".join(out))
print("written %d lines" % len(out))
