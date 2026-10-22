# -*- coding: utf-8 -*-
"""拆解解析耗时: 分离「探针阻塞」与「应用代码」两部分"""

cases = [
    # 时刻, 池, 解析总, 转dict, 提取, 解其他, 采样次数n, 单次最长
    ('18:11:01', 3000, 330.0, 159.5, 130.2, 40.3, 75, 10.0007),
    ('18:24:01', 4800, 390.0, 190.6, 130.3, 69.3, 120, 10.0009),
]

print('%-9s %6s %6s %6s %8s %8s %8s %9s' % (
    '时刻', '池', '解析', '采样n', '阻塞>=1s', '探针合计', '应用段', '应用/只'))
for t, pool, par, td, ex, po, n, mx in cases:
    # 阻塞次数: 集中度 100% 且单次最长贴 10 秒 -> 阻塞次数 = 解析总 / 10 附近，但不准确
    # 用另一条路: 探针合计 = 采样n x 均摊耗时。日志给了均摊倍数。
    # 18:11: 均摊0.5369秒/次 (244.0倍)
    # 18:24: 均摊0.5772秒/次 (262.4倍)。下面按均摊算。
    pass

# 均摊值来自日志
avg = {'18:11:01': 0.5369, '18:24:01': 0.5772}
for t, pool, par, td, ex, po, n, mx in cases:
    probe = avg[t] * n           # 探针占用总时长
    app = par - probe            # 应用代码（转dict+提取+解其他）
    seg = td + ex + po
    print('%-9s %6d %6.0f %6d %8s %8.1f %8.1f %9.1f' % (
        t, pool, par, n, '-', probe, app, app * 1000 / pool))
    print('     三段之和 %.1f vs 应用段 %.1f -> 差 %.1f'
          % (seg, app, seg - app))

print()
print('=== 探针以外的应用段 vs 三段实测之和 ===')
for t, pool, par, td, ex, po, n, mx in cases:
    probe = avg[t] * n
    app = par - probe
    seg = td + ex + po
    print('%s: 解析%.0f - 探针%.1f = 应用%.1f ; 三段实测和%.1f ; 差%+.1f (%.0f%%)'
          % (t, par, probe, app, seg, seg - app, (seg - app) / app * 100))
