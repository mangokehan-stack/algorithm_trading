# -*- coding: utf-8 -*-
"""核心核算: 解析段是不是每轮把累积池重新解析得 N 遍"""

# 18:02 那轮（pid 7908，启动 17:25，池 3000，累积覆盖 57.4%）
# 18:15 那轮（同进程，池 4800，累积覆盖 91.8%）

cases = [
    # (时刻, 累积池只数, 解析秒, 转dict, 提取, 解析其他, 采样次数)
    ('18:11:01', 3000, 330.0, 159.5, 130.2, 40.3, 75),
    ('18:24:01', 4800, 390.0, 190.6, 130.3, 69.3, 120),
]

print('%-9s %6s %7s %8s %8s %8s %8s %10s' % (
    '时刻', '池', '解析', '转dict', '提取', '解其他', '采样', '只/采样'))
for t, pool, par, td, ex, po, n in cases:
    print('%-9s %6d %7.0f %8.1f %8.1f %8.1f %8d %10.1f' % (
        t, pool, par, td, ex, po, n, pool * 1.0 / n))

print()
print('=== 关键比值 ===')
for t, pool, par, td, ex, po, n in cases:
    print('%s: 转dict/只=%.2f ms, 提取/只=%.2f ms, 解析其他/只=%.2f ms, 解析总/只=%.1f ms'
          % (t, td * 1000 / pool, ex * 1000 / pool, po * 1000 / pool, par * 1000 / pool))

print()
print('=== 池从 3000 涨到 4800（x%.2f），各段涨幅 ===' % (4800 / 3000.0))
a, b = cases[0], cases[1]
for name, i in (('解析总', 2), ('转dict', 3), ('提取', 4), ('解其他', 5), ('采样次数', 6)):
    print('  %-8s %8.1f -> %8.1f  = x%.2f' % (name, a[i], b[i], b[i] / a[i]))

print()
print('=== 每采样只数（探针每 40 只采一次，故 采样次数 x40 = 实际遍历只数）===')
for t, pool, par, td, ex, po, n in cases:
    print('%s: 采样%d次 -> 推算遍历 %d 只；日志池 %d 只' % (t, n, n * 40, pool))

print()
print('=== 若遍历只数 = 池 x K，反推 K ===')
for t, pool, par, td, ex, po, n in cases:
    print('%s: K = %d/%d = %.2f' % (t, n * 40, pool, n * 40.0 / pool))
