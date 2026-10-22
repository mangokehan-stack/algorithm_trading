import io, re, collections
from datetime import datetime

files = ['gf_native_trade.log.1', 'gf_native_trade.log']
ev = []
for f in files:
    with io.open(f, 'r', encoding='utf-8', errors='replace', newline='') as fh:
        for ln in fh:
            m = re.match(r'\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] (.*)', ln.rstrip('\r\n'))
            if m:
                ev.append((datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S'), m.group(2)))
ev.sort(key=lambda x: x[0])

# 只统计连续竞价时段（09:30~11:29 / 13:00~14:59）内的事件
def trading(t):
    hms = int(t.strftime('%H%M%S'))
    return (93000 <= hms <= 112959) or (130000 <= hms <= 145959)

print('=' * 74)
print('【A】连续竞价时段内，按分钟统计「行情取数类」条目')
print('=' * 74)
print('%-7s %-6s %-6s %-7s %-6s %-6s' % ('分钟', '情绪', 'F2拦截', '心跳', '诊断', '合计'))
per = collections.OrderedDict()
for t, msg in ev:
    if not trading(t):
        continue
    k = t.strftime('%H:%M')
    d = per.setdefault(k, collections.Counter())
    if '情绪 |' in msg:      d['emo'] += 1
    elif 'F2大盘' in msg:    d['f2'] += 1
    elif '存活打点' in msg:  d['hb'] += 1
    elif '半时诊断' in msg:  d['dg'] += 1
    d['all'] += 1
for k, d in per.items():
    print('%-7s %-6d %-6d %-7d %-6d %-6d' % (k, d['emo'], d['f2'], d['hb'], d['dg'], d['all']))

# 关键：真实取数频率 = 情绪行（每 bar 都会评估情绪，但日志节流）
print()
print('=' * 74)
print('【B】逐 bar 实锤：F2 拦截行间隔（每 bar 都打印，= bar 间隔）')
print('=' * 74)
f2 = [(t, m) for t, m in ev if 'F2大盘' in m]
prev = None
rows = []
for t, m in f2:
    g = (t - prev).total_seconds() if prev else None
    rows.append((t, g))
    prev = t
for t, g in rows:
    print('  %s  间隔=%s' % (t.strftime('%H:%M:%S'), ('%.0fs' % g) if g else '—'))
gs = [g for t, g in rows if g and g < 600]
if gs:
    gs_s = sorted(gs)
    print('  >>> 有效样本 %d 个（剔除停启间隔）：min=%.0f 中位=%.0f max=%.0f 均值=%.1f'
          % (len(gs), gs_s[0], gs_s[len(gs_s)//2], gs_s[-1], sum(gs)/len(gs)))
    print('  >>> 折算 bar 频率 %.2f 根/分钟  → 若每根都真取数则 %.2f 次/分钟' % (60.0/(sum(gs)/len(gs)), 60.0/(sum(gs)/len(gs))))

print()
print('=' * 74)
print('【C】情绪行间隔（日志节流后的展示频率，不代表取数频率）')
print('=' * 74)
emo = [t for t, m in ev if '情绪 |' in m]
prev = None
egs = []
for t in emo:
    g = (t - prev).total_seconds() if prev else None
    print('  %s  间隔=%s' % (t.strftime('%H:%M:%S'), ('%.0fs' % g) if g else '—'))
    if g and g < 600:
        egs.append(g)
    prev = t
if egs:
    print('  >>> 剔除重启间隔后：样本 %d  均值 %.0fs  中位 %.0fs' % (len(egs), sum(egs)/len(egs), sorted(egs)[len(egs)//2]))

# 日线缓存命中率推算：bar 间隔 60s，_HIST_TTL=30s → 每根 bar 必然过期 → 每根重拉
print()
print('=' * 74)
print('【D】_HIST_TTL=30s 与 bar 间隔 60s 的缓存命中推算')
print('=' * 74)
print('  bar 间隔 ≈ 60s  >  _HIST_TTL 30s  →  fetch_hist_fields 每根 bar 必然 MISS，100% 重拉')
print('  单标的每次 = get_full_tick(1) + get_market_data_ex(4字段合并 1 次) + 情绪指数(2次, 60s缓存)')
