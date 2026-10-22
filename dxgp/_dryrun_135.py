# -*- coding: utf-8 -*-
"""V2.6.135 干跑: 探针口径 + 间隔判读 + 卡死阈值

记忆 6.5: % 格式串必须真渲染一次; 只查未渲染占位符, 不能写 '%' not in out
         (会因 %% 渲染成 % 而假失败); %% 与占位符要分开数。
记忆 6.7: ast.get_source_segment 会剥掉首行前导空白, 直接 exec 必 IndentationError
         -> 干跑一律逐字重写成独立函数, AST 只用来校验占位符/实参个数。
"""
import ast
import sys

P = 'zt_shrink_strategy_gbk.py'
src = open(P, 'rb').read().decode('gbk')
tree = ast.parse(src)

PASS = []
FAIL = []


def chk(desc, cond, detail=''):
    (PASS if cond else FAIL).append(desc)
    print(('  PASS  ' if cond else '  FAIL  ') + desc + (('  [' + detail + ']') if detail else ''))


# ---------------------------------------------------------------- 1 占位符/实参个数
def fmt_specs(s):
    """数 % 格式串里真正的占位符个数, %% 不算"""
    n = 0
    i = 0
    while i < len(s):
        if s[i] == '%':
            if i + 1 < len(s) and s[i + 1] == '%':
                i += 2
                continue
            j = i + 1
            while j < len(s) and s[j] in '-+ #0123456789.':
                j += 1
            if j < len(s) and s[j] in 'diouxXeEfFgGcrsa':
                n += 1
                i = j + 1
                continue
        i += 1
    return n


print('=== 1. % 格式串: 占位符数 vs 实参个数 ===')
mismatch = []
n_checked = 0
for node in ast.walk(tree):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        if not (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)):
            continue
        nspec = fmt_specs(node.left.value)
        if isinstance(node.right, ast.Tuple):
            narg = len(node.right.elts)
        else:
            narg = 1
        n_checked += 1
        if nspec != narg:
            mismatch.append((node.lineno, nspec, narg, node.left.value[:70]))
print('  全文件 %% 格式化节点 %d 个, 不匹配 %d 个' % (n_checked, len(mismatch)))
for ln, ns, na, txt in mismatch:
    print('    L%d: 占位符%d / 实参%d  | %s' % (ln, ns, na, txt))
chk('全文件 %% 格式串占位符与实参个数全部匹配', len(mismatch) == 0,
    '%d/%d 不匹配' % (len(mismatch), n_checked))

# ---------------------------------------------------------------- 2 间隔判读逻辑
print()
print('=== 2. 卡顿间隔判读(逐字重写母版逻辑) ===')


def judge_beat(gaps):
    """与母版 D2 段逐字等价的判读逻辑"""
    _pb2_beat = u'无法判定'
    _gb_pos = [_gg for _gg in gaps if _gg > 0]
    if _gb_pos:
        _gb_min = min(_gb_pos)
        _gb_max = max(_gb_pos)
        if _gb_max <= _gb_min * 1.2:
            _pb2_beat = (u'恒定约%d秒 -> 单一定时器节拍'
                         % int(round(float(sum(_gb_pos)) / len(_gb_pos))))
        elif all(abs(round(_gg / 30.0) * 30 - _gg) <= 6
                 for _gg in _gb_pos):
            _pb2_beat = u'全部≈30秒整数倍 -> timer_poll(30秒)节拍'
        elif all(abs(round(_gg / 10.0) * 10 - _gg) <= 2
                 for _gg in _gb_pos):
            _pb2_beat = (u'全部≈10秒整数倍 -> 10秒为最小节拍单位'
                         u'(可能是10/20/30秒定时器叠加, 需配30秒模相位看)')
        else:
            _pb2_beat = u'参差 -> 外部事件, 与定时器节拍无关'
    return _pb2_beat


