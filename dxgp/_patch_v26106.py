# -*- coding: utf-8 -*-
"""V2.6.106 patch: 情绪取数跨轮累积 (方案 9)

定位: 纯 ASCII 行首锚, 避开 GBK 中文注释手抄不准。
写入: 全程 io.open(encoding='gbk', newline=''), 绝不经过 Edit 类工具(会破坏 GBK 字节)。
"""
import io
import sys

F = 'zt_shrink_strategy_gbk.py'

with io.open(F, 'r', encoding='gbk', newline='') as fh:
    raw = fh.read()

L = raw.split('\r\n')
print('原始行数 %d' % len(L))
n_ops = 0


def find_one(pred, why, lo=0):
    hits = [i for i in range(lo, len(L)) if pred(L[i])]
    if len(hits) != 1:
        print('!! 锚点 "%s" 命中 %d 次(需 1): %s'
              % (why, len(hits), [L[h][:70] for h in hits[:4]]))
        sys.exit(1)
    return hits[0]


def ins_at(idx, lines, why):
    global n_ops
    L[idx:idx] = lines
    n_ops += 1
    print('  [%s] 插入 %d 行 @ L%d' % (why, len(lines), idx + 1))


def rep_line(idx, new, why):
    global n_ops
    n_ops += 1
    print('  [%s] 替换 L%d: %s' % (why, idx + 1, new.strip()[:72]))
    L[idx] = new


# ============================================================ A. 累积容器
i = find_one(lambda s: s.startswith('SENT_STATE = {}'), 'A SENT_STATE')
ins_at(i + 1, [
    '',
    '# V2.6.106(方案9): 情绪取数跨轮累积容器。',
    '#   病因(V2.6.103~105 三版都没治好): 110 秒预算在 17~21 秒/批的实盘速度下只能跑',
    '#   5~6 批 = 1500~1800 只, 覆盖 29%~34%。_cov_min() 在预算截断时要求的',
    '#   "零失败且已取>=480只"本身是能满足的; 真正卡死的是 SENT_COVERAGE_MIN=0.90 ——',
    '#   ratio 用的是"本轮取到 / 全市场", 单轮永远够不到 90%, 于是一直走',
    '#   _sent_use_last_good() 沿用上一次成功信号, 情绪被冻结。',
    '#   解法: 把"一次取全"改成"多轮拼全"。每轮只从还没取过的标的里继续取,',
    '#   已有数据直接复用不再调接口; 累积覆盖达到 SENT_COVERAGE_MIN 才出信号,',
    '#   否则挂起等下一轮。累积全天连续: 第一轮 34% + 第二轮 +34% = 68% + 第三轮 -> 100%。',
    '#   用**小写**模块级 dict, 不新增 UPPER_CASE 常量 —— 否则 _fp_keys() 会把它收进',
    '#   参数指纹, 使 verified_fp 失效(项目铁律)。',
    "_SENT_ACC = {'date': '', 'md': {}, 'ok': 0, 'fail': 0, 'retry': 0,",
    "             'rounds': 0, 'pend_rounds': 0}",
], 'A 累积容器')

# ==================================================== B. 分批取数支持 acc
i = find_one(lambda s: s.startswith('def _sent_fetch_md_batch('), 'B 签名')
rep_line(i, 'def _sent_fetch_md_batch(C, codes, fields, start, cnt, box, depth, acc=None):', 'B 签名')

i = find_one(lambda s: s.strip() == 'return _md', 'B return _md')
ins_at(i, [
    '        # V2.6.106: 整批一次成功 -> 直接并入累积容器(acc); 空 DataFrame 不算取到。',
    '        if acc is not None and _n > 0:',
    '            for _c in codes:',
    '                if _md.get(_c) is not None:',
    '                    acc[_c] = _md[_c]',
], 'B 累积写入')

k = find_one(lambda s: s.strip().endswith('start, cnt, box, depth + 1))'), 'B 递归', i)
rep_line(k, L[k].replace('depth + 1))', 'depth + 1, acc))'), 'B 递归透传')

# ================================================ C. 轮内累积: 跳过已取
i = find_one(lambda s: s.strip() == "'ratio': None, 'samples': [], 'fields_all': False}",
             'C _cov 定义')
ins_at(i + 1, [
    "        # V2.6.106(方案9): 跨轮累积准备",
    "        #   _acc_md  : 累积池(当天已取到的 {code: raw}), 每轮只增不减",
    "        #   _acc_cnt : 本轮开始前已累积到的只数",
    "        #   _todo    : 本轮真正要取的 = 全市场 - 已累积(已取到的绝不再调接口)",
    "        if _SENT_ACC.get('date') != str(getattr(G, 'today', '') or ''):",
    "            _SENT_ACC.update({'date': str(getattr(G, 'today', '') or ''),",
    "                              'md': {}, 'ok': 0, 'fail': 0, 'retry': 0,",
    "                              'rounds': 0, 'pend_rounds': 0})",
    "        _acc_md = _SENT_ACC['md']",
    "        _acc_cnt = len(_acc_md)",
    "        _todo = [_c for _c in _stocks if _c not in _acc_md]",
    "        _acc_new = 0",
], 'C 累积准备')

