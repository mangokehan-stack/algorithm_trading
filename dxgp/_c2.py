# -*- coding: utf-8 -*-
import re
P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
L = t.split('\r\n')

print('======== 1. _fp_keys / _FP_DENY / _fp_calc ========')
for nm in ('_FP_DENY', 'def _fp_keys', 'def _fp_calc', 'def code_fingerprint'):
    i = next((i for i, s in enumerate(L) if s.startswith(nm) or nm in s[:20]), -1)
    if i < 0:
        print('  %s: 未找到' % nm); continue
    print('--- %s @L%d ---' % (nm, i + 1))
    for j in range(i, min(i + 34, len(L))):
        print('%6d|%s' % (j + 1, L[j][:150]))
        if re.match(r'^\s*(def |_FP_|return|\})', L[j]) and j > i + 2 and L[j].strip() in ('}',) :
            break
    print()

print('======== 2. 关键参数是否进了自动捕获 ==========')
i = next((i for i, s in enumerate(L) if s.startswith('def _fp_keys')), -1)
keysblk = '\n'.join(L[i:i + 40]) if i >= 0 else ''
deny = '\n'.join(L[:3200])
need = ['FEE_COMMISSION_RATE', 'FEE_COMMISSION_MIN', 'FEE_STAMP_RATE', 'FEE_TRANSFER_RATE',
        'FEE_PROFILE', 'FEE_ON', 'DYN_PROFIT_FEE', 'MAX_HOLD_TRDAYS', 'SELL_TURNOVER_TOP',
        'PYRAMID_ON', 'TRAP_AUTO_HANDOFF', 'TRAP_EXCLUDE_FROM_PNL', 'MAX_DAILY_BUYS_LIVE',
        'MARKET_CAP_FILTER_ON', 'MARKET_TIDE_CHECK', 'REBUY_GAP_TRDAYS', 'SENT_LAG_DAYS',
        'SENT_CLIP_LIMIT', 'SENT_REGIME_PANIC_LO', 'SENT_REGIME_FRENZY_HI', 'SENT_VERSION',
        'SENT_CORE_PARAMS', 'SENT_REGIME_PARAMS', 'STRATEGY_CASH_CAP', 'MAX_POS_VALUE_ABS']
# 自动捕获: 只要不是下划线开头的大写常量就会收, 所以只需看是否被 DENY 排除
for n in need:
    in_deny = re.search(r"['\"]%s['\"]" % re.escape(n), deny)
    print('  %-26s %s' % (n, '⚠ 可能在排除名单' if in_deny else 'OK 自动捕获'))

print()
print('======== 3. 83个孤立LF 定位 ==========')
cnt = 0
for idx, s in enumerate(L):
    if '\n' in s:
        cnt += 1
        if cnt <= 8:
            print('  L%d 含孤立LF: %r' % (idx + 1, s[-90:]))
print('  含孤立LF 的行数: %d' % cnt)