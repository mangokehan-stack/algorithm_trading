# -*- coding: utf-8 -*-
"""深挖 QMT 侧策略文档: 全文扫描 userdata/mpython/python 等目录, 找终版母版特征串。"""
import os, time, hashlib

ROOTS = [
    r'C:\广发证券QMT量化交易系统 - 交易端\userdata',
    r'C:\广发证券QMT量化交易系统 - 交易端\userdata_mini',
    r'C:\广发证券QMT量化交易系统 - 交易端\mpython',
    r'C:\广发证券QMT量化交易系统 - 交易端\python',
    r'C:\广发证券QMT量化交易系统 - 交易端\config',
    r'C:\广发证券QMT量化交易系统 - 交易端\config_local',
]
NEEDLES = [b'\xe5\xb8\xbd\xe4\xb8\x8d\xe8\xb6\xb3\xe4\xb8\x80\xe6\x89\x8b\xe6\x8b\x92\xe5\x8d\x95',  # 帽不足一手拒单
           b'zt_shrink', b'V2.6.161']
t0 = time.time()
hits = []
scanned = 0
for root in ROOTS:
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        if time.time() - t0 > 40:
            print('(超时停止)')
            dirnames[:] = []
            break
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(p)
                if sz < 2000 or sz > 60000000:
                    continue
                with open(p, 'rb') as fh:
                    data = fh.read()
                scanned += 1
                found = [n for n in NEEDLES if n in data]
                if found:
                    hits.append((p, sz, found))
            except Exception:
                pass
print('扫描文件数 =', scanned, '| 命中 =', len(hits))
for p, sz, found in hits[:30]:
    names = []
    for n in found:
        try:
            names.append(n.decode('utf-8'))
        except Exception:
            names.append(repr(n))
    print('%s | %d bytes | %s' % (p, sz, names))
