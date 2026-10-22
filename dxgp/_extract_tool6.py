# -*- coding: utf-8 -*-
"""原文级搜索工具的 argparse 定义段，取上下文窗口。"""
import io, os, re, glob

BASE = r'C:\Users\MangoKehan\.workbuddy\projects'
files = []
for d in os.listdir(BASE):
    p = os.path.join(BASE, d)
    if os.path.isdir(p):
        files += glob.glob(os.path.join(p, '*.jsonl'))
    else:
        files.append(p)

PAT = re.compile(r"add_argument\(\s*['\"]--ann-pages")
found = []
for p in files:
    try:
        t = io.open(p, 'r', encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    for m in PAT.finditer(t):
        found.append((p, m.start()))

print('命中 add_argument --ann-pages 次数:', len(found))
for p, off in found[:5]:
    t = io.open(p, 'r', encoding='utf-8', errors='replace').read()
    seg = t[max(0, off - 2500):off + 2500]
    print('=' * 70)
    print('文件:', os.path.basename(os.path.dirname(p)), 'off', off)
    print(seg[:5200])
