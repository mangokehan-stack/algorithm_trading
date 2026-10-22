# -*- coding: utf-8 -*-
"""修注释里的 15%% 笔误(注释非格式化串, 会原样显示两个百分号)"""
import io, hashlib, py_compile

SRC = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = io.open(SRC, 'r', encoding='gbk', newline='').read()
old = '\u79bb\u653e\u91cf\u6b62\u76c8\u53ea\u5dee 15%% \u4ee5\u5185'
new = '\u79bb\u653e\u91cf\u6b62\u76c8\u53ea\u5dee 15% \u4ee5\u5185'
n = t.count(old)
if n != 1:
    raise SystemExit('anchor fail: %d' % n)
t = t.replace(old, new, 1)
io.open(SRC, 'w', encoding='gbk', newline='').write(t)

py_compile.compile(SRC, doraise=True)
print('PY_COMPILE_OK')
print('LINES=%d  MD5=%s' % (len(t.split('\r\n')), hashlib.md5(t.encode('gbk')).hexdigest().upper()))
