# -*- coding: utf-8 -*-
"""指纹 A/B 对照: 用同一套收集逻辑分别跑"改前备份"与"当前文件"

这不依赖我猜的期望值 —— 若两者算出的指纹相同, 就证明本次改动没动指纹;
若不同, 再把差异打印出来定位。
"""
import ast
import io
import sys

FILES = [
    ('改前 V2.6.135', 'zt_shrink_strategy_gbk.py.bak-20261020-2148'),
    ('当前 V2.6.134', 'zt_shrink_strategy_gbk.py'),
]

NEED_FN = ['_fp_calc', '_fp_keys', 'sent_fingerprint']
NEED_EXACT = {'G', '_FP_DENY'}


def collect(src):
    tree = ast.parse(src)
    got = {}
    order = []
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name):
                    nm = tg.id
                    if (nm.isupper() and len(nm) > 1) or nm in NEED_EXACT:
                        got[nm] = ast.get_source_segment(src, n)
                        order.append(nm)
        if isinstance(n, ast.ClassDef):
            got['<class:%s>' % n.name] = ast.get_source_segment(src, n)
            order.append('<class:%s>' % n.name)
        if isinstance(n, ast.FunctionDef) and n.name in NEED_FN:
            got[n.name] = ast.get_source_segment(src, n)
            order.append(n.name)
    return got, order


res = {}
for label, path in FILES:
    src = io.open(path, 'rb').read().decode('gbk')
    got, order = collect(src)
    body = [got[k] for k in order if got.get(k)]
    g = {'__name__': '<fp>'}
    pre = ('import time, datetime, traceback, sys, os, json, csv, math, '
           'shutil, threading, random, re')
    exec(pre + '\n' + '\n\n'.join(body), g)
    fp, raw = g['_fp_calc'](g['_fp_keys']())
    res[label] = (fp, raw, len(got))
    print('%s: 指纹=%s  收集条目=%d  raw长度=%d' % (label, fp, len(got), len(raw)))

a, b = FILES[0][0], FILES[1][0]
if res[a][0] == res[b][0]:
    print()
    print('PASS  参数指纹零漂移 (%s)' % res[a][0])
    sys.exit(0)

print()
print('FAIL  指纹不同: %s vs %s' % (res[a][0], res[b][0]))
ra = res[a][1].split('|')
rb = res[b][1].split('|')
sa, sb = set(ra), set(rb)
print('  只在改前:', sorted(sa - sb)[:10])
print('  只在改后:', sorted(sb - sa)[:10])
sys.exit(1)
