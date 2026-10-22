# -*- coding: utf-8 -*-
"""V2.6.89 专项单测(独立执行, 不依赖 QMT 环境)

覆盖用户 2026-10-19 22:59 回"改"的三项:
  T1 双实例告警分档  —— 用真实 heartbeat_tick 源码 + 临时目录伪造同伴心跳文件
  T2 换手率可审计    —— 直接执行母版里那段 log(格式化语句, 验参数顺序/数值落位
  T3 _float_share 异常提示 —— 用真实函数 + 抛异常的桩接口, 验不静默且节流

设计原则(延续 _test_v2688.py): 从母版源码里"抽"真实函数来跑, 不抄公式;
  否则母版改了、测试还按老公式算, 会出现"测试全绿但线上错"的假安全。
"""
import ast
import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import time
from types import SimpleNamespace

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
SRC = io.open(P, 'r', encoding='gbk', newline='').read()
LINES = SRC.split('\r\n')

PASS = []
FAIL = []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))


def func_src(name):
    """按 AST 取函数源码(去缩进), 用于在受控命名空间里执行真实实现。"""
    tree = ast.parse(SRC)
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            body = '\n'.join(LINES[n.lineno - 1:n.end_lineno])
            return textwrap.dedent(body)
    raise AssertionError('函数未找到: %s' % name)


def block(start_pat, end_pat):
    """按首尾锚点取一段源码(含两端), 去缩进。"""
    s = None
    for i, l in enumerate(LINES):
        if start_pat in l:
            s = i
            break
    assert s is not None, start_pat
    for j in range(s, min(s + 30, len(LINES))):
        if end_pat in LINES[j]:
            return textwrap.dedent('\n'.join(LINES[s:j + 1]))
    raise AssertionError('尾锚点未找到: %s' % end_pat)


# ============================================================
# T1 双实例告警分档
# ============================================================
print('=' * 60)
print('T1 双实例告警分档')

HB_SRC = func_src('heartbeat_tick')


def run_hb(peer_age=None, force=True, pre_state=None):
    """在临时目录里跑一次真实 heartbeat_tick; peer_age 秒前写过同伴心跳。"""
    d = tempfile.mkdtemp(prefix='hb89_')
    try:
        own = os.path.join(d, 'zt_shrink_heartbeat_8973786_%d.json' % os.getpid())
        if peer_age is not None:
            with io.open(os.path.join(d, 'zt_shrink_heartbeat_8973786_18792.json'),
                         'w', encoding='utf-8') as f:
                json.dump({'pid': 18792, 'ts': time.time() - peer_age, 'acc': '8973786',
                           'ver': 'V2.6.88', 'boot': time.time() - peer_age - 1}, f)
        logs, push = [], []
        st = {'last_ts': 0.0, 'last_alert_ts': 0.0, 'peer': '', 'boot': 0.0,
              'peer_kind': '', 'last_stale_ts': 0.0}
        if pre_state:
            st.update(pre_state)
        ns = {
            'os': os, 'json': json, 'time': time, 'VERSION': 'V2.6.89',
            'G': SimpleNamespace(accid='8973786'),
            'HEARTBEAT_FILE': 'zt_shrink_heartbeat.json',
            'HEARTBEAT_SEC': 30, 'HEARTBEAT_STALE_SEC': 120, 'HEARTBEAT_ALERT_SEC': 300,
            '_HB_STATE': st,
            'log': logs.append, 'notify_enqueue': push.append,
            'file_base_dir': lambda: d,
            '_split_name': lambda n: (n[:-5], '.json'),
            '_account_suffix': lambda: '_8973786',
            'heartbeat_path': lambda: own,
            '_f': float,
            '_exc_text': lambda e: '%s: %s' % (type(e).__name__, e),
        }
        exec(compile(HB_SRC, '<heartbeat_tick>', 'exec'), ns)
        ns['heartbeat_tick'](force=force)
        return logs, push, st
    finally:
        shutil.rmtree(d, ignore_errors=True)


