# -*- coding: utf-8 -*-
"""V2.6.101 收尾修正:
  1) 代码块注释里写了 "stop_order=0" 字样, 被铁律检查(全文 count stop_order == 0)抓到 -> 改掉
  2) _check_inv.py 的行数期望 12700 -> 12738 (本次新增 38 行)
"""
import io, re

SRC = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
CHK = r'E:\桌面\666666\dxgp\_check_inv.py'

# ---- 1) 去掉代码注释里的 stop_order 字样 ----
t = io.open(SRC, 'r', encoding='gbk', newline='').read()
old = '(NEVER_STOP_LOSS / stop_order=0 \u672a\u52a8)'
new = '(NEVER_STOP_LOSS \u672a\u52a8, \u5168\u7a0b\u65e0\u6b62\u635f\u5355\u903b\u8f91)'
n = t.count(old)
if n != 1:
    raise SystemExit('anchor fail: %d' % n)
t = t.replace(old, new, 1)
io.open(SRC, 'w', encoding='gbk', newline='').write(t)

# 再次确认全文(排除版本号行)无 stop_order
body = '\r\n'.join(l for l in t.split('\r\n') if not l.startswith('\u7248\u672c\u53f7: '))
print('stop_order_in_body=%d' % body.count('stop_order'))
print('NEVER_STOP_LOSS = True ->', 'NEVER_STOP_LOSS = True' in body)

# ---- 2) 同步 _check_inv.py 行数期望 ----
c = io.open(CHK, 'r', encoding='utf-8', newline='').read()
o2 = 'chk("\u884c\u6570=12700", len(lines) == 12700'
n2 = 'chk("\u884c\u6570=12738", len(lines) == 12738'
if c.count(o2) == 1:
    c = c.replace(o2, n2, 1)
    io.open(CHK, 'w', encoding='utf-8', newline='').write(c)
    print('check_inv line-count updated 12700 -> 12738')
else:
    print('WARN: check_inv anchor count=%d' % c.count(o2))

# ---- 3) 行数自检 ----
t2 = io.open(SRC, 'r', encoding='gbk', newline='').read()
print('LINES=%d  CRLF=%d' % (len(t2.split('\r\n')), t2.count('\r\n')))
import py_compile, hashlib
py_compile.compile(SRC, doraise=True)
print('PY_COMPILE_OK  MD5=%s' % hashlib.md5(t2.encode('gbk')).hexdigest().upper())
