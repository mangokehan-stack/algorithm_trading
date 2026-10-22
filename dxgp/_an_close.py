# -*- coding: utf-8 -*-
"""闭合反推: 用 _elapsed 与各实测段反推 _dt_rest，验证是否存在大块未知耗时"""
import io, re

P = r'C:/广发证券QMT量化交易系统 - 交易端/bin.x64/zt_shrink_run.log'
raw = io.open(P, 'rb').read()


def dec_line(b):
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('gbk', 'replace')


lines = [dec_line(x) for x in raw.split(b'\r\n') if x.strip()]

rows = []
for ln in lines:
    if '内置通道取数完成' not in ln:
        continue
    m = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', ln)
    m2 = re.search(r'耗时(\d+)秒\((.*?)\)\s*字段', ln)
    if not (m and m2):
        continue
    rows.append((m.group(1), int(m2.group(1)), m2.group(2)))

print('%-9s %5s %5s %5s %6s %6s %6s %7s' % (
    '时刻', '总', '列表', '批下', '解析', '落盘', '组装', '残差'))
for tm, tot, seg in rows[-10:]:
    def g(k):
        mm = re.search(k + r'([\d.]+)', seg)
        return float(mm.group(1)) if mm else 0.0
    lst = g(r'列表')
    bd = g(r'批内下载')
    par = float(re.search(r'解析(\d+)', seg).group(1))
    dp = g(r'落盘')
    asm = g(r'组装')
    amt = g(r'指数量能')
    rest = tot - (lst + bd + par + dp + asm + amt)
    print('%-9s %5d %5.0f %5.0f %6.0f %6.1f %6.1f %7.1f' % (
        tm[-8:], tot, lst, bd, par, dp, asm, rest))

# 关键: 完成时刻 - 移交时刻 是否等于 总耗时（验证 _elapsed 起点）
print('\n--- 移交 -> 完成 墙钟差 vs 总耗时 ---')
import datetime as dt
for tm, tot, seg in rows[-6:]:
    t1 = dt.datetime.strptime(tm, '%Y-%m-%d %H:%M:%S')
    # 往前找同一天内最近的一条「移交后台线程」
    prev = None
    for ln in lines:
        if '移交后台线程' in ln:
            m = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', ln)
            if m and m.group(1) < tm:
                prev = m.group(1)
    if prev:
        t0 = dt.datetime.strptime(prev, '%Y-%m-%d %H:%M:%S')
        print('移交%s 完成%s 墙钟差%4.0f秒 | 总耗时%4d秒' % (
            prev[-8:], tm[-8:], (t1 - t0).total_seconds(), tot))
