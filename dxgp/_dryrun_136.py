# -*- coding: utf-8 -*-
"""V2.6.136 干跑: 用磁盘真实累积池验证跨代恢复

本脚本只验证【跨代判定】逻辑(恢复/丢弃/三道校验)。
恢复出来的值形状是否正确(必须 {日期:{close,preClose}} 而非 [close,preClose])
由 _dryrun_137.py 覆盖 —— V2.6.137 修的就是形状不匹配。

用例:
  [1] gen 相同(同代)            -> 正常恢复, 说明串无"跨代"
  [2] gen 不同(跨代, 本次修复)   -> 仍恢复, 说明串含"跨代恢复"
  [3] 换日                      -> 丢弃(保留原语义)
  [4] cols 不符                 -> 丢弃(保留原语义)
  [5] v 不符 / 日期池为空        -> 丢弃
  [6] 恢复后 _SENT_ACC['gen']    -> 等于本代 gen(改动4 的核心)
  [7] 文件不存在                -> '无落盘文件'
"""
import ast
import io
import json
import os
import shutil
import sys
import tempfile
import types

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
CRLF = '\r\n'
src = open(P, 'rb').read().decode('gbk')
tree = ast.parse(src)

# 逐字抽取真实函数(模块级 def, 无前导空白)
want = ('_sent_acc_load', '_exc_text')
segs = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in want:
        segs.append(ast.get_source_segment(src, node))
assert len(segs) == 2, '抽取函数数不符: %d' % len(segs)
mod = '\n'.join(s.replace(CRLF, '\n') for s in segs)

PASS = [0]
FAIL = []


def chk(name, ok, detail=''):
    if ok:
        PASS[0] += 1
        print('  PASS  %-52s %s' % (name, detail))
    else:
        FAIL.append(name)
        print('  FAIL  %-52s %s' % (name, detail))


# 真实累积池
REAL = r'C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_sent_acc_8973786.json'
assert os.path.exists(REAL), '真实累积池不存在'
base = json.load(open(REAL, encoding='utf-8'))
print('源池: date=%s gen=%.1f v=%s cols=%s md=%d dates=%d' % (
    base.get('date'), base.get('gen') or 0, base.get('v'), base.get('cols'),
    len(base.get('md') or {}), len(base.get('dates') or [])))

TMPDIR = tempfile.mkdtemp(prefix='zx136_')


def build_env(pool_path, today, gen_now):
    """构造最小真实环境: os/json 用真模块, G/_GEN_STATE/_SENT_ACC 用真结构"""
    ns = {
        'os': os, 'json': json,
        'G': types.SimpleNamespace(today=today),
        '_GEN_STATE': {'id': gen_now, 'path': ''},
        '_SENT_ACC': {'date': '', 'gen': 0.0, 'md': {}, 'ok': 0, 'fail': 0,
                      'rounds': 0, 'pend_rounds': 0, 'ser': {}},
    }
    exec(mod, ns)
    # 路径函数: 指向本次用例的临时文件(只替路径, 不替被测算逻辑)
    ns['_sent_acc_path'] = lambda: pool_path
    exec(mod, ns)
    return ns


def write_pool(name, **override):
    """复制源池并覆盖字段, 返回路径"""
    d = dict(base)
    d.update(override)
    p = os.path.join(TMPDIR, name)
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(d, ensure_ascii=False))
    return p


DAY = str(base.get('date') or '')
GEN_OLD = float(base.get('gen') or 0.0)
GEN_NEW = GEN_OLD + 1234.5
N_MD = len(base.get('md') or {})

print('\n--- [1] gen 相同(同代) ---')
p1 = write_pool('same.json')
ns1 = build_env(p1, DAY, GEN_OLD)
n1, m1 = ns1['_sent_acc_load']()
chk('[1] 同代可恢复', n1 == N_MD, '恢复 %d / 期望 %d' % (n1, N_MD))
chk('[1] 同代说明串不含"跨代"', '跨代' not in m1, m1[:90])
chk('[1] _SENT_ACC[gen] == 本代', abs(ns1['_SENT_ACC']['gen'] - GEN_OLD) < 1e-6,
    '%.1f' % ns1['_SENT_ACC']['gen'])

print('\n--- [2] gen 不同(跨代, 本次修复) ---')
p2 = write_pool('cross.json')
ns2 = build_env(p2, DAY, GEN_NEW)
n2, m2 = ns2['_sent_acc_load']()
chk('[2] 跨代仍可恢复(核心)', n2 == N_MD, '恢复 %d / 期望 %d' % (n2, N_MD))
chk('[2] 说明串含"跨代恢复"', '跨代恢复' in m2, m2[:110])
chk('[2] 说明串含盘内/本代 gen', ('盘内gen=%.1f' % GEN_OLD) in m2 and ('本代gen=%.1f' % GEN_NEW) in m2)
chk('[2] _SENT_ACC[gen] == 本代(改动4)',
    abs(ns2['_SENT_ACC']['gen'] - GEN_NEW) < 1e-6, '%.1f' % ns2['_SENT_ACC']['gen'])