# T1a 真活着(20 秒前刚跳): 必须喊[告警] + 手机推送带"立即关闭"
logs, push, st = run_hb(peer_age=20)
chk('T1a 活同伴 -> [告警]', any('[安全][告警]' in x for x in logs), str(logs)[:120])
chk('T1a 活同伴 -> 手机推送', len(push) == 1 and '立即关闭' in push[0])
chk('T1a 活同伴 -> peer_kind=live', st.get('peer_kind') == 'live', st.get('peer_kind'))

# T1b 残留(100 秒前, 即 2026-10-19 22:55:28 那一例): 只提示, 不喊立即关闭
logs, push, st = run_hb(peer_age=100)
_txt = ' '.join(logs)
chk('T1b 残留 -> 走[提示]档', any('[安全][提示] 检测到疑似残留心跳' in x for x in logs), _txt[:120])
chk('T1b 残留 -> 日志不出现[告警]', not any('[安全][告警]' in x for x in logs))
chk('T1b 残留 -> 日志不喊"请立即关闭其中一个"',
    '请立即关闭其中一个' not in _txt)
chk('T1b 残留 -> 仍推手机(只是文案温和)',
    len(push) == 1 and '疑似残留' in push[0])
chk('T1b 残留 -> peer_kind=stale', st.get('peer_kind') == 'stale', st.get('peer_kind'))
chk('T1b 分档阈值表述为 45 秒', '45 秒' in _txt, _txt[-90:])

# T1c 连续两轮都是残留: 只在进档时提示一次, 不刷屏
logs, push, st = run_hb(peer_age=100)
logs2, push2, st2 = run_hb(peer_age=100, pre_state={'peer_kind': 'stale',
                                                    'last_stale_ts': time.time()})
chk('T1c 首轮进档有提示', len([x for x in logs if '疑似残留心跳' in x]) == 1)
chk('T1c 次轮同档不再提示', len([x for x in logs2 if '疑似残留心跳' in x]) == 0,
    str(logs2)[:120])

# T1d 同伴退出: 提示恢复单实例 + 清 peer_kind
logs, push, st = run_hb(peer_age=None, pre_state={'peer': 'PID=18792 版本=V2.6.88',
                                                  'peer_kind': 'stale'})
chk('T1d 退出 -> 恢复单实例日志', any('当前为单实例运行' in x for x in logs), str(logs)[:120])
chk('T1d 退出 -> peer_kind 清空', st.get('peer_kind') == '')
chk('T1d 退出 -> 不乱推手机', len(push) == 0)

# T1e 边境: age=44 秒仍算活, 46 秒算残留(阈值 45 = HEARTBEAT_SEC*1.5)
logs, push, st = run_hb(peer_age=44)
chk('T1e age=44s 判活', st.get('peer_kind') == 'live', st.get('peer_kind'))
logs, push, st = run_hb(peer_age=46)
chk('T1e age=46s 判残留', st.get('peer_kind') == 'stale', st.get('peer_kind'))

# ============================================================
# T2 换手率可审计(直接执行母版里那段 log 语句, 验参数顺序)
# ============================================================
print('=' * 60)
print('T2 换手率漏斗/优选项日志')

FUNNEL = block("log('           -> 换手率不符", '(st_mcap_low + st_mcap_high + st_mcap_miss), total))')
out = []
ns = {'log': out.append, 'st_turnover': 5, 'st_turn_lo': 2, 'st_turn_hi': 3,
      'st_turnover_calc': 7, 'st_turnover_missing': 1, 'st_amt': 0, 'st_excl': 11,
      'st_excl_risk': 0, 'st_excl_st': 0, 'st_excl_board': 0, 'st_excl_oth': 0,
      'st_namefail': 0, 'st_sthist': 25, 'st_risk': 10, 'st_ma10': 15,
      'st_lowhold': 0, 'st_hot': 0, 'st_dedup': 0, 'st_susp': 0,
      'st_mcap_low': 1, 'st_mcap_high': 1, 'st_mcap_miss': 0, 'total': 8}
exec(compile(FUNNEL, '<funnel>', 'exec'), ns)
_seg = out[0] if out else ''
chk('T2 漏斗只输出一行', len(out) == 1, str(len(out)))
chk('T2 换手率四段数值落位正确', '换手率不符5(过低2/过高3/自算7/缺失放行1)' in _seg, _seg[:90])
chk('T2 后续计数未被移位(成交额0/板块11)',
    '成交额不足0' in _seg and '板块或名称排除11' in _seg, _seg[:140])
