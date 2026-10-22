# -*- coding: utf-8 -*-
"""P2-3 回退修补(2026-10-19): 修复 load_state hold 校验两个缺陷
缺陷A: hold 缺失时 disk.get('hold')=None 被误判容器损坏 -> 误冻结交易
缺陷B: hold 类型错误时通用循环先重置成 {}, 掩盖容器损坏信号 -> state_broken 漏置位
方案: 循环前抓原始值 + 哨兵区分缺失/null + hold 跳过通用循环由专用块处理"""
import io, sys

p = 'zt_shrink_strategy_gbk.py'
raw = open(p, 'rb').read()
assert raw.count(b'\r\n') > 10000, 'CRLF baseline missing'
txt = raw.decode('gbk')
lines = txt.split('\r\n')
base = len(lines)

def L(n):   # 1-based -> 0-based
    return lines[n - 1]

# ---- 锚点断言(ASCII 安全) ----
assert L(1267).lstrip().startswith('# P2-3'), 'L1267 anchor'
assert L(1268) == '            _bad = []', 'L1268 anchor'
assert L(1269) == '            for _fk, _fd in _STATE_SCHEMA.items():', 'L1269 anchor'
assert L(1270) == '                if _fk not in disk:', 'L1270 anchor'
assert L(1287).lstrip().startswith('# hold'), 'L1287 anchor'
assert L(1289) == '            if not isinstance(disk.get(\'hold\'), dict):', 'L1289 anchor'
assert L(1293) == '            elif disk.get(\'hold\'):', 'L1293 anchor'
assert L(1297) == '                    disk[\'hold\'] = _hv', 'L1297 anchor'
assert L(1233) == '                 \'pos_empty_n\': 0}', 'L1233 anchor'

# ---- 自底向上编辑, 保持上方行号有效 ----
# 编辑1: 替换 L1287-1297(hold 专用块, 11行 -> 15行)
new_hold = [
    '            # hold 容器检查(P2-3回退修补 2026-10-19): 必须用循环前抓到的原始值判断——',
    '            # 通用循环会把类型错误的 hold 重置成 {}, 且缺失时 .get() 返回 None, 两者',
    '            # 都会让下面的 isinstance 检查失真。正确语义:',
    '            #   缺失(无此键)=用默认空 dict, 不冻结(账户对账逻辑兜底, 避免假阳性阻止交易);',
    '            #   JSON null / list / str 等类型错误=容器损坏=持仓记录全丢, 冻结开新仓需人工核对;',
    '            #   容器完好但个别记录非 dict=仅摘除坏记录+告警, 不冻结',
    '            if _hold_raw is not _HOLD_MISSING and not isinstance(_hold_raw, dict):',
    '                _bad.append(\'hold(容器损坏, 停止开新仓需人工核对)\')',
    '                disk[\'hold\'] = {}',
    '                G.state_broken = True',
    '            elif isinstance(_hold_raw, dict) and _hold_raw:',
    '                _hv = {_k: _v for _k, _v in _hold_raw.items() if isinstance(_v, dict)}',
    '                if len(_hv) != len(_hold_raw):',
    '                    _bad.append(\'hold(%d条坏记录已摘除)\' % (len(_hold_raw) - len(_hv)))',
    '                    disk[\'hold\'] = _hv',
]
assert len(new_hold) == 15
lines[1286:1297] = new_hold

# 编辑2: L1270 前插入 hold 跳过(通用循环不管 hold)
lines[1269:1269] = [
    '                if _fk == \'hold\':',
    '                    continue      # hold 由下方专用容器检查处理(类型错误=损坏, 非简单重置)',
]

# 编辑3: L1267 后插入原始值抓取
lines[1267:1267] = [
    '            # P2-3回退修补(2026-10-19): 循环前抓 hold 原始值(哨兵区分缺失与 JSON null)',
    '            _hold_raw = disk[\'hold\'] if \'hold\' in disk else _HOLD_MISSING',
]

# 编辑4: _STATE_SCHEMA 后插入哨兵定义
lines[1233:1233] = [
    '_HOLD_MISSING = object()   # P2-3回退修补(2026-10-19): hold缺失哨兵(JSON null=容器损坏需冻结, 缺失=用默认值不冻结)',
]

out = '\r\n'.join(lines)
assert len(lines) == base + 9, 'delta expect +9, got %+d' % (len(lines) - base)
assert out.count('\r\n') == raw.count(b'\r\n') + 9, 'CRLF count mismatch'
assert out.split('\r\n') == lines, 'roundtrip mismatch'
open(p, 'wb').write(out.encode('gbk'))
print('written. base=%d delta=%+d new=%d' % (base, len(lines) - base, len(lines)))
print('P2-3 FIXUP OK')
