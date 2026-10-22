# -*- coding: utf-8 -*-
"""对指定文件跑 _check_inv.py 的全量不变量(用于基线对比)"""
import io, sys, os

TARGET = sys.argv[1]
src = io.open(r'E:\桌面\666666\dxgp\_check_inv.py', 'r', encoding='utf-8').read()
old_path = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
assert src.count(old_path) == 1, 'PATH anchor count=%d' % src.count(old_path)
src = src.replace(old_path, TARGET)

buf = io.StringIO()
_stdout = sys.stdout
sys.stdout = buf
try:
    exec(compile(src, '_check_inv_inline.py', 'exec'), {'__name__': '__main__'})
finally:
    sys.stdout = _stdout

out = buf.getvalue().splitlines()
fails = [l for l in out if l.startswith('FAIL')]
summary = [l for l in out if l.strip().endswith('PASS') and '/' in l]
print('=== TARGET: %s' % TARGET)
for l in fails:
    print(l)
for l in summary:
    print(l)
print('FAIL_COUNT=%d' % len(fails))
