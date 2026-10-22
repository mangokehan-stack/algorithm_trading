# -*- coding: utf-8 -*-
"""心跳双实例 + 排雷清单 专项"""
import re
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
L = t.split('\r\n')

print('======== A. 心跳链路: 谁调用谁 ========')
for i, s in enumerate(L):
    if re.search(r'\b(pnl_tick|status_log_if_changed|pnl_startup_note|pnl_halfhour_report|'
                 r'alert_portfolio|hourly_reason_dump|_clock_session_note)\s*\(', s) \
            and not s.strip().startswith('def '):
        print('  L%-6d %s' % (i + 1, s.strip()[:130]))

print()
print('======== B. 心跳的注册入口: handlebar / timer_poll / run_time ========')
for nm in ('def handlebar', 'def timer_poll', 'def _timer_poll_unlocked', 'def log_guard',
           'def after_init', 'def init('):
    for i, s in enumerate(L):
        if s.startswith(nm):
            print('  --- %s @L%d ---' % (nm, i + 1))
            for j in range(i, min(i + 26, len(L))):
                print('  %6d|%s' % (j + 1, L[j][:130]))
            print()
            break

print('======== C. 排雷清单 RISK_EXCLUDE 相关常量与函数 ========')
for i, s in enumerate(L[:700]):
    if re.match(r'^RISK_EXCLUDE[A-Z_]*\s*=', s) or re.match(r'^EXCLUDE[A-Z_]*\s*=', s):
        print('  L%-5d %s' % (i + 1, s.strip()[:140]))
print('  --- 函数 ---')
for i, s in enumerate(L):
    if re.match(r'^def .*(risk_exclude|exclude)', s):
        print('  L%-5d %s' % (i + 1, s.strip()[:140]))