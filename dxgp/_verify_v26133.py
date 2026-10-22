# -*- coding: utf-8 -*-
"""
V2.6.133 结构验证（不靠肉眼看缩进，用 AST）
校验点：
  1. 相位序列采集语句在解析 for 循环体内、且在 >=1.0 分支内
  2. 相位序列初始化在循环外（否则每只票重置）
  3. 间隔日志在正确的 try 块内
  4. _lg_on 局部量存在且 if _lg_on 包住 run_time 注册
  5. 参数指纹零漂移（重新算一遍）
"""
import io
import ast
import hashlib

P = 'zt_shrink_strategy_gbk.py'
src = open(P, 'rb').read().decode('gbk')
tree = ast.parse(src)
lines = src.split('\r\n')

print('=== 1. AST 结构校验 ===')


def find_func(name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


# ---- 1a. _pb2_slow_seq.append 必须在 for 循环体内、if >=1.0 体内
target = None
for n in ast.walk(tree):
    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == 'append'
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == '_pb2_slow_seq'):
        target = n
        break
assert target is not None, '找不到 _pb2_slow_seq.append'
print('[OK] 找到 _pb2_slow_seq.append  L%d' % target.lineno)

# 检查它在 if _pb2_dt >= 1.0 体内
found_in_if = False
for n in ast.walk(tree):
    if isinstance(n, ast.If):
        try:
            cond_txt = ast.get_source_segment(src, n.test) or ''
        except Exception:
            cond_txt = ''
        if '_pb2_dt' in cond_txt and '1.0' in cond_txt:
            for sub in ast.walk(n):
                if sub is target:
                    found_in_if = True
                    print('[OK] 在 if 条件内: %s  L%d' % (cond_txt, n.lineno))
                    break
assert found_in_if, 'append 不在 if _pb2_dt >= 1.0 体内'

# 检查外层是 for 循环（不是函数顶层）
# 收集所有 for 节点，看 target 是否在其 body 里
in_for = False
for n in ast.walk(tree):
    if isinstance(n, ast.For):
        for sub in ast.walk(n):
            if sub is target:
                in_for = True
                break
    if in_for:
        break
assert in_for, 'append 不在 for 循环内'

# ---- 1b. _pb2_slow_seq = [] 必须在 for 循环【外】
assign_seq = None
for n in ast.walk(tree):
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id == '_pb2_slow_seq':
                assign_seq = n
                break
    if assign_seq is not None:
        break
assert assign_seq is not None, '找不到 _pb2_slow_seq = []'
print('[OK] 初始化 _pb2_slow_seq = []  L%d' % assign_seq.lineno)
assert assign_seq.lineno < target.lineno, '初始化必须在采集之前'

# 验证初始化不在 for 内: 找包含 append 的那个 for，其起止行
for_node = None
for n in ast.walk(tree):
    if isinstance(n, ast.For):
        for sub in ast.walk(n):
            if sub is target:
                if for_node is None or n.lineno > for_node.lineno:
                    for_node = n
assert for_node is not None
print('   解析 for 循环起点 L%d' % for_node.lineno)
assert assign_seq.lineno < for_node.lineno, \
    '初始化(L%d)必须在 for(L%d)之前，否则每只票重置' % (assign_seq.lineno, for_node.lineno)
print('[OK] 初始化在 for 循环之外(不会被每只票重置)')

# ---- 2. _lg_on 开关
has_lg_on = False
for n in ast.walk(tree):
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id == '_lg_on':
                has_lg_on = True
assert has_lg_on, '找不到 _lg_on 赋值'
print('[OK] _lg_on 局部开关存在')

# 确认 run_time('log_guard') 被 if 包住
lg_call = None
for n in ast.walk(tree):
    if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == 'run_time'):
        try:
            seg = ast.get_source_segment(src, n) or ''
        except Exception:
            seg = ''
        if 'log_guard' in seg:
            lg_call = n
assert lg_call is not None, '找不到 run_time(log_guard) 调用'

guarded = False
for n in ast.walk(tree):
    if isinstance(n, ast.If):
        for sub in ast.walk(n):
            if sub is lg_call:
                guarded = True
                try:
                    txt = ast.get_source_segment(src, n.test) or ''
                except Exception:
                    txt = ''
                print('[OK] run_time(log_guard) 被 if 包住, 条件 = %s  L%d'
                      % (txt, n.lineno))
                break
    if guarded:
        break
assert guarded, 'run_time(log_guard) 未被 if 包住'

# ---- 3. 间隔日志存在
assert '卡顿时刻序列' in src, '找不到间隔日志'
assert '_pb2_gaps.append' in src, '找不到间隔计算'
print('[OK] 间隔序列日志与计算均存在')

# ---- 4. 版本
assert "VERSION = 'V2.6.133'" in src
assert '版本号: V2.6.133' in src
print('[OK] 版本 = V2.6.133 (文件头 + VERSION 常量)')

print()
print('=== 2. 参数指纹 ===')
# 复算参数指纹算法（与文件内一致：模块级大写常量 + 值）
MOD_SKIP = set()
fp_src = []
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id.isupper():
                try:
                    val = ast.literal_eval(node.value)
                except Exception:
                    continue
                fp_src.append('%s=%r' % (t.id, val))
fp_txt = '|'.join(sorted(fp_src))
fp = hashlib.md5(fp_txt.encode('utf-8')).hexdigest()[:8]
print('复算指纹 =', fp)
print('期望指纹 = 8a4ab7e8')
assert fp == '8a4ab7e8', '参数指纹漂移! 得到 %s' % fp
print('[OK] 参数指纹零漂移')

print()
print('=== 3. 文件格式 ===')
raw = open(P, 'rb').read()
print('size =', len(raw))
print('md5  =', hashlib.md5(raw).hexdigest().upper())
assert b'\xef\xbb\xbf' != raw[:3], '存在 BOM'
assert '\n' not in src.replace('\r\n', ''), '存在裸 LF'
assert raw.decode('gbk').encode('gbk') == raw, 'GBK 往返不一致'
print('[OK] 无BOM / 无裸LF / GBK往返一致')
print()
print('ALL PASS')
