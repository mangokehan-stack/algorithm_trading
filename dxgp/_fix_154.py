# -*- coding: utf-8 -*-
"""修正 V2.6.154 文件头说明里的一处自我污染：
   说明文字引用了被删指令的原文，导致 "改回 0.0" 断言假失败（同一个坑第 5 次）。
   改成中文转述，不含该字面。版本号仍是 V2.6.154（同一次落盘过程内的修正）。
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
print("[前] MD5=%s 字节=%d" % (hashlib.md5(raw).hexdigest(), len(raw)))

OLD = '原注释里 "拿沪市交割单验证, 若为 0 就改回 0.0" 的待办指令已删除'
NEW = '原注释里那句"拿沪市交割单验证, 若该栏为 0 就把它改回零"的待办指令已删除'

c = txt.count(OLD)
assert c == 1, "锚点 count=%d" % c
txt = txt.replace(OLD, NEW)
print("[改] 文件头说明措辞已避开被删指令的字面")

out = txt.encode("gbk")
open(P, "wb").write(out)

# ---- 全量复核 ----
raw2 = open(P, "rb").read()
txt2 = raw2.decode("gbk")
L2 = txt2.split(CRLF)

res = []
def ck(n, cond, d=""):
    res.append((n, bool(cond), d))

ck("GBK 往返一致", txt2.encode("gbk") == raw2)
ck("无 BOM", not raw2.startswith(b"\xef\xbb\xbf"))
ck("裸 LF == 0", txt2.count("\n") == txt2.count(CRLF), "%d/%d" % (txt2.count("\n"), txt2.count(CRLF)))
ck("段数 14629", len(L2) == 14629, str(len(L2)))
ck("危险指令(带空格)已彻底消失", "改回 0.0" not in txt2)
ck("危险指令(无空格)已彻底消失", "改回0.0" not in txt2)
ck("无残留「无从自证」", "无从自证" not in txt2)
ck("新口径在位", "按正常标准收取" in txt2)
ck("买卖各一次已写明", "买入收一次、卖出收一次" in txt2)
ck("V2.6.153 退潮文案仍在", txt2.count("退潮层通过(仍须过情绪等其它闸门)") >= 2)
ck("VERSION = V2.6.154", txt2.count("VERSION = 'V2.6.154'") == 1)
ck("文件头首行 = V2.6.154", re.search(r"# 版本号: (V[\d.]+)", txt2).group(1) == "V2.6.154")
ck("费率数值未变", txt2.count("FEE_COMMISSION_RATE = 0.0000841") == 1)
ck("过户费仍 0.00001", txt2.count("FEE_TRANSFER_RATE = 0.00001") == 1)
ck("desc 未动(保护参数指纹)", txt2.count("过户费沪市双边万0.1(保守计入)") == 1)

try:
    compile(txt2, P, "exec")
    ck("compile", True)
except SyntaxError as e:
    ck("compile", False, str(e))

tree = ast.parse(txt2)
nm = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "stop_order"]
at = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "stop_order"]
ck("铁律: 硬止损 AST = 0", not nm and not at, "Name=%d Attr=%d" % (len(nm), len(at)))

print("\n" + "=" * 64)
bad = 0
for n, ok, d in res:
    print("%-4s %-32s %s" % ("PASS" if ok else "FAIL", n, d))
    bad += 0 if ok else 1
print("=" * 64)
print("[后] MD5=%s 字节=%d" % (hashlib.md5(raw2).hexdigest(), len(raw2)))
print("结果: %d/%d PASS" % (len(res) - bad, len(res)))
sys.exit(1 if bad else 0)
