# -*- coding: utf-8 -*-
"""P2-8 修正: _patch_p2a.py 第二处插入误覆盖了 out[_dk] = v, 本脚本恢复该行"""
P = 'zt_shrink_strategy_gbk.py'
raw = open(P, encoding='gbk', newline='').read()
lines = raw.split('\r\n')
assert len(lines) == 11113, len(lines)

i = None
for idx, ln in enumerate(lines):
    if (ln == "                        _dk = datetime.datetime.fromtimestamp(_ts).strftime('%Y%m%d')"
            and lines[idx + 1] == '            except Exception:'
            and lines[idx + 2] == '                out[str(k)[:8]] = v'):
        i = idx
        break
assert i is not None, 'anchor not found'
assert 'out[_dk] = v' not in lines[i - 12:i + 1], 'out[_dk] already present?'
lines[i + 1:i + 1] = ['                out[_dk] = v']
assert len(lines) == 11114, len(lines)
open(P, 'w', encoding='gbk', newline='').write('\r\n'.join(lines))
print('restored out[_dk] = v after L%d; new count %d' % (i + 1, len(lines)))
