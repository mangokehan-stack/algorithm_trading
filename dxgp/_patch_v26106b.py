# -*- coding: utf-8 -*-
"""V2.6.106 patch 第二阶段: E(应用侧累积判定) + 取数侧口径对齐 + F(bootstrap 重置)

全程 io.open(encoding='gbk', newline=''), 不经任何 Edit 类工具(会破坏 GBK 字节)。
所有区块替换前先断言首尾行内容, 定位失败即 exit(1), 不写盘。
"""
import io
import sys

F = 'zt_shrink_strategy_gbk.py'

with io.open(F, 'r', encoding='gbk', newline='') as fh:
    raw = fh.read()
L = raw.split('\r\n')
print('起始行数 %d' % len(L))
n_ops = 0


def find_a(pred, why, lo=0):
    for i in range(lo, len(L)):
        if pred(L[i]):
            return i
    print('!! 找不到锚: %s' % why)
    sys.exit(1)


def rep_block(a, b, lines, why):
    global n_ops
    n_ops += 1
    print('  [%s] 替换 L%d-L%d (%d 行 -> %d 行)'
          % (why, a + 1, b + 1, b - a + 1, len(lines)))
    L[a:b + 1] = lines


def ins_at(idx, lines, why):
    global n_ops
    L[idx:idx] = lines
    n_ops += 1
    print('  [%s] 插入 %d 行 @ L%d' % (why, len(lines), idx + 1))


# ============ E-1. 应用侧 _sent_apply_rows: 覆盖判定改累积 ============
a = find_a(lambda s: s.startswith('        _min_cov = SENT_COVERAGE_MIN'), 'E1 _min_cov')
assert L[a + 1].strip().startswith("if _cov.get('budget_hit')"), repr(L[a + 1])
assert L[a + 2].strip().startswith('_min_cov = 0.0'), repr(L[a + 2])
b = a
while L[b].strip() != 'return':
    b += 1
    if b - a > 12:
        print('!! E1 段定位失败')
        sys.exit(1)
rep_block(a, b, [
    "        _min_cov = SENT_COVERAGE_MIN",
    "        # ---- V2.6.106(方案9): 覆盖口径从'本轮'改为'跨轮累积' ----",
    "        #   旧逻辑(budget_hit 时 fail==0 且 ok>=480 即放行)已被累积机制取代:",
    "        #   每轮只从'还没取到的'里取, 多轮自然拼满, 不必再为预算截断单开例外。",
    "        #   累积达到 SENT_COVERAGE_MIN -> 出信号; 未达到 -> 挂起(沿用上次成功信号),",
    "        #   等下一轮继续拼。既不冻结, 也不用 34% 的偏样本去做买卖决策。",
    "        _acc_r = _cov.get('acc_ratio')",
    "        try:",
    "            _acc_r = float(_acc_r) if _acc_r is not None else None",
    "        except Exception:",
    "            _acc_r = None",
    "        if _acc_r is not None:",
    "            _ratio = _acc_r",
    "        if _ratio is not None and _ratio < _min_cov:",
    "            _SENT_ACC['pend_rounds'] = int(_SENT_ACC.get('pend_rounds') or 0) + 1",
    "            SENT_STATE['acc_pending'] = True",
    "            _sent_use_last_good(",
    "                '累积覆盖率%.1f%%(<%.0f%%下限; 本轮新取%d只/累积%d只/全市场%d只/"
    "失败%d只/重试%d次/第%d轮)'",
    "                % (_ratio * 100.0, _min_cov * 100.0,",
    "                   int(_cov.get('round_ok') or 0), int(_cov.get('acc_ok') or 0),",
    "                   int(_cov.get('req') or 0), int(_cov.get('fail') or 0),",
    "                   int(_cov.get('retry') or 0), int(_cov.get('rounds') or 0)))",
    "            return",
    "        SENT_STATE['acc_pending'] = False",
], 'E1 应用侧累积判定')

