# -*- coding: utf-8 -*-
import io
import re

P = r'C:/广发证券QMT量化交易系统 - 交易端/bin.x64/zt_shrink_run.log'
raw = io.open(P, 'rb').read()


def dec(b):
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('gbk', 'replace')


ls = [dec(x) for x in raw.split(b'\r\n') if x.strip()]
rows = []
for ln in ls:
    if '内置通道取数完成' not in ln:
        continue
    m = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', ln)
    m2 = re.search(r'耗时(\d+)秒\((.*?)\)\s*字段', ln)
    if not (m and m2):
        continue
    seg = m2.group(2)
    mo = re.search(r'本轮成功(\d+)只', ln)
    ma = re.search(r'累积(\d+)只/全市场(\d+)只', ln)
    ok = int(mo.group(1)) if mo else 0
    acc = int(ma.group(1)) if ma else ok
    m3 = re.search(r'解析(\d+)\[转dict([\d.]+)\+提取([\d.]+)\+其他([\d.]+)\]', seg)
    if m3:
        par, td, ex = float(m3.group(1)), float(m3.group(2)), float(m3.group(3))
    else:
        par = td = ex = 0.0
    rows.append((m.group(1)[-8:], int(m2.group(1)), ok, acc, par, td, ex))

hdr = ('%-9s %5s %6s %6s %6s %9s %8s' %
       ('time', 'tot', 'round', 'acc', 'parse', 'dict/ea', 'ext/ea'))
print(hdr)
for t, tot, ok, acc, par, td, ex in rows[-10:]:
    a = max(acc, 1)
    print('%-9s %5d %6d %6d %6.0f %9.2f %8.2f' % (
        t, tot, ok, acc, par, td * 1000.0 / a, ex * 1000.0 / a))
