# -*- coding: utf-8 -*-
"""V2.6.146 细查: 指纹覆盖 / 孤立LF / 6项现状 / 版本号一致性"""
import re
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
L = t.split('\r\n')          # 按CRLF切, 孤立LF会留在行内

print('======== 1. param_fingerprint 实际结构 ========')
i = next((i for i, s in enumerate(L) if 'def param_fingerprint' in s), -1)
print('定义在 L%d' % (i + 1))
for j in range(i, min(i + 55, len(L))):
    print('%6d|%s' % (j + 1, L[j][:160]))
    if j > i + 3 and re.match(r"^\s*return\b", L[j]):
        break