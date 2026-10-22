# -*- coding: utf-8 -*-
"""决定性验证: 每只候选票的 _bars_to_dict 到底多贵（本机实测，含构造同形 DataFrame）"""

import time
import random


def make_df(n_days=73, seed=1):
    """构造与 QMT 返回同形的 DataFrame：索引=日期字符串，列=close/preClose"""
    rnd = random.Random(seed)
    idx = ['2026%02d%02d' % (7 + (i // 28), 1 + i % 28) for i in range(n_days)]
    idx = sorted(set(idx))
    data = {'close': [round(10 + rnd.random(), 2) for _ in idx],
            'preClose': [round(10 + rnd.random(), 2) for _ in idx]}
    return idx, data


# --- 1) 纯 Python 模拟 _df_to_rows 的算法（不含 DataFrame）---
def dict_from_cols(cols, idx, vals):
    return dict(zip(idx, [dict(zip(cols, row)) for row in zip(*vals)]))


def bench_pure(n_iter=3000, n_days=73):
    idx, data = make_df(n_days)
    cols = ['close', 'preClose']
    vals = [data[c] for c in cols]
    t0 = time.time()
    for _ in range(n_iter):
        rows = dict_from_cols(cols, idx, vals)
        # 模拟 _bars_to_dict 的键规整循环
        out = {}
        for k, v in rows.items():
            sk = str(k)
            dk = sk[:8]
            out[dk] = v
    dt = time.time() - t0
    return dt, n_iter


dt, n = bench_pure()
print('=== 纯 Python 模拟 _bars_to_dict(无 DataFrame) ===')
print('3000 只 x %d 天: %.3f 秒 -> %.4f ms/只'
      % (73, dt, dt * 1000 / n))

# --- 2) pandas DataFrame（真实路径会走 df[c].values，每列一次跨 COM）---
try:
    import pandas as pd
    print()
    print('pandas 版本', pd.__version__)
    idx, data = make_df(73)
    df = pd.DataFrame(data, index=idx)

    # 精确模拟 _df_to_rows
    def df_to_rows(df):
        cols = list(df.columns)
        ix = list(df.index)
        vals = [df[c].values for c in cols]
        return dict(zip(ix, [dict(zip(cols, row)) for row in zip(*vals)]))

    N = 500
    t0 = time.time()
    for _ in range(N):
        r = df_to_rows(df)
    dt2 = time.time() - t0
    print('本地 DataFrame df_to_rows: %d 次 %.3f 秒 -> %.4f ms/只'
          % (N, dt2, dt2 * 1000 / N))

    # 对照: 只取两列的最小写法
    def cheap(df):
        return dict(zip(list(df.index)[:], zip(df['close'].values,
                                              df['preClose'].values)))

    t0 = time.time()
    for _ in range(N):
        r2 = cheap(df)
    dt3 = time.time() - t0
    print('最小写法(直接 zip 两列): %d 次 %.3f 秒 -> %.4f ms/只'
          % (N, dt3, dt3 * 1000 / N))
    print('倍差: %.1f 倍' % (dt2 / dt3 if dt3 else 0))
except ImportError:
    print()
    print('本机无 pandas，跳过 DataFrame 实测')
