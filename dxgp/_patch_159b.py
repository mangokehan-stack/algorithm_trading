# -*- coding: utf-8 -*-
"""V2.6.159 收尾: 把 bootstrap 上方那句"clear 后原样放回"改成与实现一致
(现在只有信号完整才放回), 避免又留一处文档与代码不符。
"""
import os, sys, hashlib, ast

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
src = raw.decode('gbk')
assert src.encode('gbk') == raw

OLD = (
"        #   故 clear 前把该标记取出来, clear 后原样放回。\r\n")
NEW = (
"        #   故 clear 前把该标记取出来; V2.6.159 起改为与信号本体一起取出,\r\n"
"        #   只有本体完整才放回(见下方恢复条件), 否则丢弃标记让当天重取一次。\r\n")

c = src.count(OLD)
if c != 1:
    print('锚点命中 %d 次(应为1)' % c)
    sys.exit(1)
out = src.replace(OLD, NEW, 1)
enc = out.encode('gbk')
assert enc.decode('gbk') == out
ast.parse(out)
n = out.count('\r\n')
if out.count('\n') - n or out.count('\r') - n:
    sys.exit('换行不干净')
open(P + '.tmp', 'wb').write(enc)
os.replace(P + '.tmp', P)
d = open(P, 'rb').read()
print('OK 落盘 %d 字节 MD5=%s' % (len(d), hashlib.md5(d).hexdigest()[:8]))
