# -*- coding: utf-8 -*-
"""读取审计用清单/操作单/说明文件（自动探测编码），只读。"""
import os

BASE = r"E:\桌面\666666\dxgp"
FILES = [
    "_部署操作单_V26106.txt",
    "_部署操作单_V26105.txt",
    "_funcmap.txt",
    "_deleted_files_manifest.txt",
]

def decode(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("gbk", errors="replace"), "gbk-replace"

for fn in FILES:
    p = os.path.join(BASE, fn)
    if not os.path.exists(p):
        print("MISSING", fn)
        continue
    txt, enc = decode(p)
    lines = txt.splitlines()
    print("=" * 90)
    print("[%s] enc=%s lines=%d" % (fn, enc, len(lines)))
    print("=" * 90)
    show = lines[:120]
    for i, ln in enumerate(show, 1):
        print("%04d| %s" % (i, ln[:180]))