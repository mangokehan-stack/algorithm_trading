# -*- coding: utf-8 -*-
"""查 trap_credit_left 现状"""
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
L = open(P, 'rb').read().decode('gbk').split('\r\n')
out = []
for i, l in enumerate(L):
    if 'trap_credit' in l:
        s = l.strip()
        tag = '[注释]' if s.startswith('#') else '[代码]'
        out.append('L%-6d %s %s' % (i + 1, tag, s[:160]))
open(r'E:\桌面\666666\dxgp\_audit_trapcredit.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('ok %d' % len(out))
