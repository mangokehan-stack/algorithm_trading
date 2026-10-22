# -*- coding: utf-8 -*-
"""V2.6.93 专项单测(独立执行, 不依赖 QMT 环境)

三项全是日志可读性, 所以测试也全部对着"日志文案"断言, 不看代码长相:
  T1 异常压缩        —— RemoteDisconnected(...) 只留类名, 不再切成半句
  T2 长文本兜底      —— 拿不到类名才截断, 且带 "..." 结尾
  T3 空异常          —— None/空串 -> '失败'(不能让日志出现空白)
  T4 覆写人话        —— panic 档输出 0.5->0.3 / 30->45, 含方向说明
  T5 无覆写          —— 空 dict 返回空串(不得打 "参数覆写: ")
  T6 未知键          —— 不隐藏, 原样输出并注明未收录
  T7 预算告警实跑    —— 用源码里的真实代码块 + 桩时间跑, 断言 4批/均49秒/慢24倍
  T8 预算告警解释    —— 必须写明"批间检查/不可中断", 否则 195>180 像算错
  T9 两条排雷告警    —— 副本行不得再带错误串, 且必须自称副本
  T10 _nb_ok 位置    —— 只在批循环外初始化 1 次
  T11 参数指纹       —— 仍为 8a4ab7e8(只改日志不改参数)
  T12 铁律           —— stop_order 0 / NEVER_STOP_LOSS 未动

设计原则(延续 _test_v2688~2692): exec 母版真实代码, 不重写判据。
"""
import contextlib
import io
import os
import re
import textwrap
from types import SimpleNamespace

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
SRC = io.open(P, 'r', encoding='gbk', newline='').read()
FULL = SRC.replace('\r\n', '\n')
# 与 _check_inv.py 同口径: 正文不含"版本号: "开头的版本历史注释行
BODY = '\n'.join(l for l in FULL.split('\n') if not l.startswith('版本号: '))

PASS, FAIL = [], []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))


def load_ns():
    ns = {'__file__': os.path.join(os.environ.get('TEMP', '.'), 'fake_v2693.py'),
          '__name__': 'v2693_probe'}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(BODY, P, 'exec'), ns)
    return ns


NS = load_ns()
SHORT = NS['_risk_src_err_short']
NOTE = NS['_sent_override_note']

# 指纹必须在改 globals 之前算(T11): 下面要给宿主默认参数塞桩值, 会污染指纹
try:
    FP = NS['param_fingerprint']()
    FP = FP[0] if isinstance(FP, tuple) else FP
except Exception as _e:
    FP = 'ERR:%r' % (_e,)

# 模拟宿主默认参数(未覆写时的值), 用于 T4/T5/T6
NS['SHRINK_BUY_RATIO'] = 0.5
NS['BUY_MIN_ELAPSED_MIN'] = 30
NS['EXPAND_SELL_RATIO'] = 2.0

# ---------------------------------------------------------------- T1/T2/T3
c1 = SHORT("RemoteDisconnected('Remote end closed connection without response')")
chk('T1 只留异常类名', c1 == 'RemoteDisconnected', 'got=%r' % c1)
chk('T1 不再出现半句/半个引号', "closed co" not in c1 and "'" not in c1, 'got=%r' % c1)
c2 = SHORT("OSError('timed out')")
chk('T1b 其它异常同样压缩', c2 == 'OSError', 'got=%r' % c2)

c3 = SHORT('连接超时, 对方未响应')
chk('T2 纯文本短句原样保留', c3 == '连接超时, 对方未响应', 'got=%r' % c3)
c4 = SHORT('x' * 80)
chk('T2b 超长文本截断且加省略号', c4.endswith('...') and len(c4) == 43, 'len=%d' % len(c4))
chk('T2c 截断后仍可读(不以半个括号结尾)', not c4.rstrip('.').endswith('('), 'got=%r' % c4)

chk('T3 None -> 失败', SHORT(None) == '失败', repr(SHORT(None)))
chk('T3b 空串 -> 失败', SHORT('') == '失败', repr(SHORT('')))
chk('T3c 空白 -> 失败', SHORT('   ') == '失败', repr(SHORT('   ')))

# ---------------------------------------------------------------- T4/T5/T6
ov = NOTE({'SHRINK_BUY_RATIO': 0.3, 'BUY_MIN_ELAPSED_MIN': 45})
chk('T4 缩量阈值 0.5->0.3', '缩量阈值 0.5->0.3' in ov, 'got=%r' % ov)
chk('T4b 开盘等待 30->45', '开盘等待分钟 30->45' in ov, 'got=%r' % ov)
chk('T4c 带方向说明(更难买)', '越低越严' in ov, 'got=%r' % ov)
chk('T5 无覆写返回空串', NOTE({}) == '', repr(NOTE({})))
chk('T5b None 返回空串', NOTE(None) == '', repr(NOTE(None)))
ov2 = NOTE({'SOME_NEW_KEY': 7})
chk('T6 未知键不隐藏', 'SOME_NEW_KEY 2->7' in ov2 or 'SOME_NEW_KEY' in ov2, 'got=%r' % ov2)
chk('T6b 未知键注明未收录', '未收录的键' in ov2, 'got=%r' % ov2)