chk('[2] 恢复的 md 与源池键集一致',
    sorted(ns2['_SENT_ACC']['md'].keys()) == sorted(base['md'].keys()))

print('\n--- [3] 换日 -> 仍丢弃 ---')
ns3 = build_env(p2, '20991231', GEN_NEW)
n3, m3 = ns3['_sent_acc_load']()
chk('[3] 换日丢弃', n3 == 0 and '换日丢掉' in m3 or ('换日' in m3), '%d | %s' % (n3, m3[:60]))
chk('[3] 换日后 _SENT_ACC 未被填充', not ns3['_SENT_ACC']['md'])

print('\n--- [4] cols 不符 -> 仍丢弃 ---')
p4 = write_pool('badcols.json', cols='close/volume')
ns4 = build_env(p4, DAY, GEN_NEW)
n4, m4 = ns4['_sent_acc_load']()
chk('[4] cols 不符丢弃', n4 == 0 and '字段口径不符' in m4, '%d | %s' % (n4, m4[:70]))

print('\n--- [5] v=2 但日期池为空 -> 丢弃 ---')
p5 = write_pool('nodates.json', dates=[])
ns5 = build_env(p5, DAY, GEN_NEW)
n5, m5 = ns5['_sent_acc_load']()
chk('[5] 日期池为空丢弃', n5 == 0 and '日期池为空' in m5, '%d | %s' % (n5, m5[:70]))

print('\n--- [6] md 为空 -> 丢弃 ---')
p6 = write_pool('nomd.json', md={})
ns6 = build_env(p6, DAY, GEN_NEW)
n6, m6 = ns6['_sent_acc_load']()
chk('[6] 盘内样本为空丢弃', n6 == 0 and '样本为空' in m6, '%d | %s' % (n6, m6[:70]))

print('\n--- [7] 文件不存在 ---')
ns7 = build_env(os.path.join(TMPDIR, 'nope.json'), DAY, GEN_NEW)
n7, m7 = ns7['_sent_acc_load']()
chk('[7] 无落盘文件', n7 == 0 and m7 == '无落盘文件', '%d | %s' % (n7, m7))

print('\n--- [8] 旧结构 v<2 (兼容分支) ---')
old_form = {'date': DAY, 'gen': GEN_OLD, 'v': 1, 'cols': 'close/preClose',
            'md': {'000001.SZ': {'20261016': [10.5, 10.2]},
                   '600000.SH': {'20261016': [7.1, 7.0]}},
            'ok': 2, 'fail': 0, 'rounds': 1, 'pend_rounds': 0}
p8 = os.path.join(TMPDIR, 'v1.json')
with io.open(p8, 'w', encoding='utf-8', newline='') as f:
    f.write(json.dumps(old_form, ensure_ascii=False))
ns8 = build_env(p8, DAY, GEN_NEW)
n8, m8 = ns8['_sent_acc_load']()
chk('[8] v=1 旧结构跨代可恢复', n8 == 2, '%d | %s' % (n8, m8[:90]))
chk('[8] v=1 值解析正确',
    ns8['_SENT_ACC']['md'].get('000001.SZ', {}).get('20261016') == [10.5, 10.2],
    str(ns8['_SENT_ACC']['md'].get('000001.SZ')))

print('\n--- [9] _gen_now=0(未初始化) 不应误报跨代 ---')
ns9 = build_env(p2, DAY, 0.0)
n9, m9 = ns9['_sent_acc_load']()
chk('[9] gen_now=0 时仍可恢复', n9 == N_MD, '%d' % n9)
chk('[9] gen_now=0 时不写"跨代恢复"', '跨代' not in m9, m9[:90])
chk('[9] gen_now=0 时 _SENT_ACC[gen] 回退盘内值',
    abs(ns9['_SENT_ACC']['gen'] - GEN_OLD) < 1e-6, '%.1f' % ns9['_SENT_ACC']['gen'])

shutil.rmtree(TMPDIR, ignore_errors=True)

print('\n' + '=' * 66)
print('PASS %d / FAIL %d' % (PASS[0], len(FAIL)))
if FAIL:
    for f in FAIL:
        print('  FAILED:', f)
    sys.exit(1)
print('ALL PASS')
