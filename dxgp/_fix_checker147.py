# -*- coding: utf-8 -*-
"""让 _check_inv.py 的 .index() 锚点缺失时记 FAIL 而非中断"""
P = r'E:\桌面\666666\dxgp\_check_inv.py'
s = open(P, encoding='utf-8').read()

# 1) 插入安全字符串类
anchor = 'PATH = r"E:\\桌面\\666666\\dxgp\\zt_shrink_strategy_gbk.py"'
assert s.count(anchor) == 1
cls = '''-*- placeholder -*-
'''
cls = '''class _S(str):
    """锚点缺失时 index() 返回 nan: 任何大小比较都为 False => 该断言自动记 FAIL,
    不会像原版那样直接 ValueError 中断整个校验脚本。"""
    def index(self, sub, *a):
        try:
            return str.index(self, sub, *a)
        except ValueError:
            return float("nan")


'''
s = s.replace(anchor, cls + anchor, 1)

# 2) 三个被查字符串包成 _S
for old, new in (
    ('    text = f.read()', '    text = _S(f.read())'),
    ('_body = "\\r\\n".join(l for l in lines if not l.startswith("版本号: "))',
     '_body = _S("\\r\\n".join(l for l in lines if not l.startswith("版本号: ")))'),
    ('_body_code = "\\n".join([_ln for _ln in _body.split("\\n")',
     '_body_code = _S("\\n".join([_ln for _ln in _body.split("\\n")'),
):
    assert s.count(old) == 1, '锚点未命中: %r' % old
    s = s.replace(old, new, 1)
# _body_code 结尾需补一个 ')'
i = s.index('_body_code = _S("\\n".join([_ln for _ln in _body.split("\\n")')
j = s.index('\n', s.index('\n', i) + 1)      # 该语句第二行末
seg = s[i:j]
assert seg.count('(') == seg.count(')') + 1, '括号配平异常:\n%s' % seg
s = s[:j] + ')' + s[j:]

# 3) 唯一的切片用法(L540 附近)改成安全形式
old_slice = '_body[_body.index("risk_ex_hits.append"):_body.index("risk_ex_hits.append") + 200]'
if old_slice in s:
    s = s.replace(old_slice,
                  '_ix_win(_body, "risk_ex_hits.append", 200)', 1)
    helper2 = '''

def _ix_win(s, sub, n):
    """取锚点后 n 个字符; 锚点不存在返回空串"""
    i = s.index(sub)
    return "" if i != i else s[int(i):int(i) + n]
'''
    s = s.replace('\ndef chk(', helper2 + '\ndef chk(', 1)

# 4) 版本钉死项
s = s.replace('chk("行数=14006", len(lines) == 14006,', 'chk("行数=14514", len(lines) == 14515,')
s = s.replace('chk("V2.6.138 文件头版本号已升到 V2.6.138",\n    text.count("# 版本号: V2.6.138") == 1)',
              'chk("V2.6.147 文件头版本号已升到 V2.6.147",\n    text.count("# 版本号: V2.6.147") == 1)')
s = s.replace('''chk("V2.6.138 VERSION 常量已升到 V2.6.138",
    text.count("VERSION = 'V2.6.138'") == 1)''',
              '''chk("V2.6.147 VERSION 常量已升到 V2.6.147",
    text.count("VERSION = 'V2.6.147'") == 1)''')
assert '行数=14006' not in s and 'VERSION = \'V2.6.138\'' not in s

open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('ok, lines=%d' % s.count('\n'))