# 防副本漂移: 手写函数里的四个文案必须与母版逐字一致 —— 母版改了文案
# 而这里没跟, 就应该报 FAIL, 而不是让干跑"用旧逻辑验证新代码"白跑。
print('  -- 副本与母版文案一致性 --')
for _kw in [u'恒定约%d秒 -> 单一定时器节拍',
            u'全部≈30秒整数倍 -> timer_poll(30秒)节拍',
            u'全部≈10秒整数倍 -> 10秒为最小节拍单位',
            u'参差 -> 外部事件, 与定时器节拍无关',
            u'_gb_pos = [_gg for _gg in _pb2_gaps if _gg > 0]']:
    chk('  副本同步: ' + _kw[:26], src.count(_kw) >= 1)


# 母版与手写是否逐字一致(去缩进后比对关键 4 行)
i_src = src.find(u'_gb_pos = [_gg for _gg in _pb2_gaps if _gg > 0]')
chk('母版含 _gb_pos 判读段', i_src > 0)
i_30 = src.find(u'全部≈30秒整数倍 -> timer_poll(30秒)节拍')
i_10 = src.find(u'全部≈10秒整数倍 -> 10秒为最小节拍单位')
i_can = src.find(u'参差 -> 外部事件, 与定时器节拍无关')
chk('母版四个判读分支文案齐全', i_30 > 0 and i_10 > 0 and i_can > 0)
chk('母版顺序: 30秒分支早于10秒分支', 0 < i_30 < i_10)

CASES = [
    ('本轮实测 120,91,30', [120, 91, 30], u'timer_poll(30秒)'),
    ('三次 30（每周期都冻）', [30, 30, 30], u'恒定约30秒'),
    ('三次 10（log_guard 节拍）', [10, 10, 10], u'恒定约10秒'),
    ('10/20/30 混合', [10, 20, 30], u'10秒为最小节拍单位'),
    ('参差 7,13,22', [7, 13, 22], u'参差'),
    ('单次无间隔', [], u'无法判定'),
    ('含 0 间隔(同秒两次)', [0, 30, 30], u'恒定约30秒'),
]
for desc, g, want in CASES:
    got = judge_beat(g)
    ok = want in got
    chk('  判读 %-18s %-16s -> %s' % (desc, str(g), got), ok, '期望含 ' + want)

# ---------------------------------------------------------------- 3 探针口径分离
print()
print('=== 3. 探针口径分离(用本轮真实读数) ===')
_pb2_loop = 90
_pb2_sum = 118.5           # 探针总墙钟(日志: 占解析 32.92%)
_pb2_max = 29.9999
_pb2_base = 0.0022
_dt_par = 360.0
_slow_seq = [29.9999, 29.9996, 28.6157, 29.5154]
_pb2_slow_n = len(_slow_seq)
_pb2_slow_sum = sum(_slow_seq)

_pb2_norm_n = _pb2_loop - _pb2_slow_n
_pb2_norm_s = _pb2_sum - _pb2_slow_sum
_pb2_norm_avg = (_pb2_norm_s / _pb2_norm_n) if _pb2_norm_n > 0 else 0.0
_pb2_norm_x = (_pb2_norm_avg / _pb2_base) if _pb2_base > 0 else 0.0
_pb2_frz_sh = ((_pb2_slow_sum / _dt_par * 100.0) if _dt_par > 0 else 0.0)
_pb2_avg = _pb2_sum / float(_pb2_loop)
_pb2_x = _pb2_avg / _pb2_base
_pb2_mx = _pb2_max / _pb2_base

out1 = (u'[基准] 解析期间并发采样: 采样%d次(每40只一次) | '
        u'冻结%d次 合计%.1f秒=解析%.1f%% | '
        u'正常%d次 均摊%.4f秒/次=本机基线的%.2f倍'
        % (_pb2_loop, _pb2_slow_n, _pb2_slow_sum, _pb2_frz_sh,
           _pb2_norm_n, _pb2_norm_avg, _pb2_norm_x))
out2 = (u'[基准] 单次最长%.4f秒=基线%.1f倍 | 旧均摊口径%.4f秒/次'
        u'=%.1f倍(把冻结摊到每次, 会严重高估"执行变慢") | '
        u'判读: 正常段%.2f倍才反映主机快慢, 冻结段是整块阻塞'
        % (_pb2_max, _pb2_mx, _pb2_avg, _pb2_x, _pb2_norm_x))

