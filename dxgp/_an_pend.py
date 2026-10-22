# -*- coding: utf-8 -*-
"""正确口径: 探针在 _t_bt 之外，故探针耗时落在 _dt_pend(解析其他) 内"""

cases = [
    # 时刻, 池, 解析, 转dict, 提取, 解其他(=pend), 采样n, 均摊秒/次
    ('18:11:01', 3000, 330.0, 159.5, 130.2, 40.3, 75, 0.5369),
    ('18:24:01', 4800, 390.0, 190.6, 130.3, 69.3, 120, 0.5772),
]

print('校验: 解析总 == 转dict + 提取 + 解析其他 ?')
for t, pool, par, td, ex, po, n, av in cases:
    print('  %s: %.1f + %.1f + %.1f = %.1f  vs 解析 %.0f  -> %s'
          % (t, td, ex, po, td + ex + po, par,
             'OK' if abs(td + ex + po - par) < 0.6 else '不符'))

print()
print('%-9s %6s %8s %8s %10s %10s %8s' % (
    '时刻', '池', '解析其他', '探针占用', 'PEND里纯应用', '转dict/只', '提取/只'))
for t, pool, par, td, ex, po, n, av in cases:
    probe = av * n
    pend_app = po - probe
    print('%-9s %6d %8.1f %10.1f %10.1f %10.2f %9.2f' % (
        t, pool, po, probe, pend_app, td * 1000 / pool, ex * 1000 / pool))

print()
print('=== 结论: 三段实测之和 == 解析总，探针被算进"解析其他" ===')
print('故 18:11 的 "转dict159.5+提取130.2" 是【不含探针】的真实应用耗时')
print('    每只成本: 转dict %.2f ms + 提取 %.2f ms = %.2f ms'
      % (159.5 * 1000 / 3000, 130.2 * 1000 / 3000,
         (159.5 + 130.2) * 1000 / 3000))
print('    18:24: 转dict %.2f + 提取 %.2f = %.2f ms'
      % (190.6 * 1000 / 4800, 130.3 * 1000 / 4800,
         (190.6 + 130.3) * 1000 / 4800))
