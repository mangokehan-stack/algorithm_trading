# -*- coding: utf-8 -*-
"""V2.6.151 干跑: 情绪未就绪是否真的拦住买入 + 原因文案是否分得开
纪律: 从母版 AST 切片取真实函数体执行, 不注入模块桩."""
import ast
import sys

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
src = t.replace('\r\n', '\n')
tree = ast.parse(src)
lines = src.split('\n')


def seg(n):
    return '\n'.join(lines[n.lineno - 1:n.end_lineno])


want_assign = {'_SENTIMENT_ON', '_SENTIMENT_READY', 'SENT_STATE', 'VERSION'}
chunks = []
for nd in tree.body:
    if isinstance(nd, ast.Assign):
        for tg in nd.targets:
            if isinstance(tg, ast.Name) and tg.id in want_assign:
                chunks.append(seg(nd))
want_fn = {'sent_gate_skip', 'sent_block_note'}
for nd in tree.body:
    if isinstance(nd, ast.FunctionDef) and nd.name in want_fn:
        chunks.append(seg(nd))

miss = want_assign | want_fn
got = set()
for nd in tree.body:
    if isinstance(nd, ast.Assign):
        got |= {tg.id for tg in nd.targets if isinstance(tg, ast.Name)}
    if isinstance(nd, ast.FunctionDef):
        got.add(nd.name)
lost = miss - got
assert not lost, '母版缺定义: %s' % lost

code = '\n\n'.join(chunks)
ns = {}
exec(compile(code, '<slice>', 'exec'), ns)
print('切片装载成功, 长度 %d 字符, 含: %s' % (len(code), sorted(want_fn)))

res = []


def case(name, on, ready, gate, want_skip, want_note_kw):
    ns['_SENTIMENT_ON'] = on
    ns['_SENTIMENT_READY'] = ready
    ns['SENT_STATE']['gate_skip'] = gate
    sk = ns['sent_gate_skip']()
    nt = ns['sent_block_note']()
    assert sk == want_skip, '%s: sent_gate_skip 期望 %r 实际 %r' % (name, want_skip, sk)
    if want_note_kw is None:
        assert nt == '', '%s: 期望空串实际 %r' % (name, nt)
    else:
        assert want_note_kw in nt, '%s: 期望含 %r 实际 %r' % (name, want_note_kw, nt)
    # 两函数必须一致: 有原因 <=> 拦阻
    assert bool(nt) == sk, '%s: 布尔与原因不一致 skip=%r note=%r' % (name, sk, nt)
    res.append((name, sk, nt))


case('模块关闭(总开关False)', False, False, True, False, None)
case('开着但未就绪(启动空窗期)', True, False, True, True, '未就绪')
case('开着但未就绪(降级)', True, False, False, True, '未就绪')
case('就绪+恐慌闸门触发', True, True, True, True, '情绪L1闸门')
case('就绪+正常放行', True, True, False, False, None)

# 关键回归: 旧版在"开着但未就绪"时返回 False 放行, 新版必须 True
ns['_SENTIMENT_ON'] = True
ns['_SENTIMENT_READY'] = False
ns['SENT_STATE']['gate_skip'] = False
assert ns['sent_gate_skip']() is True, '★ 未就绪必须在就绪标记为 False 时也拦(不受 state 值影响)'
res.append(('★ 未就绪 + state=False 仍拦', True, ns['sent_block_note']()))

# 文案渲染: can_open_new / risk_increase_allowed 的三句格式串
note = ns['sent_block_note']()
outs = {
    'can_open_new 双重': '%s + 市场退潮期(双重触发), 暂停新开仓' % note,
    'can_open_new 单情绪': '%s, 暂停新开仓' % note,
    'risk_increase': '%s, 暂停分批加仓' % note,
}
for k, v in outs.items():
    assert '%s' not in v, '%s 占位符没渲染: %r' % (k, v)

# AST 级确认消费点真的用了 note, 不是还留着旧写法
g2 = ast.parse(src)
found = {}
for nd in ast.walk(g2):
    if isinstance(nd, ast.FunctionDef) and nd.name in ('can_open_new', 'risk_increase_allowed'):
        b = seg(nd)
        found[nd.name] = b
assert 'sent_block_note()' in found['can_open_new'], 'can_open_new 未接入 note'
assert 'sent_block_note()' in found['risk_increase_allowed'], 'risk_increase 未接入 note'
assert "not sent_gate_skip()" not in found['can_open_new'], 'can_open_new 仍残留旧写法'
assert "'情绪L1闸门, 暂停新开仓'" not in found['can_open_new'], 'can_open_new 旧文案残留'
assert "情绪L1闸门(恐慌/狂热/极端事件), 暂停分批加仓'" not in found['risk_increase_allowed'], \
    'risk_increase 旧文案残留'

print()
for name, sk, nt in res:
    print('  %-30s skip=%-5s note=%s' % (name, sk, nt or '(空)'))
print()
for k, v in outs.items():
    print('  文案 %-22s %s' % (k, v))
print()
print('PASS  %d/%d' % (len(res) + 1, len(res) + 1))
