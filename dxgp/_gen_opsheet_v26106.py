# -*- coding: utf-8 -*-
"""生成 V2.6.106 手工部署操作单(GBK), 全部按内容定位。"""
import io
import sys

F = 'zt_shrink_strategy_gbk.py'
L = io.open(F, 'r', encoding='gbk', newline='').read().split('\r\n')


def idx(pred, why, lo=0):
    for i in range(lo, len(L)):
        if pred(L[i]):
            return i
    print('!! 找不到: %s' % why)
    sys.exit(1)


def seg(a, b):
    return '\r\n'.join(L[a - 1:b])


i_state = idx(lambda s: s.startswith('SENT_STATE = {}'), 'SENT_STATE')
i_acc_end = idx(lambda s: s.strip().endswith("'rounds': 0, 'pend_rounds': 0}"), '_SENT_ACC 尾')
i_return_md = idx(lambda s: s.strip() == 'return _md', 'return _md')
i_accw = i_return_md - 4
i_abort = idx(lambda s: s.strip().startswith('_abort = False'), '_abort')
i_prep = i_abort - 11
i_cover = idx(lambda s: s.strip() == "SENT_STATE['cover'] = _cov", 'cover')
i_dprep = i_cover - 9
i_rp = idx(lambda s: s.strip().startswith('_ratio_pct = _acc_ratio'), '_ratio_pct')
i_dblk = idx(lambda s: s.strip().startswith('# V2.6.106(方案9): 统计口径改用累积池重算'), '_stats_all 注释头')
i_rows = idx(lambda s: s.strip() == 'rows = []', 'rows=[]', i_dblk)
assert i_rows - i_dblk == 26, 'D 段偏移异常: %d' % (i_rows - i_dblk)
i_apply = idx(lambda s: s.strip() == '_min_cov = SENT_COVERAGE_MIN', '应用侧 _min_cov')
b = i_apply
while L[b].strip() != 'return':
    b += 1
i_apply_end = b
i_tip = idx(lambda s: s.strip().startswith('if _budget_hit and _acc_ratio >= SENT_COVERAGE_MIN:'),
            'budget 提示')
i_warn = idx(lambda s: s.strip().startswith('if _acc_ratio < SENT_COVERAGE_MIN:'), '累积告警')
i_call = idx(lambda s: s.strip().startswith('_md = _sent_fetch_md_batch(C, _batch'), '批量调用行')
assert L[i_call + 1].strip() == '_acc_md)', '续行异常: %r' % L[i_call + 1]
i_boot = -1
for i in range(len(L)):
    if L[i].strip() == "SENT_STATE['acc_pending'] = False":
        for k in range(i + 1, min(i + 12, len(L))):
            if L[k].strip() == "SENT_STATE['rows'] = []":
                i_boot, i_boot_end = i, k
                break
    if i_boot >= 0:
        break
if i_boot < 0:
    sys.exit('!! bootstrap 定位失败')

# 完整性自检
assert L[i_tip + 3].strip().startswith('#   21 '), 'budget 提示段后面异常: %r' % L[i_tip + 3]
assert L[i_warn + 4].strip() == 'return rows', '累积告警段后面异常: %r' % L[i_warn + 4]

out = []
w = out.append

