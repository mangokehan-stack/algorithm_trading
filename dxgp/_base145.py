# -*- coding: utf-8 -*-
"""V2.6.145 重新建立基线 + 核对上一轮已确认的6项是否已被别人修掉"""
import re, os, tempfile, py_compile, datetime

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
t = raw.decode('gbk')
L = t.split('\r\n')

print('======== A. 当前文件基线 ========')
print('最后修改 :', datetime.datetime.fromtimestamp(os.path.getmtime(P)).strftime('%Y-%m-%d %H:%M:%S'))
print('大小     : %d 字节' % len(raw))
print('行数     : %d' % (t.count('\r\n') + 1))
print('CRLF     : %d   孤立LF: %d   孤立CR: %d' % (t.count('\r\n'), t.count('\n') - t.count('\r\n'), t.count('\r') - t.count('\r\n')))
print('首3字节  :', raw[:3].hex(), '(23636f=无BOM)')
try:
    py_compile.compile(P, cfile=os.path.join(tempfile.gettempdir(), 'c145.pyc'), doraise=True)
    print('语法编译 : OK')
except Exception as e:
    print('语法编译 : FAIL ->', e)
ver = [s.strip() for s in L if s.startswith('VERSION =')]
print('VERSION  :', ver[0][:60] if ver else '未找到')
print('文件头版本记录(前3行):')
for i in range(4, 8):
    print('  L%d %s' % (i + 1, L[i][:150]))

print()
print('======== B. 上一轮已确认6项: 现在什么状态 ========')

def show_region(keyword, before=2, after=14, label=''):
    for i, s in enumerate(L):
        if keyword in s:
            print('  [%s] L%d' % (label or keyword, i + 1))
            for j in range(i - before, min(i + after, len(L))):
                print('       %6d|%s' % (j + 1, L[j][:150]))
            return True
    return False

# 问题1: 参数指纹覆盖
i = next((i for i, s in enumerate(L) if s.startswith('def param_fingerprint')), -1)
if i >= 0:
    j = next((k for k in range(i, i + 80) if 'keys = [' in L[k]), i)
    k = next((k for k in range(j, j + 80) if L[k].strip().startswith(']')), j)
    keys = re.findall(r"'([A-Za-z_][A-Za-z0-9_]*)'", '\n'.join(L[j:k + 1]))
    print('[问题1] param_fingerprint keys 数量 = %d' % len(keys))
    need = ['FEE_ON', 'FEE_COMMISSION_RATE', 'FEE_COMMISSION_MIN', 'FEE_STAMP_RATE',
            'FEE_TRANSFER_RATE', 'FEE_PROFILE', 'DYN_PROFIT_FEE', 'MAX_HOLD_TRDAYS',
            'SELL_TURNOVER_TOP', 'EARLY_SELL_BLOCK_MIN', 'EARLY_SELL_END_MIN',
            'PYRAMID_ON', 'TRAP_AUTO_HANDOFF', 'TRAP_EXCLUDE_FROM_PNL',
            'MAX_DAILY_BUYS_LIVE', 'MARKET_CAP_FILTER_ON', 'MARKET_TIDE_CHECK',
            'REBUY_GAP_TRDAYS', 'SENT_LAG_DAYS', 'SENT_CLIP_LIMIT']
    miss = [n for n in need if n not in keys]
    print('       关键项缺失: %s' % (miss if miss else '无(已补齐!)'))
    print('       是否仍含FEE_RATE_EST(废弃粗估): %s' % ('FEE_RATE_EST' in keys))

# 问题2: PARAM_VERIFY_ENFORCE 冻结
print('[问题2] state_broken 清除点:')
for i, s in enumerate(L):
    if 'G.state_broken = False' in s:
        print('       L%d|%s' % (i + 1, s.strip()[:130]))
print('       param_verify 独立标志: %s' % ('param_verify_block' in t or 'state_broken_param' in t))

# 问题3: 移交额度监控提醒
print('[问题3] 移交累计监控: %s' % ('handoff' in t.lower() and ('notify' in t.lower())))
for i, s in enumerate(L):
    if re.search(r'handoff.*(alert|notify|提醒|累计)', s):
        print('       L%d|%s' % (i + 1, s.strip()[:130]))

# 问题4: handle_unfilled_buy 裸 del
print('[问题4] handle_unfilled_buy 内的裸 del:')
fi = next((i for i, s in enumerate(L) if s.startswith('def handle_unfilled_buy')), -1)
if fi >= 0:
    for j in range(fi, min(fi + 200, len(L))):
        if re.match(r"^\s*del G\.state\['hold'\]", L[j]):
            print('       L%d|%s   <<< 仍在' % (j + 1, L[j].strip()))
    print('       该函数是否已改用 _safe_rollback_placeholder: %s'
          % ('_safe_rollback_placeholder' in '\n'.join(L[fi:fi + 200])))

# 问题5: orderError_callback 死代码
print('[问题5] orderError_callback 内 del 之后写 pend_vol:')
oi = next((i for i, s in enumerate(L) if s.startswith('def orderError_callback')), -1)
if oi >= 0:
    for j in range(oi, min(oi + 120, len(L))):
        if "del G.state['hold']" in L[j] or ("pend_vol" in L[j] and 'del' in L[j - 1] if j > oi else False):
            print('       L%d|%s' % (j + 1, L[j].strip()[:120]))

# 问题6: 轻微项
print('[问题6] SENT_LAG_DAYS 出现次数: %d' % t.count('SENT_LAG_DAYS'))
print('       孤立CR数量: %d' % (t.count('\r') - t.count('\r\n')))

print()
print('======== C. 本轮新增重点排查项: 定位 ========')
for kw, desc in [('pnl_tick', '心跳'), ('HEARTBEAT', '心跳常量'),
                 ('SENT_STATE', '情绪状态池'), ('risk_exclude', '排雷清单'),
                 ('RISK_EXCLUDE', '排雷常量'), ('排雷', '排雷中文')]:
    hits = [i + 1 for i, s in enumerate(L) if kw in s]
    print('  %-16s %-12s 出现 %d 次, 行号前10: %s' % (kw, desc, len(hits), hits[:10]))