# ---------------------------------------------------------------- T7/T8 预算告警
i0 = BODY.index('        if _budget_hit:\n')
# V2.6.99: _budget_hit 告警已挪到"取数完成"行之后(告警不再比完成行早), 块终点改为
#   if _cov['samples']:(告警块内部含退避提示分支)
i1 = BODY.index("        if _cov['samples']:\n", i0)
BLOCK = textwrap.dedent(BODY[i0:i1])
LOGS = []


class FakeTime(object):
    @staticmethod
    def time():
        return 1000.0


ns2 = {'time': FakeTime, '_t_beg': 805.0, '_nb_ok': 4, '_BUDGET_SEC': 180.0,
       '_budget_hit': True,
       '_cov': {'req': 5226, 'ok': 1200, 'fail': 0, 'retry': 0},
       'SENT_STATE': {'bh_streak': 0},  # V2.6.99: 告警块含退避提示分支, 需注入
       '_sent_wlog': lambda s: LOGS.append(s)}
exec(compile(BLOCK, '<budget>', 'exec'), ns2)
msg = LOGS[0] if LOGS else ''
chk('T7 预算告警有输出', len(LOGS) == 1, 'lines=%d' % len(LOGS))
chk('T7b 报批数与批次大小', '4批x300只' in msg, 'got=%r' % msg[:90])
chk('T7c 报均秒每批', '均49秒/批' in msg, 'got=%r' % msg[:90])
chk('T7d 报实际耗时', '实际耗时195秒' in msg, 'got=%r' % msg[:90])
chk('T7e 报相对常态倍数', '本轮慢24倍' in msg, 'got=%r' % msg[:90])
chk('T7f 报放弃只数', '余下4026只' in msg, 'got=%r' % msg[:90])
chk('T8 解释 195>180 的原因', '预算只在批间检查' in msg and '不可中断' in msg, '')

# 零批次的极端情形: 不能在除零处炸掉, 也不能打出 nan
LOGS2 = []
ns3 = dict(ns2)
ns3['_nb_ok'] = 0
ns3['_sent_wlog'] = lambda s: LOGS2.append(s)
exec(compile(BLOCK, '<budget>', 'exec'), ns3)
m2 = LOGS2[0] if LOGS2 else ''
chk('T7g 零批次不崩且无 nan', ('nan' not in m2.lower()) and '0批' in m2, 'got=%r' % m2[:80])

# ---------------------------------------------------------------- T9 两条排雷告警
i2 = BODY.index("log('[排雷][告警] 清单生成时%d类数据源失败")
i3 = BODY.index('elif _src_errs:', i2)
SEG = BODY[i2:i3]
chk('T9 主告警仍带具体数据源名', '%s ——' in SEG or '类数据源失败: %s' in SEG, '')
chk('T9b 副本行自称副本', '本条是上一行日志的推送副本' in SEG, '')
chk('T9c 副本行不再重复错误串', SEG.count('_bdet') <= 2, 'count=%d' % SEG.count('_bdet'))
chk('T9d 旧裸截断已清除', "get('err') or '失败')[:40]" not in BODY, '')
chk('T9e 主告警走压缩函数', "_risk_src_err_short((_src.get(k) or {}).get('err'))" in BODY, '')

# ---------------------------------------------------------------- T10 _nb_ok
chk('T10 _nb_ok 只初始化一次', BODY.count('_nb_ok = 0') == 1,
    'count=%d' % BODY.count('_nb_ok = 0'))
chk('T10b 初始化早于批循环',
    BODY.index('_nb_ok = 0') < BODY.index('for _attempt in (0, 1):'), '')
chk('T10c 每批 +1 只一处', BODY.count('_nb_ok += 1') == 1,
    'count=%d' % BODY.count('_nb_ok += 1'))
chk('T10d 未新增模块级大写常量', 'RISK_SRC_ERR' not in BODY and 'SENT_BUDGET' not in BODY, '')

# ---------------------------------------------------------------- T11/T12
chk('T11 参数指纹仍 8a4ab7e8', FP == '8a4ab7e8', 'got=%s' % FP)
chk('T12 止损单仍为 0', BODY.count('stop_order') == 0, '')
chk('T12b 绝不止损开关未动', 'NEVER_STOP_LOSS = True' in BODY, '')
def _ver(s):
    return tuple(int(x) for x in re.findall(r'\d+', s)[:3])
_v = re.search(r"VERSION = '([^']+)'", BODY)
_cur = _ver(_v.group(1)) if _v else (0, 0, 0)
# 版本号会一直往上走, 这里只保证"不早于本测试诞生时的 V2.6.93", 避免每次升版都要改测试
chk('T12c VERSION 不早于 V2.6.93', _cur >= (2, 6, 93), 'got=%s' % (_v.group(1) if _v else '?'))

print('\n%d/%d PASS' % (len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print('FAILED: %s' % FAIL)
    raise SystemExit(1)
