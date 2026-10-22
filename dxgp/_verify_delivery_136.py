# -*- coding: utf-8 -*-
"""V2.6.136 交付前硬检查"""
import ast
import glob
import hashlib
import os

P = 'zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
t = raw.decode('gbk')

print('=' * 66)
print('V2.6.136 交付复核')
print('=' * 66)
print('bytes  %d' % len(raw))
print('MD5    %s' % hashlib.md5(raw).hexdigest())
print('CRLF   %d   LF %d   (裸LF=%d)'
      % (raw.count(b'\r\n'), raw.count(b'\n'),
         raw.count(b'\n') - raw.count(b'\r\n')))
print('BOM    %s' % (raw[:3] == b'\xef\xbb\xbf'))
print('GBK往返 %s' % (t.encode('gbk') == raw))
seg = len(t.split('\r\n'))
print('段数   %d  (真实行数 %d)' % (seg, seg - 1))
print('文件头 %s' % t.split('\r\n')[4].strip()[:60])

try:
    compile(t, P, 'exec')
    print('compile OK')
except SyntaxError as e:
    print('compile FAIL: %s' % e)

tree = ast.parse(t)
n_stop = 0
for nd in ast.walk(tree):
    if isinstance(nd, ast.Attribute) and nd.attr == 'stop_order':
        n_stop += 1
    if isinstance(nd, ast.Name) and nd.id == 'stop_order':
        n_stop += 1
print('stop_order AST = %d  (铁律要求 0)' % n_stop)

# 模块级大写常量清点: 确认本版没新增(与改前备份比对)
def upper_consts(src):
    out = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign):
            for tg in node.targets:
                if (isinstance(tg, ast.Name) and tg.id.isupper()
                        and not tg.id.startswith('_')
                        and isinstance(node.value, ast.Constant)):
                    out.add(tg.id)
    return out


bak = sorted(glob.glob(P + '.bak-*'))[-1]
braw = open(bak, 'rb').read()
bt = braw.decode('gbk')
a = upper_consts(bt)
b = upper_consts(t)
print()
print('模块级大写常量: 改前 %d 个, 改后 %d 个, 新增 %s, 删除 %s'
      % (len(a), len(b), sorted(b - a) or '无', sorted(a - b) or '无'))

print()
print('关键项核验:')
for name, cond in [
    ('VERSION = V2.6.136', "VERSION = 'V2.6.136'" in t),
    ('文件头 V2.6.136', '# 版本号: V2.6.136' in t),
    ('NEVER_STOP_LOSS = True', 'NEVER_STOP_LOSS = True' in t),
    ('_lg_on = True (已恢复)', '_lg_on = True' in t),
    ('_lg_on = False (旧) 已消失', '_lg_on = False      # V2.6.133' not in t),
    ('_age > 900.0 (新阈值)', '_age > 900.0' in t),
    ('_age > 360.0 (旧阈值) 已消失', '_age > 360.0' not in t),
    ('_pb2_slow_sum 冻结合计', '_pb2_slow_sum += _pb2_dt' in t),
    ('_pb2_slow30 30秒模', '_pb2_k30 = int(_pb2_t1) % 30' in t),
    ('_pb2_beat 自动判读', "_pb2_beat = '无法判定'" in t),
    ('旧模板「相邻差恒为10」已清', '相邻差恒为10' not in t),
    ('旧文案「将全天中性」已清', '将全天中性' not in t),
    ('keep_from 仍为 0 (V2.6.134 已撤销)', 'keep_from' not in t),
    ('取数窗口仍 110', '        _sent_backfill_days = 110\r\n' in t),
]:
    print('  %-34s %s' % (name, 'PASS' if cond else 'FAIL'))

print()
print('备份链:')
for f in sorted(glob.glob(P + '.bak-*')):
    r = open(f, 'rb').read()
    print('  %-34s %8d  %s'
          % (os.path.basename(f), len(r), hashlib.md5(r).hexdigest()[:8]))
print('  %-34s %8d  %s  <- 现役 V2.6.136'
      % (P, len(raw), hashlib.md5(raw).hexdigest()[:8]))
