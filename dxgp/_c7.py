# -*- coding: utf-8 -*-
import re
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
L = t.split('\r\n')
def dump(nm, n=70):
    for i, s in enumerate(L):
        if s.startswith(nm):
            print('======== %s @L%d ========' % (nm, i + 1))
            for j in range(i, min(i + n, len(L))):
                print('%6d|%s' % (j + 1, L[j][:170]))
            print()
            return i
    print('!! %s 未找到\n' % nm); return -1

print('======== HEARTBEAT_SEC / STALE / FILE 定义位置 ========')
for nm in ('HEARTBEAT_SEC', 'HEARTBEAT_STALE_SEC', 'HEARTBEAT_FILE', 'GEN_FILE', 'GEN_DOWN'):
    hits = [(i + 1, L[i][:150]) for i, s in enumerate(L) if re.match(r'^\s*%s\s*=' % nm, s)]
    print('  %-22s %s' % (nm, hits if hits else '★ 未找到赋值'))

dump('def load_risk_exclude', 75)
dump('def risk_excluded', 60)