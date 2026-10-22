# -*- coding: utf-8 -*-
"""修 V2.6.103 提示日志的多行字符串漏引号(第一行/第二行末尾缺 ')"""
import io, hashlib, py_compile

SRC = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
NL = '\r\n'
t = io.open(SRC, 'r', encoding='gbk', newline='').read()
lines = t.split(NL)

hit = -1
for i, l in enumerate(lines):
    if '_sent_wlog' in l and '\u672c\u8f6e\u88ab\u603b\u9884\u7b97\u622a\u65ad' in l:
        hit = i
        break
if hit < 0:
    raise SystemExit('anchor not found')

print('BEFORE:')
for j in range(hit, hit + 4):
    print('  %d| %s' % (j + 1, repr(lines[j])))

lines[hit] = ("            _sent_wlog('[\u63d0\u793a] \u672c\u8f6e\u88ab\u603b\u9884\u7b97\u622a\u65ad, "
              "\u4f46\u96f6\u5931\u8d25\u4e14\u5df2\u53d6\u5230%d\u53ea'")
lines[hit + 1] = ("                       '(\u5168\u5e02\u573a\u5747\u5300\u62bd\u6837, \u8986\u76d6%.1f%%), "
                  "\u6837\u672c\u91cf\u8db3\u591f: '")
lines[hit + 2] = ("                       '\u91c7\u7528\u672c\u8f6e\u5b9e\u6d4b\u60c5\u7eea"
                  "(\u4e0d\u518d\u6cbf\u7528\u4e0a\u6b21\u6210\u529f\u4fe1\u53f7)'")

print('AFTER:')
for j in range(hit, hit + 4):
    print('  %d| %s' % (j + 1, repr(lines[j])))

t = NL.join(lines)
io.open(SRC, 'w', encoding='gbk', newline='').write(t)
py_compile.compile(SRC, doraise=True)
print('PY_COMPILE_OK  LINES=%d  MD5=%s' % (
    len(lines), hashlib.md5(t.encode('gbk')).hexdigest().upper()))
