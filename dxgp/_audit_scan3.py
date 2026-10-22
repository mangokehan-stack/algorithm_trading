# -*- coding: utf-8 -*-
"""查备注后缀依赖 + log 签名"""
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
L = open(P, 'rb').read().decode('gbk').split('\r\n')
out = []
def p(s=''):
    out.append(s)

p('=== 备注后缀 NEW/ADD 的消费点 ===')
for i, l in enumerate(L):
    s = l.strip()
    if ("'NEW'" in s or '"NEW"' in s or "'ADD'" in s or '"ADD"' in s) and not s.startswith('#'):
        p('L%-6d %s' % (i + 1, s[:150]))
p()

p('=== log / disp / trigger_log 定义 ===')
for i, l in enumerate(L):
    s = l.strip()
    if s.startswith('def log(') or s.startswith('def disp(') or s.startswith('def disp_code(') \
            or s.startswith('def _flush_log(') or s.startswith('def pnl_alert('):
        p('L%-6d %s' % (i + 1, s[:150]))
p()

p('=== deal_callback 中 rm / parts 的使用行 ===')
for i, l in enumerate(L):
    s = l.strip()
    if 11179 <= i + 1 <= 11410 and ('rm' in s and ('parts' in s or "'|'" in s or 'split' in s)):
        p('L%-6d %s' % (i + 1, s[:150]))
p()

p('=== 情绪累积池 关键点 ===')
for i, l in enumerate(L):
    s = l.strip()
    if '_SENT_ACC' in s and not s.startswith('#'):
        p('L%-6d %s' % (i + 1, s[:140]))

open(r'E:\桌面\666666\dxgp\_audit_scan3.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('ok %d' % len(out))
