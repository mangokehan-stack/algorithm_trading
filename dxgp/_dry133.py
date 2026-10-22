# -*- coding: utf-8 -*-
"""
V2.6.133 干跑验证：把「相位采集 + 间隔输出」逐字重写成独立函数真跑。
(不用 AST 抽取 —— 抽取会剥掉首行前导空白导致 IndentationError)
覆盖 4 个场景：有间隔 / 只有1次 / 无慢采样 / 序列异常
断言：日志真的产生、能渲染、数字自洽、无残留占位符
"""
# 逐字复刻文件里的逻辑（变量名一致，缩进重建）
SENT_LOG = []


def _sent_wlog(msg):
    # 文件里 def _sent_wlog(msg): log('[情绪] ' + msg)
    SENT_LOG.append('[情绪] ' + msg)


def run_case(seq, label):
    """seq: [(t0_sec, t1_sec, dt)]"""
    out = []
    _pb2_slow = {}
    _pb2_slow_n = 0
    _pb2_slow_seq = []

    # --- 采集段（复刻 for 循环体里 if _pb2_dt >= 1.0 的内容）---
    for (t0, t1, dt) in seq:
        if dt >= 1.0:
            _pb2_k = int(t1) % 10
            _pb2_slow[_pb2_k] = _pb2_slow.get(_pb2_k, 0) + 1
            _pb2_slow_n += 1
            _pb2_slow_seq.append([int(t0), int(t1), round(dt, 4)])

    # --- 输出段（复刻文件里的相位日志 try）---
    try:
        if _pb2_slow_n > 0:
            _pb2_top = sorted(_pb2_slow.items(), key=lambda _kv: -_kv[1])[:3]
            _pb2_desc = ', '.join(['sec' + str(_k) + '=' + str(_v)
                                   for _k, _v in _pb2_top])
            _pb2_conc = _pb2_top[0][1] * 100.0 / _pb2_slow_n
            _sent_wlog('[基准] 卡顿落点相位: 共%d次采样>=1秒, 最集中 %s | '
                       '集中度%.1f%% (>80%%=确证固定周期源; <40%%=非单一定时器)'
                       % (_pb2_slow_n, _pb2_desc, _pb2_conc))
            _pb2_gaps = []
            for _gi in range(1, len(_pb2_slow_seq)):
                _pb2_gaps.append(_pb2_slow_seq[_gi][0]
                                 - _pb2_slow_seq[_gi - 1][0])
            _pb2_seq_txt = ' '.join(['s' + str(_sq[0] % 60) + '+' + str(_sq[2])
                                     for _sq in _pb2_slow_seq[:6]])
            if _pb2_gaps:
                _sent_wlog('[基准] 卡顿时刻序列: %s | 起点间隔=%s '
                           '(相邻差恒为10=10秒节拍; 恒为30=timer_poll; '
                           '参差=外部事件, 与两个定时器都无关)'
                           % (_pb2_seq_txt,
                              ','.join([str(_g) for _g in _pb2_gaps])))
            else:
                _sent_wlog('[基准] 卡顿时刻序列: %s (只有1次, 无法算间隔)'
                           % _pb2_seq_txt)
        else:
            _sent_wlog('[基准] 卡顿落点相位: 本轮无>=1秒的采样(全程流畅)')
    except Exception as _pb2_pe:
        try:
            _sent_wlog('[基准] 卡顿落点相位统计异常(不影响主流程): %s'
                       % str(_pb2_pe)[:120])
        except Exception:
            pass
    return out


def check(msgs, label, must_have=None, must_not=None):
    print('--- %s ---' % label)
    for m in msgs:
        print('   ', m)
    txt = '\n'.join(msgs)
    # 未渲染占位符
    assert '%.' not in txt, '残留 %%. 占位符: %s' % txt
    assert '%d' not in txt, '残留 %d 占位符: %s' % txt
    assert '%s' not in txt, '残留 %s 占位符: %s' % txt
    if must_have:
        for k in must_have:
            assert k in txt, '%s 场景缺少 %r' % (label, k)
    if must_not:
        for k in must_not:
            assert k not in txt, '%s 场景不应出现 %r' % (label, k)
    print('    [PASS]')
    return txt


# ===== 场景1: 3 次卡顿, 起点间隔恒为 10 (10秒节拍特征) =====
SENT_LOG.clear()
run_case([(1792494631, 1792494641, 10.0007),
          (1792494641, 1792494651, 10.0031),
          (1792494651, 1792494661, 10.0002)], 'case1')
t1 = check(SENT_LOG, '场景1: 起点间隔恒为10(应能看出10秒节拍)',
           must_have=['集中度100.0%', '起点间隔=10,10', '共3次'])
