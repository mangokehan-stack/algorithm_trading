# -*- coding: utf-8 -*-
"""V2.6.102 收尾: 到期日志的"超N个交易日"改为实际等待期 _ex_wait
   (赢家延长到 8 天后, 日志应显示 8 而不是写死 5)"""
import io, hashlib, py_compile

SRC = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = io.open(SRC, 'r', encoding='gbk', newline='').read()

old = "'分批等待超%d个交易日(已%d日), 放弃剩余%d股(计划%d股/已买%d股), '"
new = "'分批等待超%d个交易日(已%d日), 放弃剩余%d股(计划%d股/已买%d股), '"
n = t.count(old)
if n != 1:
    raise SystemExit('anchor1 fail: %d' % n)

# 只改 % 实参里的第一个: PYRAMID_MAX_WAIT_TRDAYS -> _ex_wait
old2 = "% (PYRAMID_MAX_WAIT_TRDAYS, waited, remain,"
new2 = "% (_ex_wait, waited, remain,"
n2 = t.count(old2)
if n2 != 1:
    raise SystemExit('anchor2 fail: %d' % n2)
t = t.replace(old2, new2, 1)

io.open(SRC, 'w', encoding='gbk', newline='').write(t)
py_compile.compile(SRC, doraise=True)
print('PY_COMPILE_OK  LINES=%d  MD5=%s' % (
    len(t.split('\r\n')), hashlib.md5(t.encode('gbk')).hexdigest().upper()))
