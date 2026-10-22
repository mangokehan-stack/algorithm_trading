# -*- coding: utf-8 -*-
import sys, hashlib, ast
sys.stdout.reconfigure(encoding="utf-8")
P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
b = open(P, "rb").read()
t = b.decode("gbk")
L = t.split("\r\n")
print("MD5      = %s" % hashlib.md5(b).hexdigest())
print("字节     = %d" % len(b))
print("段数     = %d  (真实行数 %d)" % (len(L), len(L) - 1))
print("BOM      = %s" % b.startswith(b"\xef\xbb\xbf"))
print("裸LF     = %d" % t.replace("\r\n", "").count("\n"))
print("裸CR     = %d" % t.replace("\r\n", "").count("\r"))
print("往返一致 = %s" % (t.encode("gbk").decode("gbk") == t))
import re
print("VERSION  = %s" % re.search(r"(?m)^VERSION = '([^']+)'", t).group(1))
print("文件头   = %s" % L[4][:60])
print()
print("--- 改动行定位 ---")
for i, l in enumerate(L):
    if "账本成交" in l:
        print("L%d: %s" % (i + 1, l.strip()))
print()
tree = ast.parse(t)
print("AST 可解析 = True")
print("禁词AST节点 = %d" % sum(1 for n in ast.walk(tree)
      if isinstance(n, ast.Name) and getattr(n, "id", "") == "stop" + "_order"))
mods = [n for n in tree.body if isinstance(n, ast.Assign)]
up = 0
for n in tree.body:
    if isinstance(n, ast.Assign) and n.targets and isinstance(n.targets[0], ast.Name):
        nm = n.targets[0].id
        if nm.isupper() and not nm.startswith("_"):
            up += 1
print("模块级大写常量(粗计) = %d" % up)
