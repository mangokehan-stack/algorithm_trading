# -*- coding: utf-8 -*-
"""交叉核对: 生产 53ms/只 vs 本机 0.036ms/只 的差距，能否用"跨COM"解释？

关键: _df_to_rows 里 df[c].values 每列都要跨一次 COM 边界。
QMT 的 DataFrame 不是本地 pandas 对象，每次属性访问都可能是一次 COM 调用。
"""

# 本机实测
local_ms = 0.0356          # 纯 Python 模拟（无 COM）

# 生产实测
prod = [
    ('18:11:01', 3000, 53.17, 43.40),
    ('18:24:01', 4800, 39.71, 27.15),
]

print('本机纯 Python: %.4f ms/只' % local_ms)
print()
print('%-9s %6s %10s %10s %10s %10s' % (
    '时刻', '池', '转dict/只', '提取/只', '合计/只', '倍差(合计/本机)'))
for t, pool, td, ex in prod:
    tot = td + ex
    print('%-9s %6d %10.2f %10.2f %10.2f %10.0f' % (
        t, pool, td, ex, tot, tot / local_ms))

print()
print('=== 若瓶颈是"每列一次跨 COM"，估算单次跨 COM 成本 ===')
# _df_to_rows: vals = [df[c].values for c in cols] -> 2 次跨 COM（只取 2 列时）
# 实际 QMT 返回约 10 列，但 cols 只有 2 个，所以 2 次
for t, pool, td, ex in prod:
    print('%s: 转dict %.1f ms/只 / 2 次跨COM = %.1f ms/次' % (t, td, td / 2.0))

print()
print('=== 若按 QMT 返回 10 列全访问（旧版 _df_to_rows 写法）===')
for t, pool, td, ex in prod:
    print('%s: 转dict %.1f ms/只 / 10 次 = %.1f ms/次' % (t, td, td / 10.0))

print()
print('=== 提取段的每只成本（纯 Python 循环，无 COM）===')
for t, pool, td, ex in prod:
    print('%s: 提取 %.2f ms/只  vs 本机同类循环约 0.02ms -> 倍差 %.0f'
          % (t, ex, ex / 0.02))
