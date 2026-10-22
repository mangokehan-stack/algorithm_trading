# -*- coding: utf-8 -*-
import re
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
L = t.split('\r\n')
def dump(nm, n=60):
    for i, s in enumerate(L):
        if s.startswith(nm):
            print('======== %s @L%d ========' % (nm, i + 1))
            for j in range(i, min(i + n, len(L))):
                print('%6d|%s' % (j + 1, L[j][:165]))
            print()
            return i
    print('!! %s 未找到' % nm); return -1
dump('def heartbeat_tick')
dump('def gen_announce', 50)
print('======== HEARTBEAT_SEC / GEN 相关常量 ========')
for i, s in enumerate(L[:800]):
    if re.match(r'^(HEARTBEAT|GEN|ACC)[A-Z_]*\s*=', s):
        print('  L%-5d %s' % (i + 1, s.strip()[:150]))
print()
print('======== 排雷清单: 路径解析与加载 ========')
dump('def risk_exclude_path', 30)