# -*- coding: utf-8 -*-
u"""V2.6.97 专项单测(独立执行, 不依赖 QMT 环境)

用户回"先让我把 ②③④ 改完", 三项全只改日志:
  T1 元数据        —— VERSION / 版本头 / 全 CRLF / 行数
  T2 优选截断留痕   —— 真跑截断代码块: 4只->2只时落选 2 只必须各有日志(本次核心)
  T3 日志顺序      —— 落选日志必须在切片之前(切片后对象就没了)
  T4 下载耗时      —— 完成行带耗时/均速, 非完成行不带; dl_t0 是 G 属性不是模块常量
  T5 公告缺口量化   —— ann>0 推算 / ann=0 明示未采到(覆盖在 _test_v2692 T8/T8b)
  T6 铁律与指纹    —— stop_order 0 / NEVER_STOP_LOSS 未动 / Thread 1 / _api 52 / 参数指纹不变

设计原则(延续 _test_v2688~2696): exec 母版真实代码块, 不重写判据。
"""
import io
import os
import re
import sys
import textwrap

P = 'zt_shrink_strategy_gbk.py'
_raw = io.open(P, 'rb').read()
SRC = _raw.decode('gbk')
FULL = SRC.replace('\r\n', '\n')
LINES = SRC.split('\r\n')
BODY = '\n'.join(l for l in FULL.split('\n') if not l.startswith(u'版本号: '))

PASS, FAIL = [], []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))


# ---------------------------------------------------------------- T1 元数据
print('=== T1 元数据 ===')
m = re.search(r"VERSION\s*=\s*'(V2\.6\.\d+)'", SRC)
_vt = tuple(int(x) for x in m.group(1)[1:].split('.')) if m else (0,)
chk('T1.1 VERSION>=V2.6.97', _vt >= (2, 6, 97), m.group(1) if m else '?')
chk('T1.2 版本头首条为 V2.6.x', LINES[4].startswith(u'版本号: V2.6.'), LINES[4][:44])
chk('T1.3 上一版记录仍在(V2.6.96)', any(l.startswith(u'版本号: V2.6.96') for l in LINES[5:12]))
chk('T1.4 全 CRLF 无裸 LF', SRC.count('\r\n') == SRC.count('\n'),
    'CRLF=%d LF=%d' % (SRC.count('\r\n'), SRC.count('\n')))
chk('T1.5 行数>=12597', len(LINES) >= 12597, 'actual=%d' % len(LINES))

# ---------------------------------------------------------------- T2 优选截断留痕
print('=== T2 优选截断留痕(真跑代码块) ===')
i0 = FULL.index(u'    total = len(G.candidates)')
i1 = FULL.index(u'        G.candidates = G.candidates[:MAX_DAILY_PICKS]', i0)
i1 = FULL.index('\n', i1) + 1
# V2.6.98: 落选打印已挪到优选行之后, 截断块继续取到 else 分支结束
_i_else = FULL.index(u'        _rej = []', i1)
i1 = FULL.index('\n', _i_else) + 1
BLOCK = textwrap.dedent(FULL[i0:i1])
# V2.6.98: 落选循环单独抽出来, 与截断块拼成一段可执行代码(母版里两者已不相邻)
_r0 = FULL.index(u'    for _rlc in _rej:')
_r1 = FULL.index(u'\ndef rescreen_if_needed', _r0)
REJ = textwrap.dedent(FULL[_r0:_r1])
CODE = BLOCK + '\n' + REJ
chk('T2.0 截断块只存不打印', u'_rej = list(' in BLOCK and u'落选(超出每日优选上限' not in BLOCK)
chk('T2.0b 落选循环已抽出且含打印格式',
    u'落选(超出每日优选上限' in REJ and u'第%d天' in REJ)


class _G(object):
    candidates = []


def run_trunc(rows, picks=2):
    logs = []
    g = _G()
    g.candidates = [dict(x) for x in rows]
    ns = {'G': g, 'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
          'MAX_DAILY_PICKS': picks}
    exec(compile(CODE, '<trunc>', 'exec'), ns)
    return logs, g


ROWS = [
    {'stock': '001299.SZ', 'name': u'美能能源', 'shrink_rank': 0.48, 'pullback': 0.035, 'offset': 4},
    {'stock': '002549.SZ', 'name': u'凯美特气', 'shrink_rank': 0.51, 'pullback': 0.079, 'offset': 5},
    {'stock': '600001.SH', 'name': u'甲', 'shrink_rank': 0.72, 'pullback': 0.120, 'offset': 3},
    {'stock': '600002.SH', 'name': u'乙', 'shrink_rank': 0.90, 'pullback': 0.050, 'offset': 6},
]
lg, g = run_trunc(ROWS, picks=2)
chk('T2.1 落选 2 只各一条日志', len(lg) == 2, repr(lg))
chk('T2.2 落选的是量比大的两只', all('0.72' in x or '0.90' in x for x in lg), repr(lg))
chk('T2.3 日志含上限只数', all(u'超出每日优选上限2只' in x for x in lg), repr(lg[:1]))
chk('T2.4 日志含量比/回撤/第N天',
    any(u'昨量/基准量=0.72' in x and u'昨收回撤=12.0%' in x and u'第3天' in x for x in lg), repr(lg))
chk('T2.5 保留的是量比最小的两只',
    [c['stock'] for c in g.candidates] == ['001299.SZ', '002549.SZ'],
    repr([c['stock'] for c in g.candidates]))
chk('T2.6 优选表未被打乱(仍按量比升序)',
    [round(c['shrink_rank'], 2) for c in g.candidates] == [0.48, 0.51],
    repr([c['shrink_rank'] for c in g.candidates]))


