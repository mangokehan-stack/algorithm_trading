# -*- coding: utf-8 -*-
"""零预设审计: 关键点位逐项断言(程序化证据)"""
import ast, re

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
src = open(P, 'rb').read().decode('gbk').replace('\r\n', '\n')
L = src.split('\n')
out = []
def p(s=''):
    out.append(s)

def has(s):
    return s in src

# A 历史修复点复核
p('=== A 历史修复点逐项复核 ===')
checks = [
    ('V2.6.136/137 累积池 v>=2 分支还原为 dict', "_box[str(_c)] = dict(_one)" in src),
    ('V2.6.137 旧的 list 形状 [_cc,_pp] 已消失', "= [_cc, _pp]" not in src),
    ('V2.6.138 抛点日志(extract_tb 末三帧)', 'extract_tb' in src and '抛点' in src),
    ('V2.6.138 坏样本按只兜底 _nbad3', '_nbad3' in src),
    ('V2.6.138 异常轮告警不编造读数', '本轮取数异常作废' in src),
    ('V2.6.138 isinstance(_row3, dict) 守卫', 'isinstance(_row3, dict)' in src),
    ('V2.6.85 VERSION 排除出参数指纹', "'VERSION'" in src.split('_FP_DENY = {')[1].split('}')[0]),
    ('V2.6.108 世代自噬加锁 _GEN_DOWN', "_GEN_DOWN.get('yes')" in src),
    ('V2.6.88 心跳启动自证', '心跳已就绪' in src),
    ('V2.6.88 换手率自算兜底 _float_share', 'def _float_share' in src),
    ('V2.6.91 世代判定三条件', 'def _gen_superseded' in src),
    ('V2.6.106 累积池 _SENT_ACC', '_SENT_ACC = {' in src),
    ('V2.6.149 缓存覆盖率日志', '%d/%d只(%.1f%%)' in src),
    ('V2.6.149 ratio 保留 1.0 + 说明注释', 'ratio 刻意保留 1.0' in src),
]
for name, ok in checks:
    p('  %s %s' % ('PASS' if ok else 'FAIL', name))
p()

# B 止损铁律 AST
p('=== B 铁律 AST 复核 ===')
tree = ast.parse(src)
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
         and getattr(getattr(n, 'func', None), 'id', '') == 'stop_order']
attrs = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == 'stop_order']
p('  stop_order 直接调用 = %d ; 属性引用 = %d' % (len(calls), len(attrs)))
p('  NEVER_STOP_LOSS = %s' % re.search(r'^NEVER_STOP_LOSS\s*=\s*(\S+)', src, re.M).group(1))
p()

# C 卖出铁律闸门存在性(无条件, 不依赖开关)
p('=== C 卖出铁律闸门 ===')
for name, pat in [
    ('is_at_loss 无条件拦截', 'if is_at_loss(h, lp):'),
    ('扣费净利无条件拦截', 'if net_pnl_if_sell(h, px, s) <= 0:'),
    ('解套保护价 floor', 'floor_px = _f(exit_price_needed(h, s))'),
    ('亏损禁卖结构化日志', '卖出拦截-亏损禁卖(铁律)'),
    ('扣费不为正结构化日志', '卖出拦截-扣费净利不为正'),
]:
    p('  %s %s' % ('PASS' if has(pat) else 'FAIL', name))
p()

# D 重复下单防线
p('=== D 重复下单防线 ===')
for name, pat in [
    ('发单前 critical 落盘(买入首笔)', 'if not save_state(critical=True):'),
    ('在途量先于 passorder 设置', "h['pend_vol'] = int(vol)"),
    ('异常后实时查柜台(_o = buy_order_obj(s, None))', 'buy_order_obj(s, None)'),
    ('撤单宽限期 CANCEL_CONFIRM_GRACE_SEC', 'CANCEL_CONFIRM_GRACE_SEC'),
    ('委托归属三重判定 _own_order', 'def _own_order'),
    ('成交幂等键 _deal_key', 'def _deal_key'),
    ('当日买入 codes 重入守卫', 'daily_buy_done'),
    ('在途占持仓名额(Q2)', "or int(_f(h.get('pend_vol', 0)) or 0) > 0"),
]:
    p('  %s %s' % ('PASS' if has(pat) else 'FAIL', name))
p()

# E 情绪覆盖率观测点(本次发现的 P2)
p('=== E 情绪缓存路径放行门槛 ===')
i = src.find('def _sent_fetch_from_cache')
seg = src[i:i + 800]
m = re.search(r'len\(_gh\) < (\d+)', seg)
p('  当前门槛: len(_gh) < %s 只即放行聚合' % (m.group(1) if m else '?'))
p('  cover["ratio"] 在缓存路径被写死为 1.0: %s' % ('"ratio": 1.0' in src))
p('  真实覆盖率只进日志: %s' % ('%d/%d只(%.1f%%)' in src))
p()

# F 移交释放双额度
p('=== F 移交后释放股票名额与资金额度 ===')
for name, okflag in [
    ('持有名额排除 is_handoff', 'and not is_handoff(h)' in src),
    ('资金占用排除 is_handoff', 'if is_handoff(_h):' in src),
    ('移交名义额度不回填(trap_credit_left 已删)', 'trap_credit_left' not in src),
]:
    p('  %s %s' % ('PASS' if okflag else 'FAIL', name))
p('  is_handoff 定义: %s' % ('有' if 'def is_handoff' in src else '缺失'))
p()

open(r'E:\桌面\666666\dxgp\_audit_verify.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('ok %d' % len(out))