w('V2.6.106 广发交易端手工部署操作单')
w('=' * 78)
w('策略: 涨停缩量低吸 (zt_shrink_strategy_gbk.py)')
w('母版: 12949 行 / 771064 字节 / 参数指纹 8a4ab7e8 (与 V2.6.105 完全一致)')
w('')
w('广发交易端没有"导入"功能, QMT 内部引擎执行的是编辑器里的策略文档, 不读')
w('bin.x64 下的 .py。只能按下面区段在编辑器里逐段替换。')
w('')
w('【铁律】动手前先把编辑器里的原文整段复制到记事本存一份。QMT 无版本管理。')
w('【顺序】必须 0 -> 7 顺序做。第 1 步先加累积池, 后面各步才有 _SENT_ACC 可引用。')
w('【缩进】每段代码缩进已对齐, 粘贴后不要用编辑器自动格式化。')
w('')
w('-' * 78)
w('第 0 步: 升版本号 (改 1 行)')
w('-' * 78)
w("搜索: VERSION = 'V2.6.105'")
w("改成: VERSION = 'V2.6.106'")
w('')
w('-' * 78)
w('第 1 步: 新增累积池 —— 在 "SENT_STATE = {}" 那行下方空一行粘贴')
w('-' * 78)
w('搜索: SENT_STATE = {}')
w('粘贴(共 %d 行, 紧跟 SENT_STATE = {} 那行后面):' % (i_acc_end - i_state - 1))
w('')
w(seg(i_state + 2, i_acc_end + 1))
w('')
w('-' * 78)
w('第 2 步: _sent_fetch_md_batch (3 处)')
w('-' * 78)
w('2-1 搜索函数定义行:')
w('    旧: def _sent_fetch_md_batch(C, codes, fields, start, cnt, box, depth):')
w('    新: def _sent_fetch_md_batch(C, codes, fields, start, cnt, box, depth, acc=None):')
w('')
w('2-2 搜索 "        return _md" (该函数内唯一一处), 在它上面插入 5 行:')
w('')
w(seg(i_accw + 1, i_return_md))
w('')
w('2-3 搜索以 "_out.update(_sent_fetch_md_batch(" 开头的那行递归调用,')
w('    把行尾 "depth + 1))" 改成 "depth + 1, acc))"')
w('')
w('-' * 78)
w('第 3 步: _sent_fetch_sync 主线改累积遍历 (6 处)')
w('-' * 78)
w('3-1 搜索 "_abort = False", 在它上面插入 12 行:')
w('')
w(seg(i_prep + 1, i_abort))
w('')
w('3-2 搜索 "for _i in range(0, len(_stocks), 300):"')
w('    改成 "for _i in range(0, len(_todo), 300):"')
w('')
w('3-3 搜索 "_batch = _stocks[_i:_i + 300]"')
w('    改成 "_batch = _todo[_i:_i + 300]"')
w('')
w('3-4 搜索 "_ok_before = _box[0]" (分批循环内), 紧接其后插入一行:')
w('                _acc_before = len(_acc_md)')
w('')
w('3-5 搜索 "_md = _sent_fetch_md_batch(C, _batch, _fields, _start, _cnt, _box, 0)"')
w('    整行改成两行(第二行 %d 个空格, 对齐到左括号内侧):' % (len(L[i_call + 1]) - len(L[i_call + 1].lstrip(' '))))
w(L[i_call])
w(L[i_call + 1])
w('')
w('3-6 搜索 "_nb_ok += 1" (分批循环内), 在它上面插入一行:')
w('                _acc_new += (len(_acc_md) - _acc_before)')
w('')
w('-' * 78)
w('第 4 步: 收尾改累积口径 (4 处)')
w('-' * 78)
w("4-1 在 \"SENT_STATE['cover'] = _cov\" 这一行上面插入 10 行:")
w('')
w(seg(i_dprep + 1, i_cover))
w('')
w('4-2 搜索 "if not _stats:"')
w('    改成 "if not _stats and _acc_cnt <= 0:"')
w('')
w('4-3 找到含有 "统计口径改用累积池重算" 那段注释的头一行,')
w('    从它开始到 rows = [] 上方为止, 共 %d 行 —— 在 rows = [] 这行【上方】插入:'
  % (i_rows - i_dblk))
w('')
w(seg(i_dblk + 1, i_rows - 1))
w('')
w('    插完后的顺序应该是: [上面这段] -> rows = [] -> for _d in sorted(...)')
w('')
w('4-4 搜索整行:')
w("    _ratio_pct = _cov['ratio'] * 100.0 if _cov['ratio'] is not None else 0.0")
w('  整行替换为 1 行:')
w(seg(i_rp + 1, i_rp + 1))
w('')
w('-' * 78)
w('第 5 步: 应用侧覆盖判定 (_sent_apply_rows)')
w('-' * 78)
w('搜索 "        _min_cov = SENT_COVERAGE_MIN", 从这行开始往下选中到随后的')
w('"            return" 为止 —— 共 %d 行(中间含 if _cov.get(budget_hit) 那三行):'
  % (i_apply_end - i_apply + 1))
