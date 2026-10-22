# -*- coding: utf-8 -*-
"""把校验脚本里会 IndexError 的 split()[n] 换成安全取值"""
P = r'E:\桌面\666666\dxgp\_check_inv.py'
s = open(P, encoding='utf-8').read()

# 1) 追加两个助手
anchor = '\ndef chk('
assert s.count(anchor) == 1
helpers = '''

def _seg(s, a):
    """a 之后到行尾; 锚点缺失返回空串"""
    i = s.index(a)
    return "" if i != i else s[int(i) + len(a):].split("\\n")[0]


def _seg2(s, a, b):
    """a 之后到 b 之前; 任一锚点缺失返回空串"""
    i = s.index(a)
    if i != i:
        return ""
    return s[int(i) + len(a):].split(b)[0]
'''
s = s.replace(anchor, helpers + anchor, 1)

reps = [
    ('and "_pb_" not in _body.split("_dt_rest = _elapsed")[1].split("\\n")[0])',
     'and "_pb_" not in _seg(_body, "_dt_rest = _elapsed"))'),
    ('"_pb2_" not in _body.split("_dt_rest = _elapsed")[1].split("_t_over =")[0])',
     '"_pb2_" not in _seg2(_body, "_dt_rest = _elapsed", "_t_over ="))'),
    ('"慢%.1f倍" in _body and "慢%.0f倍" not in _body.split("[基准] 宿主执行环境探针")[1]\n    .split("判读")[0])',
     '"慢%.1f倍" in _body\n    and "慢%.0f倍" not in _seg2(_body, "[基准] 宿主执行环境探针", "判读"))'),
]
for old, new in reps:
    n = s.count(old)
    print('%-52s x%d' % (old[:50].replace('\n', '\\n'), n))
    assert n >= 1, '锚点未命中:\n%s' % old
    s = s.replace(old, new)

open(P, 'w', encoding='utf-8', newline='\n').write(s)
compile(s, P, 'exec')
print('written ok')