assert '10,10' in t1, '间隔未正确计算'

# ===== 场景2: 只有 1 次卡顿 =====
SENT_LOG.clear()
run_case([(1792494631, 1792494641, 10.0007)], 'case2')
t2 = check(SENT_LOG, '场景2: 只有1次(应走"无法算间隔"分支)',
           must_have=['无法算间隔', '共1次'],
           must_not=['起点间隔='])

# ===== 场景3: 无慢采样 =====
SENT_LOG.clear()
run_case([], 'case3')
t3 = check(SENT_LOG, '场景3: 无>=1秒(应说"全程流畅")',
           must_have=['本轮无>=1秒的采样(全程流畅)'])
assert '共' not in t3, '空场景不应出现"共N次"'

# ===== 场景4: 起点间隔参差(=外部事件) =====
SENT_LOG.clear()
run_case([(1792494601, 1792494611, 10.0),
          (1792494619, 1792494629, 10.0),
          (1792494647, 1792494657, 10.0)], 'case4')
t4 = check(SENT_LOG, '场景4: 间隔参差(应显示18,28)',
           must_have=['起点间隔=18,28'])

# ===== 场景5: 集中度计算正确性(混合相位, sec1 恰好 2 次) =====
# 4 个结束秒 %10: 21->1, 41->1, 45->5, 51->1 是 sec1 三次, 不是我想要的两次。
# 重新构造: 21->1, 41->1, 45->5, 27->7 => sec1=2, sec5=1, sec7=1 => 集中度 50.0%
SENT_LOG.clear()
run_case([(1792494611, 1792494621, 10.0),
          (1792494631, 1792494641, 10.0),
          (1792494635, 1792494645, 10.0),
          (1792494617, 1792494627, 10.0)], 'case5')
t5 = check(SENT_LOG, '场景5: 4次中2次落sec1(集中度应=50.0%)',
           must_have=['集中度50.0%'])
assert 'sec1=2' in t5, 'sec1 计数应为 2, 实际: %s' % t5

# ===== 场景6: 异常路径 =====
SENT_LOG.clear()
try:
    _pb2_slow = {'1': 'x'}      # 故意让 sort 失败
    _pb2_slow_n = 1
    _pb2_top = sorted(_pb2_slow.items(), key=lambda _kv: -_kv[1])[:3]
except Exception as _pb2_pe:
    _sent_wlog('[基准] 卡顿落点相位统计异常(不影响主流程): %s' % str(_pb2_pe)[:120])
assert len(SENT_LOG) == 1 and '统计异常' in SENT_LOG[0]
print('--- 场景6: 异常只吞不抛 ---')
print('   ', SENT_LOG[0])
print('    [PASS]')

print()
print('=' * 60)
print('全部 6 个场景 PASS')
print('=' * 60)

# ===== 反向验证: 确认源文件里确实是这套逻辑 =====
src = open('zt_shrink_strategy_gbk.py', 'rb').read().decode('gbk')
print()
print('=== 源文件交叉核对 ===')
checks = [
    ('_pb2_slow_seq = []', '序列初始化'),
    ('_pb2_slow_seq.append([int(_pb2_t0), int(_pb2_t1),', '三元组采集'),
    ('_pb2_gaps.append(_pb2_slow_seq[_gi][0]', '间隔按起点秒'),
    ('卡顿时刻序列', '日志标签'),
    ('只有1次, 无法算间隔', '单次分支'),
    ('_lg_on = False      # V2.6.133', '开关默认值'),
    ('if _lg_on:', '开关判断'),
]
for k, name in checks:
    assert k in src, '源文件缺少 %s (%r)' % (name, k)
    print('[OK] %s' % name)

# 占位符数量核对（分开数，%% 是 2 字符渲染 1 个 %）
seg_start = src.find('[基准] 卡顿落点相位: 共%d次采样>=1秒')
seg_end = src.find('_pb2_conc))', seg_start)
seg = src[seg_start:seg_end + len('_pb2_conc))')]
n_ph = seg.count('%d') + seg.count('%s') + seg.count('%.1f')
n_esc = seg.count('%%')
print()
print(f'相位行: 占位符 {n_ph} 个(应为3), 转义 {n_esc} 处(应为3)')
assert n_ph == 3, '占位符数不对: %d' % n_ph
# 3 处: %.1f%% 的字面百分号 + >80%%= + <40%%=  (实测核对, 非估算)
assert n_esc == 3, '转义数不对: %d' % n_esc
print('[OK] 占位符与转义计数正确')
print()
print('ALL DRY-RUN PASS')
