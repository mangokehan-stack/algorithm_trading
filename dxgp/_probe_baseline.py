# -*- coding: utf-8 -*-
"""V2.6.124 准备: 实测探针基线

为什么必须先跑这个:
  _patch_v26123.py 里写的 "本地0.02秒 / 0.01秒" 是【估值】。
  估值一旦偏 2 倍, 日志里那个"慢N倍"就会偏 2 倍, 而这条日志的全部意义
  就在于那个倍差 —— 基线错了整条结论就废了。

  所以先在本机(与外接 QMT 同一台机器、同一批 Python)实测同款探针,
  拿到真实基线, 再写进母版文案。

注意: 本地 CPython 与 QMT 内嵌解释器版本可能不同, 结论里要标注这一点,
  但量级(毫秒 vs 秒)是可靠的, 足以判断 823 倍是环境还是算法。
"""
import time
import sys

R_LOOP = 300000
R_DICT = 100000
R_CLOCK = 20000


def bench(repeat=5):
    loops, dicts, clocks = [], [], []
    for _k in range(repeat):
        t0 = time.time()
        a = 0
        for i in range(R_LOOP):
            a += i & 7
        loops.append(time.time() - t0)

        t0 = time.time()
        d = {}
        for i in range(R_DICT):
            d[i & 255] = i
        dicts.append(time.time() - t0)

        t0 = time.time()
        for i in range(R_CLOCK):
            c = time.time()
        clocks.append(time.time() - t0)
    # 取中位数, 避开偶尔被系统打断的那次
    loops.sort()
    dicts.sort()
    clocks.sort()
    mid = repeat // 2
    return loops[mid], dicts[mid], clocks[mid], loops, dicts, clocks


if __name__ == '__main__':
    print('Python', sys.version.replace('\n', ' '))
    print('平台', sys.platform)
    lp, dp, cp, lall, dall, call = bench()
    print('')
    print('中位数读数:')
    print('  空循环 %d 次 = %.4f 秒  (%.3f us/次)' % (R_LOOP, lp, lp / R_LOOP * 1e6))
    print('  dict   %d 次 = %.4f 秒  (%.3f us/次)' % (R_DICT, dp, dp / R_DICT * 1e6))
    print('  clock  %d 次 = %.4f 秒  (%.3f us/次)' % (R_CLOCK, cp, cp / R_CLOCK * 1e6))
    print('')
    print('波动: 空循环 %s' % ['%.4f' % x for x in lall])
    print('      dict     %s' % ['%.4f' % x for x in dall])
    print('      clock    %s' % ['%.4f' % x for x in call])
    print('')
    # 建议写进母版的基线: 取中位数保留 3 位, 避免过度精确
    print('=> 建议基线常量: _PB_LOOP_BASE=%.3f  _PB_DICT_BASE=%.3f  _PB_CLOCK_BASE=%.3f'
          % (lp, dp, cp))
