# -*- coding: utf-8 -*-
"""双指纹验证: 与 QMT 启动同一算法、同一 globals()。

V2.6.86 更正: 旧版用 AST 只抓"单目标字面量赋值"近似复算, 而母版 _fp_keys()
抓的是 globals() 里全部 UPPER_CASE 标量/容器(255 个键), 口径不同 —— 旧版算出的
94d5c464 与 QMT 实际打印的 392cbf3a 不符。现改为 exec 母版源码后直接调用
param_fingerprint() / code_fingerprint(), 结果可与客户端日志逐字符比对。

校验点:
  1 参数指纹不含 VERSION 键(当前版)
  2 同一文件重复加载, 两指纹稳定(排除 dict 顺序抖动)
  3 把 VERSION 改成 V9.9.99: 参数指纹不变、版本指纹必变
  4 真实跨版本: V2.6.85 -> V2.6.86 参数指纹相同、版本指纹不同
  5 历史版本 V2.6.83/84 的 VERSION 仍在参数键中(改造前事实, 只记录不判失败)
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile

CUR = 'zt_shrink_strategy_gbk.py'
FILES = [
    ('V2.6.83', '_baseline/V2.6.83_final.py'),
    ('V2.6.84', '_baseline/V2.6.84_final.py'),
    ('V2.6.85', '_baseline/V2.6.85_final.py'),
    ('V2.6.86', '_baseline/V2.6.86_final.py'),
    ('当前', CUR),
]
TYPES = (int, float, bool, str, tuple, list, dict, type(None))


def probe(path):
    """exec 母版, 返回运行时真实指纹"""
    src = open(path, 'rb').read().decode('gbk', 'strict')
    ns = {'__file__': os.path.abspath(path), '__name__': 'fp_probe'}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(src, path, 'exec'), ns)
    p, _ = ns['param_fingerprint']()
    # code_fingerprint 是 V2.6.85 才新增的, 历史版本没有
    c = ns['code_fingerprint']()[0] if 'code_fingerprint' in ns else '(无)'
    keys = sorted(ns['_fp_keys']())
    # 交叉核对: 按 _fp_keys 的口径独立复算一次, 必须与函数返回值一致
    raw = '|'.join('%s=%s' % (k, ns[k]) for k in keys)
    h = 2166136261
    for b in raw.encode('utf-8'):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return {
        'ver': ns.get('VERSION'), 'param': p, 'code': c,
        'nkeys': len(keys), 'has_ver_key': 'VERSION' in keys,
        'independent': '%08x' % h,
    }


def main():
    rows = []
    for ver, path in FILES:
        if not os.path.exists(path):
            print('SKIP 不存在: %s' % path)
            continue
        r = probe(path)
        r['label'] = ver
        rows.append(r)

    print('%-8s %-9s %-10s %-10s %-6s %-8s' %
          ('版本', 'VERSION', '参数指纹', '版本指纹', '参数数', 'VERSION在键中'))
    for r in rows:
        print('%-8s %-9s %-10s %-10s %-6d %-8s'
              % (r['label'], r['ver'], r['param'], r['code'], r['nkeys'],
                 '是' if r['has_ver_key'] else '否'))

    fails = []
    cur = rows[-1]

    # 1 VERSION 不进参数键
    if cur['has_ver_key']:
        fails.append('当前版 VERSION 仍在参数键中')
    # 2 独立复算一致
    if cur['independent'] != cur['param']:
        fails.append('独立复算 %s != 函数返回 %s' % (cur['independent'], cur['param']))
    # 3 重复加载稳定
    again = probe(CUR)
    if again['param'] != cur['param'] or again['code'] != cur['code']:
        fails.append('两次加载指纹不一致 %s/%s' % (cur['param'], again['param']))
    # 4 升版模拟
    tmp = tempfile.mkdtemp(prefix='fp_')
    try:
        alt = os.path.join(tmp, 'bumped.py')
        src = open(CUR, 'rb').read().decode('gbk', 'strict')
        old = "VERSION = '%s'" % cur['ver']
        if old not in src:
            fails.append('未找到 VERSION 字面量行')
        else:
            open(alt, 'wb').write(
                src.replace(old, "VERSION = 'V9.9.99'", 1).encode('gbk'))
            bump = probe(alt)
            if bump['param'] != cur['param']:
                fails.append('升版后参数指纹变化 %s->%s' % (cur['param'], bump['param']))
            if bump['code'] == cur['code']:
                fails.append('升版后版本指纹未变化 %s' % bump['code'])
            print('\n升版模拟(VERSION->V9.9.99): 参数 %s->%s | 版本 %s->%s'
                  % (cur['param'], bump['param'], cur['code'], bump['code']))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 5 真实跨版本: 85 -> 86 是纯文档版(参数必同); 86 -> 当前 新增行为常量(参数必变, 属预期)
    d = dict((r['label'], r) for r in rows)
    if 'V2.6.85' in d and 'V2.6.86' in d:
        a, b = d['V2.6.85'], d['V2.6.86']
        print('真实跨版本 V2.6.85->V2.6.86: 参数 %s->%s (%s) | 版本 %s->%s (%s)'
              % (a['param'], b['param'],
                 '相同' if a['param'] == b['param'] else '不同',
                 a['code'], b['code'],
                 '不同' if a['code'] != b['code'] else '相同'))
        if a['param'] != b['param']:
            fails.append('V2.6.85->V2.6.86(纯文档版) 参数指纹不应变化')
        if a['code'] == b['code']:
            fails.append('V2.6.85->V2.6.86 版本指纹应变化')
    if 'V2.6.86' in d:
        b = d['V2.6.86']
        print('真实跨版本 V2.6.86->%s: 参数 %s->%s (%s, 新增行为常量属预期) | 版本 %s->%s'
              % (cur['ver'], b['param'], cur['param'],
                 '相同' if b['param'] == cur['param'] else '不同',
                 b['code'], cur['code']))

    print('')
    if fails:
        for f in fails:
            print('FAIL:', f)
        return 1
    print('RESULT: 运行时参数指纹=%s(与 QMT 日志同值), 版本指纹=%s, 升版仅动版本指纹 -> PASS'
          % (cur['param'], cur['code']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
