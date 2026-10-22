# -*- coding: utf-8 -*-
"""找历史上"情绪取数完成"那一行的确切格式, 以便本轮精准等待"""
import os
import re

P = r'C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_run.log'


def dec(b):
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('gbk', 'replace')


lines = [dec(x) for x in open(P, 'rb').read().split(b'\n') if x.strip()]
print('总行数 %d' % len(lines))

# 找含 [情绪] 且含 耗时/完成 的行
print('\n=== 含 [情绪] 且含 "耗时" 或 "完成" ===')
hits = [l for l in lines if '[情绪]' in l and ('耗时' in l or '完成' in l)]
for l in hits[-12:]:
    print(l[:250])

print('\n=== 含 "转dict" 的行(最近 6 条) ===')
for l in [x for x in lines if '转dict' in x][-6:]:
    print(l[:250])

print('\n=== 含 "累积池" 且含 "已落盘" 的行(最近 5 条) ===')
for l in [x for x in lines if '累积池' in x and ('已落盘' in x or '落盘' in x)][-5:]:
    print(l[:250])
