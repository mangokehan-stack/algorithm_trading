# -*- coding: utf-8 -*-
"""Bump to V2.6.82: insert header version-history line + update VERSION constant."""
P = 'zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
text = raw.decode('gbk', errors='strict')
lines = text.split('\r\n')
base_n = len(lines)
base_crlf = text.count('\r\n')

# ---- anchors ----
old_v5 = lines[4]
assert old_v5.startswith('版本号: V2.6.81'), 'L5 not V2.6.81: %r' % old_v5[:60]
assert 'VERSION = \'V2.6.81\'' in lines[331], 'L332 VERSION mismatch: %r' % lines[331]

NEW = (
    '版本号: V2.6.82              修改时间: 2026-10-19 21:35 '
    '(V2.6.82记录: 未定义名全文件扫描(AST自由名 - 模块级定义 - builtins - QMT注入全局)坐实并修复2个真bug, '
    '用户确认"按推荐方案做" —— '
    '【Bug C】PYRAMID_BATCHES 从未定义(V2.6.78 P2-2加一致性校验时引入): '
    'pyramid_add 内 vol>=100 必抛NameError -> run_pyramid_adds 循环中断 -> _run_round_unlocked 冒泡到顶层except, '
    '整轮轮询在卖出完成后崩溃, 新买入与分批加仓永久被堵且每轮刷异常; '
    '改为与该票实际分批计划长度比对(_bn_plan=len(h[plan_batches])), 不等即真bug, 手数不足自动缩批不再误告警。 '
    '【Bug D】print_summary 从未定义(V2.6.63时代历史潜伏): '
    'init() 中 atexit.register(print_summary) 抛NameError被 except pass 静默吞掉, 连带下一行 _flush_names_cache 注册死亡'
    '(退出时名称缓存不强制落盘); 现补全 print_summary(): 输出本次运行买卖笔数+持仓只数, 收尾 _flush_log(force=True), 双注册链路恢复。 '
    '本轮另含 P2批次13项+回退修补与60项功能单测、不变量76项全过。'
    '仅修复缺陷, 未改任何交易逻辑/铁律/费率/阈值。'
)

# insert new history line at top of history block (before current L5)
lines.insert(4, NEW)
# update VERSION constant (now at index 332)
vi = [i for i, ln in enumerate(lines) if ln.startswith("VERSION = 'V2.6.81'")]
assert len(vi) == 1, vi
lines[vi[0]] = lines[vi[0]].replace("VERSION = 'V2.6.81'", "VERSION = 'V2.6.82'", 1)

new_text = '\r\n'.join(lines)
assert len(lines) == base_n + 1, len(lines)
assert new_text.count('\r\n') == base_crlf + 1
assert new_text.encode('gbk').decode('gbk') == new_text
compile(new_text, P, 'exec')
assert "VERSION = 'V2.6.82'" in new_text
assert new_text.count('版本号: V2.6.82') == 1
assert new_text.count('版本号: V2.6.81') == 1

open(P, 'wb').write(new_text.encode('gbk'))
print('bumped. lines=%d crlf=%d' % (len(lines), new_text.count('\r\n')))