chk('T2 候选数落位', _seg.rstrip().endswith('候选8只'), _seg[-30:])

PRINT_BLK = block("_tt = _f(c.get('turn_t0') or 0)", "c['offset'], _tt_txt, _fin_txt))")
c = {'stock': '603466.SH', 'name': '风语筑', 't0': '20261013', 'base_vol': 1468009,
     'shrink_rank': 0.47, 'pullback': 0.069, 'zt_close': 13.57, 'offset': 4,
     'turn_t0': 0.132}
out = []
ns = {'log': out.append, '_f': float, 'c': c, 'i': 0,
      '_fin_txt': '公告日期=20260827 | 净利润=9371.70万元'}
exec(compile(PRINT_BLK, '<print>', 'exec'), ns)
chk('T2 优选项打出涨停日换手率', len(out) == 1 and '涨停日换手=13.2%' in out[0], str(out)[:140])
chk('T2 优选项其余字段未错位',
    '603466.SH' in out[0] and '风语筑' in out[0] and '净利润=9371.70万元' in out[0])

c2 = dict(c)
c2.pop('turn_t0')                      # 状态文件旧格式(无该字段)必须不崩
out = []
ns = {'log': out.append, '_f': float, 'c': c2, 'i': 1, '_fin_txt': 'x'}
exec(compile(PRINT_BLK, '<print>', 'exec'), ns)
chk('T2 缺 turn_t0 时打"缺失(已放行)"不崩',
    len(out) == 1 and '涨停日换手=缺失(已放行)' in out[0], str(out)[:120])

# ============================================================
# T3 _float_share 异常提示(不静默 + 节流)
# ============================================================
print('=' * 60)
print('T3 _float_share 异常提示')

FS_SRC = func_src('_float_share')
logs = []


class _C(object):
    def __init__(self, mode):
        self.mode = mode

    def get_instrument_detail(self, s):
        if self.mode == 'raise':
            raise RuntimeError('柜台接口超时')
        if self.mode == 'none':
            return None
        return {'FloatVolume': 442000000}


def run_fs(mode, G):
    ns = {'time': time, 'G': G, '_f': float,
          '_api': lambda fn, *a: fn(*a),
          'log': logs.append,
          '_exc_text': lambda e: '%s: %s' % (type(e).__name__, e)}
    exec(compile(FS_SRC, '<_float_share>', 'exec'), ns)
    return ns['_float_share']('603466.SH')


G = SimpleNamespace(C=_C('raise'))
r = run_fs('raise', G)
chk('T3 接口抛异常 -> 返回 0(不误杀)', r == 0.0, str(r))
chk('T3 接口抛异常 -> 打提示不静默',
    len(logs) == 1 and '流通股本取数异常' in logs[0], str(logs)[:140])
chk('T3 提示里带异常原文', '柜台接口超时' in (logs[0] if logs else ''))

# 同一个 G(生产里 G 是常驻对象)再异常一次: 清掉流通股本缓存逼它真的重试接口,
#   如果节流键错挂在函数局部/每次新建 G 上, 这里就会再打一行 —— 线上表现为每只票刷一行。
G._fshare_cache.clear()
run_fs('raise', G)
chk('T3 30 分钟内再异常 -> 节流不再刷屏', len(logs) == 1, str(len(logs)))
chk('T3 节流键落在 G 上(跨调用可见)',
    getattr(G, '_fshare_err_ts', 0) > 0 and (time.time() - G._fshare_err_ts) < 60)

logs.clear()
G = SimpleNamespace(C=_C('none'))
r = run_fs('none', G)
chk('T3 接口返回空 dict -> 0 且不误报异常', r == 0.0 and len(logs) == 0, str(logs)[:100])

logs.clear()
G = SimpleNamespace(C=_C('ok'))
r = run_fs('ok', G)
chk('T3 正常路径 -> 取到流通股本', r == 442000000.0, str(r))
chk('T3 正常路径 -> 不打提示', len(logs) == 0)

# ============================================================
# 汇总
# ============================================================
print('=' * 60)
print('TOTAL %d/%d PASS' % (len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print('FAILED: %s' % FAIL)
    sys.exit(1)
