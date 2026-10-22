# -*- coding: utf-8 -*-
"""P2 第一批补丁: P2-9 / P2-8 / P2-12 / P2-6
GBK 安全编辑法: encoding='gbk', newline='' + split/join('\r\n')
"""
import sys

P = 'zt_shrink_strategy_gbk.py'
raw = open(P, encoding='gbk', newline='').read()
lines = raw.split('\r\n')
assert len(lines) == 11089, 'unexpected line count: %d' % len(lines)

# ================= P2-9: _is_bar_fresh 三处 return 加 0<= 下界 =================
# 原: return (now - ts) <= float(tolerance_sec)
# 问题: ts 为未来时间戳(时钟偏差/脏数据)时 now-ts<0, 旧逻辑判"新鲜"返回 True,
#       未来 bar 会被当成最新数据参与决策
T9 = '            return (now - ts) <= float(tolerance_sec)'
hits9 = [i for i, ln in enumerate(lines) if ln == T9]
assert len(hits9) == 3, 'P2-9 anchor hits=%r' % hits9
for i in hits9:
    lines[i] = '            return 0 <= (now - ts) <= float(tolerance_sec)'
print('P2-9 ok: 3 returns patched at', [h + 1 for h in hits9])

# ================= P2-8: _bars_to_dict int64/epoch 键转换 =================
i_sk = None
for i, ln in enumerate(lines):
    if ln == '                _sk = str(k)' and lines[i + 1] == '                _dk = _sk[:8]':
        i_sk = i
        break
assert i_sk is not None, 'P2-8 anchor _sk not found'
i_dk = i_sk + 1
assert lines[i_dk] == '                _dk = _sk[:8]'
lines[i_dk:i_dk + 1] = [
    '                # P2-8修复(2026-10-19): 先剥离浮点尾巴(20261013.0->20261013),',
    '                # 避免 numpy float64 索引被误判为 9 位 epoch 数字',
    "                if _sk.endswith('.0') and _sk[:-2].isdigit():",
    '                    _sk = _sk[:-2]',
    '                _dk = _sk[:8]',
]
# 找 '-' 分支体, 在其后插入 elif epoch 分支(原行为对 8 位 YYYYMMDD 数字键不变)
i_elif = None
for i in range(i_dk, i_dk + 25):
    if lines[i] == "                    _dk = _sk[:10].replace('-', '')" and lines[i + 1] == '                out[_dk] = v':
        i_elif = i
        break
assert i_elif is not None, 'P2-8 anchor elif not found'
lines[i_elif + 1:i_elif + 2] = [
    '                elif _sk.isdigit() and len(_sk) >= 9:',
    '                    # P2-8修复(2026-10-19): numpy int64/float64 索引或 epoch 键(如',
    '                    # 1791860100 秒 / 1791860100000 毫秒) str() 后为 9 位以上纯数字,',
    '                    # 原 [:8] 会产出 "17918601" 之类垃圾日期, 该 bar 与 G.today 永不',
    '                    # 匹配导致 K 线静默失效; 纯数字且长度>=9 一律按 epoch 换算为',
    "                    # YYYYMMDD(8 位 YYYYMMDD 数字键走上一分支, 行为不变)",
    '                    _ts = int(_sk)',
    '                    if _ts > 1e12:',
    '                        _ts = _ts // 1000',
    '                    if _ts > 0:',
    "                        _dk = datetime.datetime.fromtimestamp(_ts).strftime('%Y%m%d')",
]
print('P2-8 ok: epoch branch inserted after L%d' % (i_elif + 1))

# ================= P2-12: market_tide_check 剔除当日未走完 K 线 =================
i_tide = None
for i, ln in enumerate(lines):
    if ln.startswith('        bars = _bars_to_dict(d.get(MARKET_TIDE_INDEX)'):
        i_tide = i
        break
assert i_tide is not None, 'P2-12 anchor not found'
assert lines[i_tide + 1].startswith('        _cal = getattr(G,')
lines[i_tide + 1:i_tide + 1] = [
    '        # P2-12修复(2026-10-19): 剔除当日未走完的 K 线再算退潮 —— 盘中当日 K 线是',
    '        # 未完成的, 把它混入退潮计算等于用半个交易日的涨跌幅做判断; 且本函数结果按',
    '        # G.today 全天缓存(首算即定全天), 更必须用已完成交易日口径(退潮是慢变量,',
    '        # 不差当日这一天; 这样盘中首算与收盘后口径一致, 不会日内反复翻转)',
    '        if bars:',
    "            bars = {_k: _v for _k, _v in bars.items() if str(_k)[:8] != G.today}",
]
print('P2-12 ok: today-bar filter inserted at L%d' % (i_tide + 2))

# ================= P2-6: SENT_REGIME_PANIC_LO -1.5 -> -1.0 (regime/gate 分层) =================
i_panic = None
for i, ln in enumerate(lines):
    if ln.startswith('SENT_REGIME_PANIC_LO = -1.5'):
        i_panic = i
        break
assert i_panic is not None, 'P2-6 anchor not found'
lines[i_panic] = 'SENT_REGIME_PANIC_LO = -1.0              # P2-6修复(2026-10-19): 原值-1.5与L1闸门'
lines[i_panic + 1:i_panic + 1] = [
    ' ' * 41 + '# gate_panic_th(-1.5)同阈值, L1闸门(停新买)先触发, 导致[-1.5,-1.0)区间',
    ' ' * 41 + '# L3恐慌覆写(SHRINK_BUY_RATIO=0.30/等待45分钟)永无效果; 改为-1.0形成',
    ' ' * 41 + '# "regime内层-1.0/gate外层-1.5"分层, 与暴涨侧(regime+1.5/gate+1.8)',
    ' ' * 41 + '# 分层对称; gate阈值不动, 极端恐慌停新买的保护不削弱',
]
print('P2-6 ok: SENT_REGIME_PANIC_LO patched at L%d' % (i_panic + 1))

# 写回前先自查行数增量: P2-9 1:1换3行(+0); P2-8 两处插入(+4/+10); P2-12 插6行(+6); P2-6 插4行(+4)
assert len(lines) == 11089 + 24, 'line delta mismatch: %d' % len(lines)
out = '\r\n'.join(lines)
assert out.count('\r\n') == raw.count('\r\n') + 24, 'crlf count mismatch'
open(P, 'w', encoding='gbk', newline='').write(out)
print('written. new line count:', len(lines))
print('ALL P2-BATCH-A OK')
