# -*- coding: utf-8 -*-
"""核查 xtquant/xtdata/stop_order 出现位置(代码 vs 注释) -> _audit_scan2.txt"""
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
L = open(P, 'rb').read().decode('gbk').split('\r\n')
out = []
def p(s=''):
    out.append(s)

def show(title, keys):
    p('=== %s ===' % title)
    for i, l in enumerate(L):
        s = l.strip()
        if any(k in s for k in keys):
            tag = '[注释]' if s.startswith('#') else '[代码]'
            p('L%-6d %s %s' % (i + 1, tag, s[:150]))
    p()

show('xtquant / xtdata', ['xtquant', 'xtdata'])
show('stop_order', ['stop_order'])
show('risk_exclude 相关', ['risk_exclude', 'def _load_risk'])
show('blacklist 相关', ['blacklist'])

open(r'E:\桌面\666666\dxgp\_audit_scan2.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('ok %d' % len(out))