# ============ E-2. 取数侧 _cov_min: 改为累积口径 ============
a = find_a(lambda s: s.strip() == 'def _cov_min(_cv, _bh):', 'E2 _cov_min')
assert L[a + 4].strip() == 'return 0.0', repr(L[a + 4])
assert L[a + 5].strip() == 'return 0.98', repr(L[a + 5])
rep_block(a, a + 5, [
    "        # V2.6.106(方案9): 覆盖判定统一改为'跨轮累积'口径。",
    "        #   原 _cov_min(预算截断时 fail==0 且 ok>=480 即放行)已无意义 —— 累积机制下",
    "        #   每轮只取未取过的标的, 单轮必然不足, 关键看累积。此处仅供日志/告警用,",
    "        #   真正的采用/挂起判定在 _sent_apply_rows 里(同样以累积覆盖为准)。",
    "        _min_cov = SENT_COVERAGE_MIN",
], 'E2 _cov_min')

# 紧随的 _min_cov = _cov_min(...) 调用行
a = find_a(lambda s: s.strip() == '_min_cov = _cov_min(_cov, _budget_hit)', 'E2 调用')
rep_block(a, a, [], 'E2 删调用行')

# ============ E-3. 取数侧 budget 提示改累积 ============
a = find_a(lambda s: s.strip().startswith('if _budget_hit and _min_cov <= 0.0:'),
           'E3 budget 提示')
assert L[a + 4].strip().startswith('% (int(_cov.get'), repr(L[a + 4])
rep_block(a, a + 5, [
    "        if _budget_hit and _acc_ratio >= SENT_COVERAGE_MIN:",
    "            _sent_wlog('[提示] 本轮触发取数总预算, 已取%d只(累积覆盖%.1f%%), "
    "累积已达标: 采用本轮累积实测值'",
    "                       % (int(_cov.get('ok') or 0), _acc_ratio * 100.0))",
], 'E3 budget 提示')

# ============ E-4. 取数侧尾部覆盖告警改累积 ============
a = find_a(lambda s: s.strip().startswith("if _cov['ratio'] is not None and _cov['ratio'] < _min_cov:"),
           'E4 覆盖告警')
assert L[a + 5].strip() == "if _budget_hit else ''))", repr(L[a + 5])
rep_block(a, a + 5, [
    "        if _acc_ratio < SENT_COVERAGE_MIN:",
    "            _sent_wlog('[告警] 累积覆盖率不足(%.1f%% < %.0f%%): 本轮不采用, 沿用上一次成功信号, "
    "下一轮继续拼接(本轮新取%d只/累积%d只/全市场%d只)'",
    "                       % (_acc_ratio * 100.0, SENT_COVERAGE_MIN * 100.0,",
    "                          int(_cov.get('ok') or 0), int(_acc_cnt), int(len(_stocks))))",
], 'E4 覆盖告警')

# ============ F. bootstrap 重置累积池 ============
a = -1
for i in range(len(L)):
    if L[i].strip() == "SENT_STATE['rows'] = []" and L[i + 1].strip() == '_SENTIMENT_READY = False':
        a = i
        break
if a < 0:
    print('!! F 定位失败')
    sys.exit(1)
ins_at(a, [
    "        SENT_STATE['acc_pending'] = False",
    "        # V2.6.106(方案9): 重启即清空累积池 —— 换日/换进程都从零开始拼",
    "        _SENT_ACC.update({'date': '', 'md': {}, 'ok': 0, 'fail': 0,",
    "                          'retry': 0, 'rounds': 0, 'pend_rounds': 0})",
], 'F bootstrap 重置')

with io.open(F, 'w', encoding='gbk', newline='') as fh:
    fh.write('\r\n'.join(L))
print()
print('第二阶段完成, %d 处编辑, 新行数 %d' % (n_ops, len(L)))
