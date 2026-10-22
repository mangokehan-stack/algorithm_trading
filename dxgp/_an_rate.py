# -*- coding: utf-8 -*-
"""关键核算: 各轮 只数 / 解析池 / 各段 ms 每只"""
import io, re

P = r'C:/广发证券QMT量化交易系统 - 交易端/bin.x64/zt_shrink_run.log'
raw = io.open(P, 'rb').read()


def dec(b):
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('gbk', 'replace')


lines = [dec(x) for x in raw.split(b'\r\n') if x.strip()]

rows = []
for ln in lines:
    if '内置通道取数完成' not in ln:
        continue
    m = re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', ln)
    m2 = re.search(r'耗时(\d+)秒\((.*?)\)\s*字段', ln)
    if not (m and m2):
        continue
    seg = m2.group(2)
    # 本轮成功只数
    m_ok = re.search(r'本轮成功(\d+)只', ln)
    m_acc = re.search(r'累积(\d+)只/全市场(\d+)只', ln)
    ok = int(m_ok.group(1)) if m_ok else 0
    acc = int(m_acc.group(1)) if m_acc else 0
    # 解析池: 累积池 + 本轮新取 (代码遍历 _acc_md)
    pool = acc + ok if acc else ok

    def g(k):
        mm = re.search(k + r'([\d.]+)', seg)
        return float(mm.group(1)) if mm else 0.0

    m3 = re.search(r'解析(\d+)\[转dict([\d.]+)\+提取([\d.]+)\+其他([\d.]+)\]', seg)
    if m3:
        par, td, ex = float(m3.group(1)), float(m3.group(2)), float(m3.group(3))
    else:
        par = float(re.search(r'解析(\d+)', seg).group(1)) if '解析' in seg else 0
        td = ex = 0.0
    rows.append(dict(tm=m.group(1), tot=int(m2.group(1)), ok=ok, acc=acc, pool=pool,
                     bd=g(r'批内下载'), par=par, td=td, ex=ex,
                     dump=g(r'落盘')))

print('解析池口径: pool = 累积(acc) + 本轮新取(ok)  [代码遍历的是 _acc_md 累积池]')
print('%-9s %5s %5s %6s %6s %7s %7s %7s %7s' % (
    '时刻', '总', '本轮', '累积', '池', '解析', '转dict/只', '提取/只', '池ms/只'))
for r in rows[-10:]:
    p = r['pool'] or 1
    print('%-9s %5d %5d %6d %6d %7.0f %7.2f %7.2f %7.1f' % (
        r['tm'][-8:], r['tot'], r['ok'], r['acc'], r['pool'], r['par'],
        r['td'] * 1000 / p, r['ex'] * 1000 / p, r['par'] * 1000 / p))

# 再按 本轮新取(ok) 口径算一遍，看哪个口径更稳定
print('\n若按【本轮新取 ok】折:')
print('%-9s %5s %7s %7s %7s' % ('时刻', '本轮', '转dict/只', '提取/只', '解析/只'))
for r in rows[-10:]:
    o = r['ok'] or 1
    print('%-9s %5d %7.2f %7.2f %7.1f' % (
        r['tm'][-8:], r['ok'], r['td'] * 1000 / o, r['ex'] * 1000 / o, r['par'] * 1000 / o))
