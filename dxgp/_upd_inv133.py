# -*- coding: utf-8 -*-
"""
更新 _check_inv.py 到 V2.6.133
  - 行数断言 13769 -> 13812
  - VERSION 断言 V2.6.132 -> V2.6.133
  - 新增 V2.6.133 断言段（log_guard 开关 + 相位间隔序列）
注意: 本文件是 UTF-8 + LF, 锚点必须写 \n
"""
import io
import sys

P = '_check_inv.py'
t = io.open(P, 'r', encoding='utf-8', newline='').read()
orig_len = len(t)

reps = []

# ---- 1. 行数断言
old = 'chk("行数=13713", len(lines) == 13769, "actual=%d (含末尾空段)" % len(lines))'
new = 'chk("行数=13812", len(lines) == 13812, "actual=%d (含末尾空段)" % len(lines))'
reps.append(('行数断言', old, new))

# ---- 2. VERSION 断言
old = ('chk("V2.6.112 版本号已升到 V2.6.132(且行尾注释未被吞)",\n'
       '    "VERSION = \'V2.6.132\'    # 当前版本号(与启动日志和横幅展示一致" in _body)')
new = ('chk("V2.6.112 版本号已升到 V2.6.133(且行尾注释未被吞)",\n'
       '    "VERSION = \'V2.6.133\'    # 当前版本号(与启动日志和横幅展示一致" in _body)')
reps.append(('VERSION 断言', old, new))

# ---- 3. 新增 V2.6.133 断言段，插在 fails 汇总之前
old = ('fails = [n for (n, c) in ok if not c]\n'
       'print("\\n%d/%d PASS" % (len(ok) - len(fails), len(ok)))')
new = (
    '# ---- V2.6.133: log_guard 对照实验开关 + 相位间隔序列 ----\n'
    '# 开关必须是【函数内局部量】_lg_on, 不是模块级大写常量(那会污染参数指纹)\n'
    'chk("V2.6.133 log_guard 开关用函数内局部量 _lg_on(不进参数指纹)",\n'
    '    "_lg_on = False      # V2.6.133" in _body)\n'
    'chk("V2.6.133 模块级无 LG_ 前缀大写常量(否则参数指纹必漂移)",\n'
    '    "LG_ON =" not in _body and "LOG_GUARD_ON =" not in _body)\n'
    '# run_time 注册必须被 if _lg_on 包住, 否则开关形同虚设\n'
    'chk("V2.6.133 run_time(log_guard) 被 if _lg_on 包住",\n'
    '    "if _lg_on:" in _body\n'
    '    and "_lg_on:" in _body)\n'
    '# 停用分支必须打日志, 否则"没那行"与"注册失败"无法区分\n'
    'chk("V2.6.133 停用分支有明确日志(否则与注册失败无法区分)",\n'
    '    "log_guard 本轮【已停用】" in _body)\n'
    'chk("V2.6.133 恢复路径提示保留(_lg_on 改回 True 即可)",\n'
    '    "把 _lg_on 改回 True 即可恢复" in _body)\n'
    '# 相位间隔序列: 序列容器必须在循环外初始化\n'
    'chk("V2.6.133 相位绝对秒序列在循环外初始化(否则每只票重置)",\n'
    '    "_pb2_slow_seq = []" in _body)\n'
    'chk("V2.6.133 相位序列记录 (起点秒, 结束秒, 耗时) 三元组",\n'
    '    "_pb2_slow_seq.append([int(_pb2_t0), int(_pb2_t1)," in _body)\n'
    '# 间隔必须是"起点秒之差", 不是"结束秒之差" —— 结束秒受阻塞时长污染\n'
    'chk("V2.6.133 间隔按【起点秒之差】计算(结束秒会被阻塞时长污染)",\n'
    '    "_pb2_slow_seq[_gi][0]" in _body\n'
    '    and "_pb2_slow_seq[_gi - 1][0]" in _body)\n'
    'chk("V2.6.133 间隔日志有单次分支(只有1次时也要说明)",\n'
    '    "无法算间隔" in _body)\n'
    'chk("V2.6.133 相位采集仍在 if _pb2_dt >= 1.0 体内(未被挪出)",\n'
    '    "if _pb2_dt >= 1.0:" in _body)\n'
    '# 铁律复核: 本版不得引入 stop_order\n'
    'chk("V2.6.133 止损单仍为 0(铁律)", _body.count("stop_order") == 0)\n'
    '\n'
    'fails = [n for (n, c) in ok if not c]\n'
    'print("\\n%d/%d PASS" % (len(ok) - len(fails), len(ok)))')
reps.append(('V2.6.133 断言段', old, new))

for name, o, n in reps:
    c = t.count(o)
    if c != 1:
        print('[FAIL] %s 命中 %d 次(应为1)' % (name, c))
        sys.exit(1)
    t = t.replace(o, n, 1)
    print('[OK] %s' % name)

io.open(P, 'w', encoding='utf-8', newline='').write(t)
print('DONE  %d -> %d 字节' % (orig_len, len(t)))
print('行数 %d -> %d' % (orig_len, len(t)))
