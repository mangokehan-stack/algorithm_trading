# -*- coding: utf-8 -*-
"""V2.6.154 最终验证（修正口径）
   ★ 负向断言必须排除模块 docstring —— 文件头是历史版本记录,
     天然含旧口径原文(V2.6.150 行), 不排除就会假 FAIL(同一个坑第 5 次)。
   只保证: 代码/普通注释区里不再有任何"改回零"的指令。
"""
import ast
import hashlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
CRLF = "\r\n"
raw = open(P, "rb").read()
txt = raw.decode("gbk")
tree = ast.parse(txt)
doc = ast.get_docstring(tree, clean=False) or ""
# 模块 docstring 的行区间（文件头那块）
m_doc = tree.body[0]
d_lo, d_hi = m_doc.lineno - 1, m_doc.end_lineno          # 0-based / exclusive
L = txt.split("\r\n")
code_lines = L[:d_lo] + L[d_hi:]
code_zone = "\r\n".join(code_lines)
print("模块 docstring: L%d..L%d (%d 行)" % (d_lo + 1, d_hi, d_hi - d_lo))
print("代码/普通注释区: %d 行\n" % len(code_lines))

res = []
def ck(n, cond, d=""):
    res.append((n, bool(cond), d))

# ---- 编码与结构 ----
ck("MD5", True, hashlib.md5(raw).hexdigest())
ck("字节数", True, str(len(raw)))
ck("GBK 往返一致", txt.encode("gbk") == raw)
ck("无 BOM", not raw.startswith(b"\xef\xbb\xbf"))
ck("裸 LF == 0", txt.count("\n") == txt.count(CRLF), "%d/%d" % (txt.count("\n"), txt.count(CRLF)))
ck("段数 = 14629", len(L) == 14629, str(len(L)))

# ---- 核心：代码区已无危险指令 ----
ck("代码区无「改回 0.0」", "改回 0.0" not in code_zone)
ck("代码区无「改回0.0」", "改回0.0" not in code_zone)
ck("代码区无「无从自证」", "无从自证" not in code_zone)
ck("代码区有「按正常标准收取」", "按正常标准收取" in code_zone)
ck("代码区有「买入收一次、卖出收一次」", "买入收一次、卖出收一次" in code_zone)
# 历史记录里保留是允许的，但要在文档里明确它已失效
ck("文件头已声明该条失效(定论行在先)",
   txt.index("过户费口径定论") < txt.index("改回 0.0") if "改回 0.0" in txt else True,
   "定论行 L%d / 旧记录 L%d" % (
       txt[:txt.index("过户费口径定论")].count(CRLF) + 1,
       (txt[:txt.index("改回 0.0")].count(CRLF) + 1) if "改回 0.0" in txt else -1))

# ---- 两项改动都在位 ----
ck("退潮行新文案在位", txt.count("退潮层通过(仍须过情绪等其它闸门)") >= 2)
ck("V2.6.153 独立行仍保留", txt.count("# 版本号: V2.6.153") == 1)
ck("VERSION = V2.6.154", txt.count("VERSION = 'V2.6.154'") == 1)
ck("文件头首行 = V2.6.154", re.search(r"# 版本号: (V[\d.]+)", txt).group(1) == "V2.6.154")

# ---- 数值一个没动 ----
ck("佣金仍 0.0000841", txt.count("FEE_COMMISSION_RATE = 0.0000841") == 1)
ck("最低佣金仍 5.0", txt.count("FEE_COMMISSION_MIN = 5.0") == 1)
ck("印花税仍 0.0005", txt.count("FEE_STAMP_RATE = 0.0005") == 1)
ck("过户费仍 0.00001", txt.count("FEE_TRANSFER_RATE = 0.00001") == 1)
ck("desc 未动", txt.count("过户费沪市双边万0.1(保守计入)") == 1)

# ---- 语法与铁律 ----
try:
    compile(txt, P, "exec")
    ck("compile", True)
except SyntaxError as e:
    ck("compile", False, str(e))
nm = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "stop_order"]
at = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "stop_order"]
ck("铁律: 硬止损 AST = 0", not nm and not at, "Name=%d Attr=%d" % (len(nm), len(at)))

print("=" * 70)
bad = 0
for n, ok, d in res:
    print("%-4s %-36s %s" % ("PASS" if ok else "FAIL", n, d))
    bad += 0 if ok else 1
print("=" * 70)
print("结果: %d/%d PASS" % (len(res) - bad, len(res)))
sys.exit(1 if bad else 0)
