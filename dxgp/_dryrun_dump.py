# -*- coding: utf-8 -*-
"""V2.6.134 落盘诊断: 真渲染一次 % 格式串, 并模拟截断路径

记忆 6.5: % 格式串必须真渲染一次 —— 写错实参个数/类型时 compile 完全无感,
运行期 TypeError 还会被 try 吞掉。

这里把落盘函数里新增的三段【逐字重写】成独立可运行形态:
  (a) _n_scanned += 1 的自增路径
  (b) _hit_cap = True 的截断路径
  (c) _tail 拼接的 % 渲染
并断言: 未渲染的占位符不残留, 数字与场景自洽。
"""
import ast

P = 'zt_shrink_strategy_gbk.py'
src = open(P, 'rb').read().decode('gbk')

# ---- 先确认母版里这三段的真实形态 ----
for key in ['_n_scanned = 0', '_hit_cap = False', '_hit_cap = True',
            '_n_scanned += 1', "_tail += (' [3秒截断: 已扫%d/%d只 已用%.1f秒]'"]:
    assert key in src, '母版缺: %s' % key
print('母版落点全部存在')

# ---- 取出 _tail 拼接那段的完整源码, 校验实参个数 ----
tree = ast.parse(src)
seg = None
i = src.index("if _hit_cap:")
j = src.index("if _n_reparse > 0:", i)
seg = src[i:j].replace('\r\n', '\n')
print('\n母版截断标注源码:')
print(seg)

# 实参个数校验: %d %d %.1f 共 3 个占位符
n_ph = seg.count('%d') + seg.count('%.1f') + seg.count('%s')
print('占位符个数 %d' % n_ph)
assert n_ph == 3, '占位符应为 3, 实际 %d' % n_ph
# 实参元组
n_arg = seg.count('% (_n_scanned, _n_pool, time.time() - _t0)')
assert n_arg == 1, '实参元组应出现 1 次, 实际 %d' % n_arg
print('实参元组与占位符个数一致 PASS')

# ---- 真渲染: 三种场景 ----
def render(n_scanned, n_pool, elapsed):
    _tail = ' (仅%d/%d只, 余下下轮续写)' % (min(n_scanned, n_pool), n_pool)
    _tail += (' [3秒截断: 已扫%d/%d只 已用%.1f秒]'
              % (n_scanned, n_pool, elapsed))
    return _tail


CASES = [
    ('正常截断: 4800 只池, 扫了 203 只', 203, 4800, 3.00),
    ('整轮未截断也不会打(守卫为假)', 4800, 4800, 2.99),
    ('小池子被截断', 50, 120, 3.01),
    ('极端: 一只都没扫到就截断', 0, 4800, 3.02),
]
print('\n真渲染结果:')
for name, ns, np_, el in CASES:
    out = render(ns, np_, el)
    # 断言 1: 未渲染的占位符不残留(注意: 不能写 '%' not in out, 文案自带百分号)
    ok_ph = ('%.' not in out and '%d' not in out and '%s' not in out)
    # 断言 2: 数字自洽 —— 标注里的数必须等于输入
    ok_num = ('已扫%d/%d只' % (ns, np_)) in out
    ok_sec = ('已用%.1f秒' % el) in out
    print('  %-32s -> %s' % (name, out))
    print('     占位符残留=%s 数字自洽=%s 秒数自洽=%s'
          % (not ok_ph, ok_num, ok_sec))
    assert ok_ph and ok_num and ok_sec, '渲染不自洽: %s' % name

# ---- 模拟落盘循环: 计数是否真在 break 之前自增 ----
print('\n模拟落盘循环(池 10 只, 每只 0.35 秒, 3.0 秒上限):')


class FakeClock(object):
    def __init__(self):
        self.t = 0.0

    def time(self):
        return self.t


def simulate(n_pool, per=0.35, cap=3.0, break_at=None):
    _n_scanned = 0
    _hit_cap = False
    _ser = {}
    t0 = 0.0
    now = 0.0
    for k in range(n_pool):
        now = k * per
        if (now - t0) > cap:
            _hit_cap = True
            break
        _ser['c%d' % k] = [1.0, 1.0]
        _n_scanned += 1
    return _n_scanned, _hit_cap, len(_ser), now


ns, hc, nser, el = simulate(10)
print('  扫了 %d 只 / 存入 %d 只 / 截断标记=%s / 已用 %.2f 秒'
      % (ns, nser, hc, el))
print('  期望: 3.0 秒 / 0.35 = 8.57 -> 第 9 只(k=8, now=2.80)仍可, k=9 now=3.15 截断')
print('  即 _n_scanned 应为 9(不是 8 —— 被 break 那只之前已计过 8 次,')
print('     break 发生在第 10 只, 故 9 次自增全部完成)')
assert ns == 9, '扫描计数应为 9, 实际 %d' % ns
assert hc is True, '应触发截断'
assert nser == 9, '存入应与扫描一致'
print('  计数与截断自洽 PASS')

print('\n干跑总结: PASS')
