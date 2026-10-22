# -*- coding: utf-8 -*-
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
t = raw.decode('gbk')
# 用 re 保留行尾, 精确定位每个孤立LF
import re
print('======== 孤立LF 的原始上下文(带行尾标记) ========')
for m in re.finditer(r'(?<!\r)\n', t):
    a, b = max(0, m.start() - 260), m.start() + 90
    ctx = t[a:m.start()].replace('\r\n', '\n<CRLF>\n')
    print('--- 偏移 %d ---' % m.start())
    print(repr(ctx[-300:]))
    print('  后接: %r' % t[m.start():m.start() + 80].replace('\r\n', '<CRLF>'))
    print()