w('')
w('    编辑器里这 %d 行的旧内容应该是:' % (i_apply_end - i_apply + 1))
w('')
for _k in range(i_apply, i_apply_end + 1):
    w('    ' + L[_k])
w('')
w('整段删掉, 换成下面 24 行:')
w('')
w(seg(i_apply + 1, i_apply_end + 1))
w('')
w('-' * 78)
w('第 6 步: 取数侧覆盖判定改累积口径 (4 处)')
w('-' * 78)
w('6-1 搜索 "        def _cov_min(_cv, _bh):", 连同后面 5 行一起选中(共 6 行),')
w('    整段删除 —— 累积机制下这个预算特例函数已无意义。')
w('')
w('6-2 搜索 "        _min_cov = _cov_min(_cov, _budget_hit)" —— 整行删除。')
w('')
w('6-3 搜索 "if _budget_hit and _min_cov <= 0.0:", 连同后面 4 行(共 5 行)整段删掉,')
w('    换成下面 3 行:')
w('')
w(seg(i_tip + 1, i_tip + 3))
w('')
w('6-4 搜索 "if _acc_ratio < SENT_COVERAGE_MIN:", 连同后面 4 行(共 5 行)整段删掉,')
w("    旧的那段以 if _cov['ratio'] is not None and _cov['ratio'] < _min_cov: 开头。")
w('    换成下面 4 行:')
w('')
w(seg(i_warn + 1, i_warn + 4))
w('')
w('-' * 78)
w('第 7 步: bootstrap 重置累积池')
w('-' * 78)
w("搜索 SENT_STATE['rows'] = [] 紧接 _SENTIMENT_READY = False 的那一处,")
w('在 SENT_STATE[\'rows\'] = [] 这行【上方】插入 %d 行:' % (i_boot_end - i_boot + 1))
w('')
w(seg(i_boot + 1, i_boot_end))
w('')
w('=' * 78)
w('部署窗口: 收盘后 15:00 之后 (最推荐)')
w('=' * 78)
w('  收盘后 handlebar 完全空转; market_phase() 取 datetime.now() 系统真实钟点')
w('  必为 off_hours; step_day_init() 见 last_init_date==today 直接 return,')
w('  不重下 5226 只日线、不重跑选股 -> 下单风险为零, 且改错有时间改回。')
w('  禁止: 盘中 (market_phase=trading, 会真的调用 run_round 下单)。')
w('')
w('=' * 78)
w('次日开盘验证清单 (09:31 起盯这几行)')
w('=' * 78)
w('[1] [情绪] 内置通道取数完成: 请求5226只 成功17xx只(覆盖率33.x%) ...')
w('[2] [告警] 累积覆盖率不足(33.x% < 90.0%): 本轮不采用, 沿用上一次成功信号, 下一轮继续拼接')
w('[3] 约 6 分钟后 累积到 90% 以上 -> 出现 "信号刷新: 数据日=... sentiment=..."')
w('')
w('对照: 旧版(V2.6.105)全天永远停在 "行情覆盖率仅29.x%(<90%下限)", 一次信号也不出。')
w('新版若 3 轮内(约6分钟)出信号, 说明修复生效。')
w('')
w('若 6 轮后仍不出信号, 看日志里的"本轮新取%d只":')
w('  恒为 0  -> 累积池没生效(第 1 步粘贴失败, 或 _SENT_ACC 被写到函数内部)')
w('  恒定不变 -> 第 3 步 _todo 未改(仍在遍历 _stocks)')
w('=' * 78)

txt = '\r\n'.join(out)
io.open('_部署操作单_V26106.txt', 'w', encoding='gbk', newline='').write(txt)
print('已生成: %d 行 / %d 字符' % (len(out), len(txt)))
print('锚点: acc尾L%d return_md L%d abort L%d cover L%d rp L%d rows L%d apply L%d-%d tip L%d warn L%d boot L%d'
      % (i_acc_end + 1, i_return_md + 1, i_abort + 1, i_cover + 1, i_rp + 1,
         i_rows + 1, i_apply + 1, i_apply_end + 1, i_tip + 1, i_warn + 1, i_boot + 1))
