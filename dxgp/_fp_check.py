# -*- coding: utf-8 -*-
"""
用【文件里的真实函数】算参数指纹（不自己另写算法，不注入模块桩）。
按依赖闭包精确收集：
  - 全部模块级 UPPER_CASE 常量（_fp_keys 要遍历 globals）
  - G = _G() 依赖的 _G 类
  - _FP_DENY / _fp_keys / _fp_calc / param_fingerprint / code_fingerprint
"""
import ast

P = 'zt_shrink_strategy_gbk.py'
src = open(P, 'rb').read().decode('gbk')
tree = ast.parse(src)

NEED_FUNCS = {'_fp_keys', '_fp_calc', 'param_fingerprint', 'code_fingerprint'}
NEED_CLASSES = {'_G'}
NEED_ASSIGN_EXACT = {'G'}          # G = _G()

chunks = []
got = {'const': 0, 'cls': 0, 'fn': 0, 'asg': 0}

for node in tree.body:
    seg = ast.get_source_segment(src, node)
    if seg is None:
        continue
    keep = False
    if isinstance(node, ast.ClassDef) and node.name in NEED_CLASSES:
        keep = True; got['cls'] += 1
    elif isinstance(node, ast.FunctionDef) and node.name in NEED_FUNCS:
        keep = True; got['fn'] += 1
    elif isinstance(node, ast.Assign):
        ids = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if any(i in NEED_ASSIGN_EXACT for i in ids):
            keep = True; got['asg'] += 1
        elif any(i.isupper() for i in ids):
            keep = True; got['const'] += 1
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        if node.target.id.isupper():
            keep = True; got['const'] += 1
    if keep:
        chunks.append((node.lineno, seg))

print('收集统计:', got)
assert got['cls'] == 1, '_G 类收集异常'
assert got['asg'] == 1, 'G = _G() 收集异常'
assert got['fn'] == 4, '指纹函数收集异常'

chunks.sort(key=lambda x: x[0])
body = '\r\n\r\n'.join(c[1] for c in chunks).replace('\r\n', '\n')

# 真实 import 环境（与文件头一致）
import time, datetime, traceback, sys, os, json, csv, math, shutil, threading, random, re
g = {
    '__name__': '__fp_test__',
    'time': time, 'datetime': datetime, 'traceback': traceback, 'sys': sys,
    'os': os, 'json': json, 'csv': csv, 'math': math, 'shutil': shutil,
    'threading': threading, 'random': random, 're': re,
}
exec(compile(body, '<fp>', 'exec'), g)

print()
pf, pf_txt = g['param_fingerprint']()
cf, cf_txt = g['code_fingerprint']()
print('param_fingerprint =', pf)
print('code_fingerprint  =', cf)
print('常量条目数 =', len(g['_fp_keys']()))
print()
assert pf == '8a4ab7e8', '参数指纹漂移! 得到 %s' % pf
print('[PASS] 参数指纹零漂移 = 8a4ab7e8')
print('[INFO] 版本指纹 = %s (VERSION 已升到 V2.6.133, 变化属预期)' % cf)