i = find_one(lambda s: s.strip() == 'for _i in range(0, len(_stocks), 300):', 'C 遍历')
rep_line(i, L[i].replace('len(_stocks)', 'len(_todo)'), 'C 遍历改 todo')

i = find_one(lambda s: s.strip() == '_batch = _stocks[_i:_i + 300]', 'C _batch')
L[i] = L[i].replace('_stocks[_i:_i + 300]', '_todo[_i:_i + 300]')
print('  [C 批次切片] 替换 L%d' % (i + 1))

i = find_one(lambda s: s.strip().startswith('_md = _sent_fetch_md_batch(C, _batch,'), 'C 调用')
_ind = ' ' * (len(L[i]) - len(L[i].lstrip()) + 11)
L[i] = L[i].rstrip()
L[i] = L[i][:-1] + ','          # 去掉右括号, 换行续写
L.insert(i + 1, _ind + '_acc_md)')
n_ops += 1
print('  [C 传 acc] 替换 L%d 并续行' % (i + 1))

i = find_one(lambda s: s.strip() == '_ok_before = _box[0]', 'C ok_before')
ins_at(i + 1, ['                _acc_before = len(_acc_md)'], 'C acc_before')

i = find_one(lambda s: s.strip() == '_nb_ok += 1', 'C nb_ok', i)
ins_at(i, ['                _acc_new += (len(_acc_md) - _acc_before)'], 'C 新增计数')

# =============================================== D. 收尾: 累积口径 + 挂起
i = find_one(lambda s: s.strip() == "SENT_STATE['cover'] = _cov", 'D cover 落盘')
ins_at(i, [
    "        # ---- V2.6.106(方案9) 累积收尾: 覆盖口径从'本轮/全市场'改为'累积/全市场' ----",
    "        #   旧口径下预算截断必然 ratio < 0.90, 于是每轮都 _sent_use_last_good(),",
    "        #   信号永久冻结。新口径下只要'跨轮累积'够 90% 就出信号, 单轮只往前推一截。",
    "        _acc_cnt = len(_acc_md)",
    "        _acc_ratio = (float(_acc_cnt) / float(len(_stocks))) if _stocks else 0.0",
    "        _cov['round_ok'] = int(_cov['ok'])      # 本轮新取到(保留原值, 供日志对照)",
    "        _cov['acc_ok'] = int(_acc_cnt)          # 全天累积到手",
    "        _cov['acc_ratio'] = _acc_ratio",
    "        _cov['rounds'] = int(_SENT_ACC.get('rounds') or 0) + 1",
    "        _SENT_ACC['rounds'] = _cov['rounds']",
], 'D 累积口径')

i = find_one(lambda s: s.strip() == "if not _stats:", 'D 空数据判定')
L[i] = L[i].replace('if not _stats:', 'if not _stats and _acc_cnt <= 0:')
print('  [D 空数据判定] 替换 L%d' % (i + 1))

# rows 组装改为用累积池重算统计(分母恒定)
i2 = find_one(lambda s: s.strip().startswith('# 3) ') and 'rows' in s, 'D rows 注释')
j = i2 + 1
assert L[j].strip() == 'rows = []', 'D rows=[] 定位失败: %r' % L[j]
print('  [D rows=[]] 确认 @ L%d' % (j + 1))
ins_at(j, [
    "        # V2.6.106(方案9): 统计口径改用累积池重算。",
    "        #   本轮只取了一部分标的, 若用本轮 _stats 组装, advance/decline/limit_up 的",
    "        #   **分母**每轮都不同(同一交易日两次信号指标不一致), 比'冻结'更坏。",
    "        #   改为用累积到手的全部标的重算一次, 分母随累积增长但口径统一。",
    "        _stats_all = {}",
    "        for _s3, _raw3 in _acc_md.items():",
    "            _th3 = _lu_th(_s3)",
    "            for _d3, _row3 in _bars_to_dict(_raw3).items():",
    "                if _d3 < _start:",
    "                    continue",
    "                _c3 = _f((_row3 or {}).get('close'))",
    "                _p3 = _f((_row3 or {}).get('preClose'))",
    "                if _c3 <= 0 or _p3 <= 0:",
    "                    continue",
    "                _pct3 = _c3 / _p3 - 1.0",
    "                _st3 = _stats_all.get(_d3)",
    "                if _st3 is None:",
    "                    _st3 = _stats_all[_d3] = [0, 0, 0]",
    "                if _pct3 > 0:",
    "                    _st3[0] += 1",
    "                elif _pct3 < 0:",
    "                    _st3[1] += 1",
    "                if _pct3 >= _th3:",
    "                    _st3[2] += 1",
    "        if _stats_all:",
    "            _stats = _stats_all",
], 'D 累积重算统计')

i = find_one(lambda s: s.strip().startswith("_ratio_pct = _cov['ratio']"), 'D 覆盖率展示')
L[i] = ("        _ratio_pct = _acc_ratio * 100.0"
        "      # V2.6.106: 展示累积覆盖率(原为本轮覆盖率)")
print('  [D 覆盖率展示] 替换 L%d' % (i + 1))

with io.open(F, 'w', encoding='gbk', newline='') as fh:
    fh.write('\r\n'.join(L))
print()
print('阶段 A/B/C/D 完成, %d 处编辑, 新行数 %d' % (n_ops, len(L)))
