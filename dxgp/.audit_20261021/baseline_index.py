# -*- coding: utf-8 -*-
"""建立 GBK 交付版策略代码审计基线索引（只读，不改原文件）。
输出：.audit_20261021/baseline_index.txt（完整索引）+ stdout（摘要）。
"""
import ast
import io
import os
import re
import sys

BASE = r"E:\桌面\666666\dxgp"
SRC = os.path.join(BASE, "zt_shrink_strategy_gbk.py")
OUT = os.path.join(BASE, ".audit_20261021", "baseline_index.txt")

# ---------- 1. 字节与编码探测 ----------
raw = open(SRC, "rb").read()
lines = []
bom_info = "无BOM"
if raw[:3] == b"\xef\xbb\xbf":
    bom_info = "有 UTF-8 BOM"
elif raw[:2] == b"\xff\xfe":
    bom_info = "有 UTF-16 LE BOM"
elif raw[:2] == b"\xfe\xff":
    bom_info = "有 UTF-16 BE BOM"

text = None
dec_err = None
for enc in ("gbk", "utf-8"):
    try:
        text = raw.decode(enc)
        lines = text.splitlines()
        dec_err = None
        break
    except UnicodeDecodeError as e:
        dec_err = (enc, str(e))
        continue

crlf = text.count("\r\n") if text else -1
lf_only = text.count("\n") - crlf if text else -1

# ---------- 2. 版本注释（文件头） ----------
head = "\n".join(lines[:60]) if lines else ""

# ---------- 3. VERSION 常量 ----------
ver_m = re.search(r"^\s*VERSION\s*=\s*['\"]([^'\"]+)['\"]", text, re.M) if text else None

# ---------- 4. AST 索引 ----------
funcs = []   # (kind, qualname, start, end)
classes = []
assigns = []  # 模块级大写常量赋值
try:
    tree = ast.parse(text) if text is not None else None
except SyntaxError as e:
    tree = None
    syntax_err = str(e)
else:
    syntax_err = None

if tree is not None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            end = getattr(node, "end_lineno", node.lineno)
            funcs.append(("func", node.name, node.lineno, end))
        elif isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            classes.append((node.name, node.lineno, end))

    # 模块级顶层赋值（常量）
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    assigns.append((t.id, node.lineno))

# ---------- 5. 情绪模块标记 ----------
emot_tags = []
for i, ln in enumerate(lines, 1):
    if re.search(r"情绪|SENTIMENT|sent_|SENT_", ln, re.I) and re.search(r"BEGIN|END|====|-----|#.*情绪", ln):
        emot_tags.append((i, ln.strip()[:90]))

# ---------- 6. 关键函数定位 ----------
KEY = ["init", "can_open_new", "buy_stock", "calc_size", "risk_increase_allowed",
       "is_at_loss", "handlebar", "_timer_poll_unlocked", "_run_round_unlocked",
       "load_universe", "_autofix_sector_data", "sent_fetch_all_data", "param_fingerprint",
       "passorder", "heartbeat", "heart_beat", "_backtest", "backtest", "回测"]
key_hits = []
for kind, name, s, e in funcs:
    for k in KEY:
        if name == k or (k in name and len(name) <= len(k) + 12):
            key_hits.append((kind, name, s, e, "==" if name == k else "~"))
            break

# ---------- 7. 写输出 ----------
buf = io.StringIO()
buf.write("=" * 100 + "\n")
buf.write("GBK 交付版策略代码审计基线索引\n")
buf.write("生成时间: 2026-10-21 11:13 (审计任务)\n")
buf.write("=" * 100 + "\n\n")
buf.write("[文件] %s\n" % SRC)
buf.write("[大小] %d 字节\n" % len(raw))
buf.write("[编码] %s\n" % ("GBK 解码成功" if dec_err is None and text is not None and bom_info == "无BOM" else ("UTF-8 解码成功" if dec_err is None else "解码失败")))
buf.write("[BOM] %s\n" % bom_info)
buf.write("[行尾] CRLF=%d, 纯LF=%d\n" % (crlf, lf_only))
buf.write("[总行数] %d\n" % len(lines))
buf.write("[VERSION 常量] %s\n" % (ver_m.group(1) if ver_m else "未找到"))
buf.write("[AST 语法解析] %s\n" % ("成功" if syntax_err is None else ("失败: " + syntax_err)))
buf.write("[模块级函数数] %d  [类数] %d\n" % (len(funcs), len(classes)))
buf.write("\n----- 文件头 60 行（版本注释区） -----\n")
buf.write(head + "\n")
buf.write("\n----- VERSION 常量上下文 -----\n")
if ver_m:
    ln = ver_m.group(0)
    start = text[:ver_m.start()].count("\n") + 1
    for i in range(max(1, start - 2), min(len(lines), start + 3) + 1):
        buf.write("L%05d: %s\n" % (i, lines[i - 1]))
else:
    buf.write("未找到 VERSION = '...'\n")
buf.write("\n----- 情绪模块标记行（BEGIN/END/=====） -----\n")
for i, s in emot_tags:
    buf.write("L%05d: %s\n" % (i, s))
buf.write("\n----- 关键函数定位（kind, name, start-end, 匹配方式） -----\n")
for h in key_hits:
    buf.write("%-8s %-28s L%05d - L%05d  [%s]\n" % h)
buf.write("\n----- 模块级大写常量（前 120 个） -----\n")
for name, ln in assigns[:120]:
    buf.write("L%05d: %s\n" % (ln, name))
buf.write("\n----- 全部函数索引（module-level 与类内，共 %d 个） -----\n" % len(funcs))
for kind, name, s, e in funcs:
    buf.write("L%05d - L%05d  %s\n" % (s, e, name))
buf.write("\n----- 全部类索引 -----\n")
for name, s, e in classes:
    buf.write("L%05d - L%05d  class %s\n" % (s, e, name))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(buf.getvalue())

# ---------- 8. stdout 摘要 ----------
print("file_size=%d" % len(raw))
print("encoding=%s" % ("gbk" if dec_err is None and text is not None and bom_info == "无BOM" else "??"))
print("bom=%s" % bom_info)
print("lines=%d crlf=%d lf_only=%d" % (len(lines), crlf, lf_only))
print("version_const=%s" % (ver_m.group(1) if ver_m else "None"))
print("ast_ok=%s" % (syntax_err is None))
print("func_count=%d class_count=%d" % (len(funcs), len(classes)))
print("emot_tag_count=%d" % len(emot_tags))
print("key_hits=%d" % len(key_hits))
print("out=%s" % OUT)