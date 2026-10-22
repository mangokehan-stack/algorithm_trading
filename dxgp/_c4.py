# -*- coding: utf-8 -*-
import re
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
L = t.split('\r\n')
print('======== 1. 文件头版本记录 前12行 ========')
for i in range(0, 14):
    print('L%-3d| %s' % (i + 1, L[i][:300]))

print()
print('======== 2. 版本一致性核对 ========')
const = re.search(r"^VERSION\s*=\s*'([^']+)'", t, re.M)
print('VERSION 常量      :', const.group(1) if const else '未找到')
hdr = []
for i, s in enumerate(L[:40]):
    m = re.search(r'版本号:\s*(V[0-9.]+)', s)
    if m:
        hdr.append((i + 1, m.group(1)))
print('文件头声明版本号  :', hdr[:6])
print('是否一致          :', '一致' if hdr and const and hdr[0][1] == const.group(1) else '★不一致★')
# 备份文件版本
import os
for b in ['zt_shrink_strategy_gbk.py.bak_v2.6.145', 'zt_shrink_strategy_gbk.py.bak_v2.6.143']:
    fp = os.path.join(r'E:\桌面\666666\dxgp', b)
    if os.path.exists(fp):
        bt = open(fp, 'rb').read().decode('gbk')
        bm = re.search(r"^VERSION\s*=\s*'([^']+)'", bt, re.M)
        print('  备份 %-42s VERSION=%s' % (b, bm.group(1) if bm else '?'))

print()
print('======== 3. 心跳 pnl_tick 双实例风险: 全部定义与调用点 ========')
for i, s in enumerate(L):
    if re.search(r'^\s*(def pnl_tick|def _pnl_tick_unlocked|pnl_tick\(\)|_pnl_tick_unlocked\()', s):
        print('  L%d| %s' % (i + 1, s.strip()[:120]))
print('--- 心跳相关常量 ---')
for i, s in enumerate(L[:700]):
    if re.match(r'^HEARTBEAT[A-Z_]*\s*=', s) or re.match(r'^PNL_[A-Z_]*(TICK|REPORT)[A-Z_]*\s*=', s):
        print('  L%d| %s' % (i + 1, s.strip()[:120]))