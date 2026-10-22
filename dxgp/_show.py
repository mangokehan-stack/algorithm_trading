# -*- coding: utf-8 -*-
"""用法: python _show.py 标签 起始:结束 [起始:结束 ...]
输出到 _view_<标签>.txt (UTF-8)"""
import sys, os

BASE = r'E:\桌面\666666\dxgp'
P = os.path.join(BASE, 'zt_shrink_strategy_gbk.py')
tag = sys.argv[1]
t = open(P, 'rb').read().decode('gbk', 'replace')
L = t.split('\r\n')
out = []
for s in sys.argv[2:]:
    a, b = s.split(':')
    a, b = int(a), int(b)
    out.append('===== L%d-%d =====' % (a, b))
    for i in range(a - 1, min(b, len(L))):
        out.append('%5d| %s' % (i + 1, L[i]))
dst = os.path.join(BASE, '_view_%s.txt' % tag)
open(dst, 'w', encoding='utf-8').write('\n'.join(out))
print('ok %d lines -> %s' % (len(out), os.path.basename(dst)))
