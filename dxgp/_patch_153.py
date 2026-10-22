# -*- coding: utf-8 -*-
"""V2.6.152 -> V2.6.153
唯一改动：退潮判断成功那一行「正常开仓」-> 「退潮层通过(仍须过情绪等其它闸门)」
零逻辑、零参数；文件头插入新版本记录 + VERSION 常量同步。
"""
import ast
import hashlib
import os
import re
import shutil
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
CRLF = "\r\n"

# ---------- 0. 备份 ----------
stamp = datetime.now().strftime("%Y%m%d-%H%M")
bak = P + ".bak-" + stamp
shutil.copy2(P, bak)
print("[备份] %s  (%d 字节)" % (bak, os.path.getsize(bak)))

raw = open(P, "rb").read()
old_md5 = hashlib.md5(raw).hexdigest()
old_size = len(raw)
txt = raw.decode("gbk")

print("[原态] MD5=%s  字节=%d" % (old_md5, old_size))

# 编码前提
assert not raw.startswith(b"\xef\xbb\xbf"), "带 BOM"
assert txt.count("\n") == txt.count(CRLF), "存在裸 LF: %d vs %d" % (txt.count("\n"), txt.count(CRLF))

lines = txt.split(CRLF)
print("[原态] 段数=%d (真实行数 %d)" % (len(lines), len(lines) - 1))
assert len(lines) == 14627, len(lines)
assert lines[3].startswith("====="), repr(lines[3][:20])
assert lines[4].startswith("# 版本号: V2.6.152"), repr(lines[4][:40])

# ---------- 1. 文案替换 ----------
OLD = "'[退潮判断] 数据有效: %s 近%d日跌幅%.2f%%, 未达退潮阈值%.0f%%, 正常开仓'"
NEW = "'[退潮判断] 数据有效: %s 近%d日跌幅%.2f%%, 未达退潮阈值%.0f%%, 退潮层通过(仍须过情绪等其它闸门)'"

n_old = txt.count(OLD)
assert n_old == 1, "旧文案锚点计数=%d (应为1)" % n_old
# 目标必须在 L4171
pos = txt.index(OLD)
lineno = txt[:pos].count(CRLF) + 1
assert lineno == 4171, "命中行=%d (应为4171)" % lineno
print("[锚点] %s 位于 L%d  count=1" % ("正常开仓行", lineno))

txt = txt.replace(OLD, NEW)

# ---------- 2. VERSION 常量 ----------
assert txt.count("VERSION = 'V2.6.152'") == 1
txt = txt.replace("VERSION = 'V2.6.152'", "VERSION = 'V2.6.153'")
print("[升版] VERSION -> V2.6.153")

# ---------- 3. 文件头插入版本记录 ----------
now = datetime.now().strftime("%Y-%m-%d %H:%M")
HEAD = (
    "# 版本号: V2.6.153             修改时间: " + now + " "
    "(V2.6.153: 纯文案一处, 零逻辑、零参数, 无新增模块级大写常量, 参数指纹必仍为 efb96534。"
    "改的是退潮判断通过的那一行: 原文在退潮层判定通过后直接写 \"正常开仓\", 但退潮只是买入前置"
    "闸门里的其中一层, 其后还有情绪 L1 闸门、风险过滤、分批节奏等; 写成 \"正常开仓\" 等于拿局部"
    "结论冒充全局结论 —— 2026-10-21 13:25:02 的实盘日志里, 这一行与紧随其后的 \"暂不开新仓: "
    "情绪数据未就绪\" 出现在同一秒, 自相矛盾。现改为 \"退潮层通过(仍须过情绪等其它闸门)\": 只说"
    "清本层结论, 并明示后面还有闸门, 不会让人误以为整条买入链路已放行。该行每天只打一次(由 "
    "tide_ok_note_date 去重), 纯读数, 不参与任何判定, 交易行为零变化。)"
)

lines = txt.split(CRLF)
lines.insert(4, HEAD)
txt = CRLF.join(lines)

print("[文件头] 已插入 V2.6.153 记录行")
print("[文件头] 段数 -> %d (真实行数 %d)" % (len(lines), len(lines) - 1))

# ---------- 4. 写盘 ----------
out = txt.encode("gbk")
open(P, "wb").write(out)

# ---------- 5. 复核 ----------
raw2 = open(P, "rb").read()
txt2 = raw2.decode("gbk")
new_md5 = hashlib.md5(raw2).hexdigest()
L2 = txt2.split(CRLF)

checks = []
def ck(name, cond, detail=""):
    checks.append((name, bool(cond), detail))

ck("GBK 往返一致", txt2.encode("gbk") == raw2)
ck("无 BOM", not raw2.startswith(b"\xef\xbb\xbf"))
ck("裸 LF == 0", txt2.count("\n") == txt2.count(CRLF),
   "%d/%d" % (txt2.count("\n"), txt2.count(CRLF)))
ck("段数 14628", len(L2) == 14628, str(len(L2)))
ck("新文案在位", txt2.count(NEW) == 1)
ck("旧文案已删", txt2.count("未达退潮阈值%.0f%%, 正常开仓") == 0)
ck("VERSION 已升", txt2.count("VERSION = 'V2.6.153'") == 1)
ck("文件头首行版本 = V2.6.153",
   re.search(r"# 版本号: (V[\d.]+)", txt2).group(1) == "V2.6.153")
ck("旧版本记录行仍保留", txt2.count("# 版本号: V2.6.152") == 1)

# compile
try:
    compile(txt2, P, "exec")
    ck("compile", True)
except SyntaxError as e:
    ck("compile", False, str(e))

# AST: 硬止损调用仍为 0
tree = ast.parse(txt2)
nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "stop_order"]
attr = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "stop_order"]
ck("铁律: 硬止损 AST = 0", len(nodes) == 0 and len(attr) == 0,
   "Name=%d Attr=%d" % (len(nodes), len(attr)))

# 改动行的上下文
idx = next(i for i, l in enumerate(L2) if "退潮层通过" in l)
print("\n[改后上下文]")
for i in range(idx - 1, idx + 3):
    print("  L%d: %s" % (i + 1, L2[i]))

print("\n[新态] MD5=%s  字节=%d  (原 %s / %d, 增量 %+d 字节)"
      % (new_md5, len(raw2), old_md5, old_size, len(raw2) - old_size))

print("\n" + "=" * 64)
bad = 0
for name, ok, detail in checks:
    print("%s  %-28s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        bad += 1
print("=" * 64)
print("结果: %d/%d PASS" % (len(checks) - bad, len(checks)))
sys.exit(1 if bad else 0)
