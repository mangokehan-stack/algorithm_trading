# -*- coding: utf-8 -*-
"""格式修正: _keep_partial_hold 与 is_own_position 之间补空行(PEP8 两函数间空行)"""
P = 'zt_shrink_strategy_gbk.py'
raw = open(P, encoding='gbk', newline='').read()
lines = raw.split('\r\n')
assert len(lines) == 11202, len(lines)
i = None
for idx, ln in enumerate(lines):
    if (ln == "                 '挂单状态已清理, 当日买入名额不退回' % _fv)"
            and lines[idx + 1] == 'def is_own_position(h):'):
        i = idx
        break
assert i is not None, 'anchor not found'
lines[i + 1:i + 1] = ['']
assert len(lines) == 11203
open(P, 'w', encoding='gbk', newline='').write('\r\n'.join(lines))
print('blank line inserted; new count', len(lines))
