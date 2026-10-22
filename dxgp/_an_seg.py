# -*- coding: utf-8 -*-
"""日志按行自动判编码 + 分段耗时抽取（日志混编码：前段 GBK，后段 UTF-8）"""
import io, re, sys

P = r'C:/广发证券QMT量化交易系统 - 交易端/bin.x64/zt_shrink_run.log'
raw = io.open(P, 'rb').read()


def dec_line(b):
    """单行自动选编码：UTF-8 能解就用 UTF-8，否则用 GBK。"""
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('gbk', 'replace')


lines = [dec_line(x) for x in raw.split(b'\r\n') if x.strip()]
print('总行', len(lines))
print('末条', lines[-1][:90])

recs = []
for i, ln in enumerate(lines):
    if '内置通道取数完成' not in ln:
        continue
    m = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', ln)
    m2 = re.search(r'耗时(\d+)秒\((.*?)\)\s*字段', ln)
    if not (m and m2):
        continue
    recs.append((i, m.group(1), int(m2.group(1)), m2.group(2)))
print('完成行', len(recs))


def g(seg, key, dflt=None):
    m = re.search(key + r'(-?[\d.]+)', seg)
    return float(m.group(1)) if m else dflt


print('\n%-9s %5s %6s %6s %6s %6s %6s %6s %6s %6s' % (
    '时刻', '总', '批下载', '转dict', '提取', '解其他', '落盘', '组装', '残差', '核'))
for i, tm, tot, seg in recs[-8:]:
    bd = g(seg, r'批内下载') or 0
    td = g(seg, r'转dict') or 0
    ex = g(seg, r'\[')  # 不用
    m3 = re.search(r'解析\d+\[转dict([\d.]+)\+提取([\d.]+)\+其他([\d.]+)\]', seg)
    td, ex, po = [float(x) for x in m3.groups()] if m3 else (0, 0, 0)
    par = float(re.search(r'解析(\d+)', seg).group(1))
    dp = g(seg, r'落盘') or 0
    asm = g(seg, r'组装') or 0
    rest = g(seg, r'其他([\d.]+)=', None)
    m4 = re.search(r'其他([\d.]+)=(\d+)秒', seg)
    rest = float(m4.group(1)) if m4 else None
    chk = 'OK' if m4 and int(m4.group(2)) == tot else 'X'
    print('%-9s %5d %6.0f %6.1f %6.1f %6.1f %6.1f %6.1f %6s %6s' % (
        tm[-8:], tot, bd, td, ex, po, dp, asm,
        ('%.1f' % rest) if rest is not None else '?', chk))

# 各轮之间：完成时刻 -> 下一轮移交时刻，期间是否有其它 [情绪] 日志
print('\n--- 每轮完成行之后紧跟的 3 行 ---')
for i, tm, tot, seg in recs[-4:]:
    print('[完成]', tm, '总', tot)
    for j in range(i + 1, min(i + 4, len(lines))):
        print('    ', lines[j][:150])