class _G2(object):
    candidates = []


def run_keep(rows, picks=2):
    logs = []
    g = _G2()
    g.candidates = [dict(x) for x in rows]
    ns = {'G': g, 'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
          'MAX_DAILY_PICKS': picks}
    exec(compile(CODE, '<trunc>', 'exec'), ns)
    return logs, g


lg3, g3 = run_keep(ROWS[:3], picks=2)
chk('T2.7 3只->落选1只', len(lg3) == 1 and '0.90' not in lg3[0], repr(lg3))
lg1, g1 = run_keep(ROWS[:2], picks=2)
chk('T2.8 恰好2只(等于上限)不打落选', lg1 == [], repr(lg1))
lg0, g0 = run_keep([], picks=2)
chk('T2.9 空候选不炸', lg0 == [], repr(lg0))

# ---------------------------------------------------------------- T3 日志顺序
print('=== T3 日志顺序(落选改到优选行之后) ===')
chk('T3.1 落选打印在优选行之后', FULL.index(u'    for _rlc in _rej:')
    > FULL.index(u'第%d优先'))
chk('T3.2 切片仍在漏斗之前(漏斗按截断前 total 报账)',
    FULL.index('G.candidates = G.candidates[:MAX_DAILY_PICKS]')
    < FULL.index(u'选股漏斗(顺序与代码一致)'))
chk('T3.3 _rej 在切片之前赋值', FULL.index(u'_rej = list(')
    < FULL.index('G.candidates = G.candidates[:MAX_DAILY_PICKS]'))

# ---------------------------------------------------------------- T4 下载耗时
print('=== T4 下载完成行耗时 ===')
j0 = FULL.index(u'        _bucket = G.dl_i // 2000')
_mj = re.search(r'\n {8}if G\.dl_i >= _u_tot:', FULL[j0:])
assert _mj, '未找到下载进度块结束位置'
DL = textwrap.dedent(FULL[j0:j0 + _mj.start() + 1])
chk('T4.0 代码块含耗时格式串', u'耗时%d秒 均速%.1f只/秒' in DL)


class _Clk(object):
    t = 1000.0

    def time(self):
        return self.t


def run_dl(dl_i, total, mark=-1):
    logs = []

    class G(object):
        pass

    g = G()
    g.dl_i = dl_i
    g.dl_t0 = 214.0
    if mark is not None:
        g.dl_mark = mark
    ns = {'G': g, 'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
          '_u_tot': total, 'time': _Clk(), '_f': lambda x: float(x or 0)}
    exec(compile(DL, '<dl>', 'exec'), ns)
    return logs, g


lgd, _gd = run_dl(5226, 5226)
chk('T4.1 完成行带耗时786秒', len(lgd) == 1 and u'耗时786秒' in lgd[0], repr(lgd))
chk('T4.2 均速=5226/786≈6.6', u'均速6.6只/秒' in lgd[0], repr(lgd))
lgd2, _ = run_dl(250, 5226)
chk('T4.3 非完成行不带后缀', lgd2 == [u'下载进度 250 / 5226'], repr(lgd2))
lgd3, _ = run_dl(4000, 5226, 0)
chk('T4.4 跨桶非完成行不带后缀', lgd3 == [u'下载进度 4000 / 5226'], repr(lgd3))
chk('T4.5 dl_t0 是 G 属性而非模块级常量(不影响参数指纹)',
    'G.dl_t0 = time.time()' in BODY and 'DL_T0' not in BODY)

# ---------------------------------------------------------------- T5 公告缺口
print('=== T5 公告缺口量化 ===')
chk('T5.1 两条分支都在', u'同比推算%d天满覆盖约%d只' in BODY
    and u'ann类0只(该类可能完全未采到, 不等于无风险)' in BODY)
chk('T5.2 旧文案"未达%d天窗口"已移除', u'未达%d天窗口' not in BODY)
chk('T5.3 覆盖百分比已打出', u'仅覆盖%d天窗口的%.0f%%' in BODY)

# ---------------------------------------------------------------- T6 铁律与指纹
print('=== T6 铁律与指纹 ===')
chk('T6.1 正文 stop_order 0 次', BODY.count('stop_order') == 0, BODY.count('stop_order'))
chk('T6.2 NEVER_STOP_LOSS 未动', 'NEVER_STOP_LOSS = True' in BODY)
chk('T6.3 threading.Thread 仍1处', BODY.count('threading.Thread(') == 1, BODY.count('threading.Thread('))
chk('T6.4 _api( 仍52次', BODY.count('_api(') == 52, BODY.count('_api('))
chk('T6.5 本次未新增全局大写常量', 'DL_T0' not in BODY and 'RISK_EXCLUDE_ANN' not in BODY)

try:
    import contextlib
    _ns = {'__file__': os.path.join(os.getcwd(), 'fake_probe.py'), '__name__': 'v2697_probe'}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(SRC, P, 'exec'), _ns)
    _fp_raw = _ns['param_fingerprint']()
    # param_fingerprint() 返回 (指纹, 明细串) 二元组, 第一个才是 8 位 hex
    _fp = _fp_raw[0] if isinstance(_fp_raw, (tuple, list)) else _fp_raw
except Exception as _e:
    _fp = 'ERR:%s' % _e
chk('T6.6 参数指纹仍 8a4ab7e8', _fp == '8a4ab7e8', 'got=%r' % (_fp,))

print('\n========== %d PASS / %d FAIL ==========' % (len(PASS), len(FAIL)))
if FAIL:
    print('FAILED: %r' % (FAIL,))
    sys.exit(1)
print('ALL GREEN')