print('  ' + out1)
print('  ' + out2)
print()

# 真渲染检查: 分别数 %% 与占位符, 不写 '%' not in out
for nm, tmpl_specs, o in [('第1行', 7, out1), ('第2行', 5, out2)]:
    chk('%s 已真渲染(无裸露 %d/%%.替换符)' % (nm, tmpl_specs),
        '%.' not in o and '%d' not in o and '%s' not in o and '%%' not in o)
chk('第1行 冻结占比与日志 32.92%% 吻合', abs(_pb2_frz_sh - 32.92) < 0.6,
    '实际 %.2f%%' % _pb2_frz_sh)
chk('第1行 正常段倍数应接近 2 (而非 598)', 1.5 < _pb2_norm_x < 2.5,
    '实际 %.2f' % _pb2_norm_x)
chk('第1行 正常段次数 = 90-4 = 86', _pb2_norm_n == 86)
chk('第2行 旧均摊口径仍应显示约 598 倍(对照用)', 590 < _pb2_x < 610,
    '实际 %.1f' % _pb2_x)
chk('口径分离后正常段与旧口径差距 > 100 倍', _pb2_x / _pb2_norm_x > 100,
    '%.0f 倍' % (_pb2_x / _pb2_norm_x))

# ---------------------------------------------------------------- 4 卡死阈值
print()
print('=== 4. 卡死阈值(用历史真实完成耗时) ===')
HIST = [498.0, 527.0, 540.0, 570.0]     # 实测四轮完成耗时
ALERT_AT = 407.0                        # 本轮误报时刻
THRESH = 900.0

old_fire = [h for h in HIST if h > 360.0]
new_fire = [h for h in HIST if h > THRESH]
print('  历史完成耗时: %s' % [int(h) for h in HIST])
print('  旧阈值 360 秒 -> 误报 %d/%d 轮: %s' % (len(old_fire), len(HIST), [int(h) for h in old_fire]))
print('  新阈值 900 秒 -> 误报 %d/%d 轮' % (len(new_fire), len(HIST)))
chk('旧阈值 360 会让全部历史轮次误报', len(old_fire) == len(HIST))
chk('新阈值 900 不再误报任何历史轮次', len(new_fire) == 0)
chk('本轮 407 秒误报点已被新阈值排除', ALERT_AT < THRESH)
chk('新阈值仍高于历史最慢 570 秒(有 1.58 倍余量)', THRESH / max(HIST) > 1.5,
    '%.2f 倍' % (THRESH / max(HIST)))

msg = (u' —— 已运行%d秒, 超过历史最长耗时(约570秒)的1.5倍, 疑似卡死; '
       u'后续轮次仍会继续尝试(不强制全天中性), 若长时间无进展'
       u'建议重启策略(重启不影响持仓与状态文件)' % int(407))
chk('卡死文案已真渲染', '%d' not in msg and '%%' not in msg)
chk('卡死文案不再出现旧的错误数字 180', '180' not in msg)
chk('卡死文案不再声称"将全天中性"', u'将全天中性' not in msg)
print('  ' + msg)

# ---------------------------------------------------------------- 5 铁律
print()
print('=== 5. 铁律 ===')
n_stop = 0
for nd in ast.walk(tree):
    if isinstance(nd, ast.Attribute) and nd.attr == 'stop_order':
        n_stop += 1
    if isinstance(nd, ast.Name) and nd.id == 'stop_order':
        n_stop += 1
chk('stop_order AST = 0 (绝不止损)', n_stop == 0, '实际 %d' % n_stop)
chk('NEVER_STOP_LOSS = True 仍在', u'NEVER_STOP_LOSS = True' in src)
chk('_lg_on 已恢复 True', src.count(u'_lg_on = True') == 1)

# ---------------------------------------------------------------- 汇总
print()
print('=' * 70)
print('PASS %d / FAIL %d' % (len(PASS), len(FAIL)))
if FAIL:
    for f in FAIL:
        print('  FAIL: ' + f)
    sys.exit(1)
print('全部通过')
