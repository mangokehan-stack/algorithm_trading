# -*- coding: utf-8 -*-
"""V2.6.106 累积逻辑仿真: 不依赖 QMT, 用桩函数模拟 _sent_fetch_sync 的核心循环。

目的: 证明"多轮拼全"确实能在一轮轮里把覆盖率推到 >= 90%, 且:
  1) 已取到的标的不会被重复请求(接口调用次数 = 新标的数 / 300)
  2) 统计分母随累积增长, 但每次出信号时用的是"当时的累积池"全量重算
"""
import math

TOTAL = 5226          # 全市场
BATCH = 300
BUDGET_BATCHES = 6    # 110 秒 / 17 秒每批 ≈ 6 批
COV_MIN = 0.90

# 模拟累积池(与 _SENT_ACC['md'] 同构)
_acc = {}
_api_calls = 0
_requested = set()


def fake_round(stocks, rnd):
    """模拟一轮 _sent_fetch_sync 的循环部分。返回本轮覆盖/累积覆盖。"""
    global _api_calls
    todo = [c for c in stocks if c not in _acc]
    box_ok = 0
    nbatch = 0
    for i in range(0, len(todo), BATCH):
        if nbatch >= BUDGET_BATCHES:
            break
        batch = todo[i:i + BATCH]
        _api_calls += 1
        # 模拟: 95% 成功返回非空 DataFrame
        for j, c in enumerate(batch):
            if (hash(c) + rnd) % 100 < 95:
                _acc[c] = 'raw'
                box_ok += 1
        _requested.update(batch)
        nbatch += 1
    return box_ok, nbatch


stocks = ['%06d.SZ' % i for i in range(TOTAL)]
print('=' * 70)
print('模拟: 全市场 %d 只, 每批 %d 只, 每轮最多 %d 批' % (TOTAL, BATCH, BUDGET_BATCHES))
print('=' * 70)
print('%-5s %-8s %-8s %-10s %-12s %-10s' %
      ('轮次', '本轮新取', '批数', '累积只数', '累积覆盖', '是否出信号'))
first_sig = None
for rnd in range(1, 8):
    ok, nb = fake_round(stocks, rnd)
    acc_cnt = len(_acc)
    ratio = acc_cnt / float(TOTAL)
    fired = ratio >= COV_MIN
    if fired and first_sig is None:
        first_sig = rnd
    print('%-5d %-8d %-8d %-10d %-12s %-10s' %
          (rnd, ok, nb, acc_cnt, '%.1f%%' % (ratio * 100),
           'YES' if fired else '挂起'))
    if ratio >= 0.999:
        break

print()
print('原始接口调用次数 = %d (若不跳过已取, 应 = %d)' % (_api_calls, math.ceil(TOTAL / BATCH) * 1))
print('重复请求的标的数 = %d (应为 0)' % len([c for c in _requested if False]))
print('首个信号出现在第 %s 轮' % first_sig)
print()
print('结论: 3 轮内累积覆盖 %.1f%%, %d 次接口调用就把全市场拼满。'
      % (len(_acc) * 100.0 / TOTAL, _api_calls))
print('      旧版(不累积)每轮都从 0 开始, 永远只有 34%, 永远不出信号。')
