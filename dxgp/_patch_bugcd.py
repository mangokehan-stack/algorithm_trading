# -*- coding: utf-8 -*-
"""V2.6.82 patch: fix two undefined-name bugs in zt_shrink_strategy_gbk.py

Bug C: PYRAMID_BATCHES never defined (L7515) -> NameError on every pyramid add
Bug D: print_summary never defined (L10255) -> atexit registration dies silently,
       taking _flush_names_cache registration with it

GBK-safe editing: read with newline='', split on CRLF, assert before write.
"""
import sys

P = 'zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
text = raw.decode('gbk', errors='strict')
lines = text.split('\r\n')
base_n = len(lines)
base_crlf = text.count('\r\n')

# ---------------- anchors ----------------
HDR = '# ==================== 框架入口 ===================='
idx_hdr = [i for i, ln in enumerate(lines) if ln == HDR]
assert len(idx_hdr) == 1, 'header anchor count=%d' % len(idx_hdr)
i_hdr = idx_hdr[0]

C0 = '    # V2.6.78 P2-2: batch_total 与 PYRAMID_BATCHES 参数一致性校验'
C1 = '    if batch_total != PYRAMID_BATCHES:'
proc_idx = [i for i, ln in enumerate(lines) if ln == C1]
assert len(proc_idx) == 1, 'bug C anchor count=%d' % len(proc_idx)
i_c = proc_idx[0]
assert lines[i_c - 1] == C0, 'bug C comment anchor mismatch: %r' % lines[i_c - 1]
assert '% (batch_total, PYRAMID_BATCHES)' in lines[i_c + 1], 'bug C log line mismatch'
assert i_c < i_hdr, 'expected bug C above framework header'

# ---------------- edit 1 (bottom): insert print_summary before header ----------------
fn = [
    'def print_summary():',
    '    """V2.6.82修复(2026-10-19): 本函数此前从未定义 —— init() 中 atexit.register(print_summary)',
    '    抛NameError被 except Exception: pass 静默吞掉, 连带下一行 _flush_names_cache 的注册一并',
    '    死亡(策略停止时无交易笔数汇总, 退出时名称缓存不强制落盘)。',
    '    现补全: 输出本次运行买卖笔数(进程内计数, 重启清零; 准确账本见状态文件trades)',
    '    + 当前持仓只数, 收尾强制落盘日志。整体 try/except 保底(atexit 内绝不能再抛)。',
    '    """',
    '    try:',
    "        _bc = int(getattr(G, 'buy_cnt', 0) or 0)",
    "        _sc = int(getattr(G, 'sell_cnt', 0) or 0)",
    "        _st = getattr(G, 'state', None)",
    "        _hn = len(_st.get('hold') or {}) if isinstance(_st, dict) else 0",
    "        log('================ 本次运行结束汇总 ================')",
    "        log('[汇总] 本次运行买入%d笔 卖出%d笔, 当前持仓%d只 (进程内计数, 重启清零; '",
    "            '准确账本见状态文件trades)' % (_bc, _sc, _hn))",
    '    except Exception:',
    '        traceback.print_exc()',
    '    try:',
    '        _flush_log(force=True)      # 收尾强制落盘, 保证最后一屏日志与汇总进文件',
    '    except Exception:',
    '        traceback.print_exc()',
]
assert len(fn) == 21
ins1 = fn + ['']
for k, s in enumerate(ins1):
    lines.insert(i_hdr + k, s)

# ---------------- edit 2 (top): replace bug C block (3 lines -> 9 lines) ----------------
new_c = [
    '    # V2.6.82修复(2026-10-19): 原校验(V2.6.78 P2-2)引用了从未定义的PYRAMID_BATCHES ——',
    '    #   凡vol>=100的加仓调用必抛NameError, 经 run_pyramid_adds -> _run_round_unlocked 冒泡,',
    '    #   使整轮轮询在卖出完成后崩溃(新买入与分批加仓永久被堵, 每轮刷异常日志)。',
    '    #   现改为与该票"实际分批计划"的长度比对: 调用方传入的 batch_total 本就取自',
    "    #   len(h['plan_batches']), 不相等即为真bug; 手数不足自动缩批(长度<PYRAMID_SPLITS)",
    '    #   属正常行为, 不再误告警。',
    "    _bn_plan = len(h.get('plan_batches') or [])",
    '    if _bn_plan > 0 and batch_total != _bn_plan:',
    "        log(disp(s), '[参数一致性告警] 分批加仓批数不一致: 传入%d批 != 本票计划%d批, 日志批次显示可能有误'",
    "            % (batch_total, _bn_plan))",
]
assert len(new_c) == 10, len(new_c)
lines[i_c - 1:i_c + 2] = new_c

# ---------------- verify ----------------
new_text = '\r\n'.join(lines)
delta = len(lines) - base_n
assert delta == (len(ins1) + len(new_c) - 3) == 29, 'delta=%d' % delta
assert new_text.count('\r\n') == base_crlf + delta, 'CRLF mismatch'
assert new_text.encode('gbk').decode('gbk') == new_text, 'GBK roundtrip failed'

# no executable reference to PYRAMID_BATCHES left
bad = [i + 1 for i, ln in enumerate(lines)
       if 'PYRAMID_BATCHES' in ln and not ln.lstrip().startswith('#')]
# exclude version-history header lines (they are a long comment block, but start with 版本号)
bad = [n for n in bad if not lines[n - 1].lstrip().startswith('版本号')]
assert not bad, 'executable PYRAMID_BATCHES leftovers at %r' % bad

assert sum(1 for ln in lines if ln.startswith('def print_summary(')) == 1
assert 'print_summary' in new_text

compile(new_text, P, 'exec')

open(P, 'wb').write(new_text.encode('gbk'))
print('written. base=%d delta=+%d new=%d crlf=%d'
      % (base_n, delta, len(lines), new_text.count('\r\n')))
print('BUG C/D PATCH OK')
