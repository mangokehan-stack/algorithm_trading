# -*- coding: utf-8 -*-
"""V2.6.107: 退避判定改为"看累积是否有进展" —— 供 V2.6.106 累积机制生效。

病因: V2.6.106 让取数跨轮累积, 但调度侧 V2.6.99 的退避仍只看 _budget_hit。
      双实例下每轮必然 budget_hit -> bh_streak 第2轮起就 >=2 -> 退避1800秒。
      累积要4轮才拼满, 30分钟一轮 = 2小时, 一天只有4小时, 盘中还要清零重拼。
      实测日志(V2.6.100): 7轮取数横跨 2.5 小时, 覆盖率 23%~63% 从未达标。
改法: bh_streak 只在"累积覆盖没有实质进展"时才累加; 有进展就清零, 保持300秒节奏。
      "预算命中"不等于"取不动" —— 它只说明没取完, 而累积正在推进。

全部为函数内局部量 / 已有 SENT_STATE 键, 不新增模块级大写常量(参数指纹不变)。
"""
import io
import sys

F = 'zt_shrink_strategy_gbk.py'
L = io.open(F, 'r', encoding='gbk', newline='').read().split('\r\n')
ORIG = list(L)


def find(pred, why, lo=0):
    for i in range(lo, len(L)):
        if pred(L[i]):
            return i
    sys.exit('!! 找不到: %s' % why)


# ---------- 锚点 ----------
i_ver = find(lambda s: s.startswith("VERSION = 'V2.6.106'"), 'VERSION')
i_old = find(lambda s: s.strip().startswith(
    "SENT_STATE['bh_streak'] = (int(SENT_STATE.get('bh_streak') or 0) + 1)"), 'bh_streak 赋值')
assert L[i_old - 2].strip().startswith('# V2.6.99(1)'), 'L[-2] 异常: %r' % L[i_old - 2]
assert L[i_old - 1].strip().startswith('#   300->1800秒'), 'L[-1] 异常: %r' % L[i_old - 1]

i_cover = find(lambda s: s.strip() == "SENT_STATE['cover'] = _cov", 'cover 赋值', i_old)
assert i_cover - i_old == 11, '累积块偏移异常: %d' % (i_cover - i_old)
assert L[i_old + 4].strip() == "_acc_cnt = len(_acc_md)", 'L[+4] 异常: %r' % L[i_old + 4]

i_sched = find(lambda s: s.strip().startswith(
    '_bh_streak = int(SENT_STATE.get('), '调度侧 _bh_streak')
i_retry = find(lambda s: s.strip().startswith('_retry_sec = 1800.0 if _bh_streak'), '调度侧 _retry_sec')
assert i_retry == i_sched + 1, '调度侧间距异常: %d' % (i_retry - i_sched)

# ---------- 改动 1: 删除旧 bh_streak 赋值(+2行注释) ----------
rep1 = [
    '        # V2.6.107: 连续预算命中的退避计数改到累积口径 —— 见下方"累积收尾"块。',
    '        #   旧版在此处直接 +1, 但双实例下每轮必然 budget_hit, 第2轮起就退避1800秒,',
    '        #   把 V2.6.106 的跨轮累积(需4轮)拖成2小时, 盘中清零后当天根本拼不满。',
]
L[i_old - 2:i_old + 1] = rep1

# ---------- 改动 2: 累积块里加"有进展就不退避" ----------
i_cover2 = [i for i, s in enumerate(L)
            if s.strip() == "SENT_STATE['cover'] = _cov"][0]
ins = [
    '        # V2.6.107: 退避判定改看"累积是否在推进", 不再只看本轮是否被预算截断。',
    '        #   判据: 累积覆盖率较上一轮增长 >= 2 个百分点(约 105 只), 视为有实质进展 ->',
    '        #   bh_streak 清零, 调度侧保持 300 秒节奏继续拼; 增长不足 2 个百分点(真的是',
    '        #   取不动了)才累加 -> 退避 1800 秒让路。',
    '        #   为什么不是"没命中预算才清零": 双实例下几乎每轮都会命中预算, 那样等于永不',
    '        #   清零。预算命中只说明"本轮没取完", 与"接口取不动"是两件事。',
    '        _acc_prev = SENT_STATE.get(\'acc_ratio_prev\')',
    '        try:',
    '            _acc_prev = float(_acc_prev) if _acc_prev is not None else -1.0',
    '        except Exception:',
    '            _acc_prev = -1.0',
    '        _acc_gain = _acc_ratio - _acc_prev if _acc_prev >= 0.0 else 1.0',
    '        SENT_STATE[\'acc_ratio_prev\'] = _acc_ratio',
    '        if _acc_gain >= 0.02:',
    '            SENT_STATE[\'bh_streak\'] = 0      # 有实质进展: 不退避, 下一轮300秒后继续',
    '        elif _budget_hit:',
    '            SENT_STATE[\'bh_streak\'] = int(SENT_STATE.get(\'bh_streak\') or 0) + 1',
    '        else:',
    '            SENT_STATE[\'bh_streak\'] = 0      # 本轮完整取完, 无需退避',
]
L[i_cover2:i_cover2] = ins

# ---------- 改动 3: 调度侧退避文案与新口径一致 ----------
i_sched2 = [i for i, s in enumerate(L)
            if s.strip().startswith('_bh_streak = int(SENT_STATE.get(')][0]
assert L[i_sched2 - 3].strip().startswith('# V2.6.99(1)'), '调度段注释异常: %r' % L[i_sched2 - 3]
L[i_sched2 - 3:i_sched2] = [
    '        # V2.6.99(1) 建此退避, V2.6.107 改判据: 只有"累积覆盖不再推进"才退避。',
    '        #   旧判据看本轮是否 budget_hit, 双实例下每轮都命中 -> 永远退避 1800 秒,',
    '        #   与 V2.6.106 的跨轮累积冲突(累积需 4 轮, 30 分钟一轮 = 2 小时才拼满)。',
    '        #   新判据由取数侧写入: 累积增长 >= 2 个百分点即清零, 保持 300 秒节奏。',
]

# ---------- 改动 4: VERSION ----------
L[i_ver] = L[i_ver].replace("V2.6.106", "V2.6.107")

txt = '\r\n'.join(L)
io.open(F, 'w', encoding='gbk', newline='').write(txt)

print('行数: %d -> %d' % (len(ORIG), len(L)))
print('VERSION 行: %s' % L[i_ver][:60])
print('已写入 %s' % F)
