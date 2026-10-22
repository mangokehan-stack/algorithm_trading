# -*- coding: utf-8 -*-
"""V2.6.95 专项单测(独立执行, 不依赖 QMT 环境)

用户点选第 2、5、6 项(纯日志, 零风险), 测试全部对着"日志/账目口径"断言:
  T1 元数据        —— VERSION / 版本头 / 全 CRLF
  T2 下载进度跨桶  —— 首轮 250 就打, 500/750 不打, 2000/4000/末尾各一行(旧判定 %2000 永远踩不到)
  T3 桶号字段      —— G.dl_mark 有初始化, 新一轮下载重置为 -1, 旧 "% 2000 == 0" 已消失
  T4 st 账目拆分   —— 166 = 本地145 + 公告21; 相等时 +0; _cnt 缺 st 时不炸(取 max)
  T5 启动自检      —— 6 项含排雷清单; 回退路径命中无后缀文件; 无缺失时不打"请复制"提示
  T6 铁律          —— stop_order 0 / NEVER_STOP_LOSS 未动 / Thread 1 / _api 52
  T7 参数指纹      —— 仍 8a4ab7e8(只改日志不改参数)

设计原则(延续 _test_v2688~2694): exec 母版真实代码块, 不重写判据。
"""
import contextlib
import io
import os
import re
import sys
import tempfile
import textwrap

P = 'zt_shrink_strategy_gbk.py'
raw = io.open(P, 'rb').read()
SRC = raw.decode('gbk')
FULL = SRC.replace('\r\n', '\n')
BODY = '\n'.join(l for l in FULL.split('\n') if not l.startswith(u'版本号: '))
LINES = SRC.split('\r\n')

PASS, FAIL = [], []


def chk(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))


# ---------------------------------------------------------------- T1
print('=== T1 元数据 ===')
m = re.search(r"VERSION = '([^']+)'", BODY)
chk('T1.1 VERSION>=V2.6.96', bool(m) and tuple(int(x) for x in m.group(1).lstrip('V').split('.')) >= (2, 6, 96),
    m.group(1) if m else '?')
chk('T1.2 版本头首条不早于 V2.6.96',
    re.match(u'版本号: V2\\.6\\.(\\d+)', LINES[4]) is not None
    and int(re.match(u'版本号: V2\\.6\\.(\\d+)', LINES[4]).group(1)) >= 96, LINES[4][:44])
chk('T1.3 全 CRLF 无裸 LF', SRC.count('\r\n') == SRC.count('\n'),
    'CRLF=%d LF=%d' % (SRC.count('\r\n'), SRC.count('\n')))
chk('T1.4 上一版记录仍在(V2.6.94)', any(l.startswith(u'版本号: V2.6.94') for l in LINES[5:12]))
import hashlib
print('       行数=%d 字节=%d MD5=%s' % (len(LINES), len(raw), hashlib.md5(raw).hexdigest().upper()))

# ---------------------------------------------------------------- T2
print('=== T2 下载进度跨桶打印(真跑代码块) ===')
# V2.6.96: 块首的 _u_tot 挪到下载块最前面(块x5 改造), 抽取起点改为桶号判定行,
#   否则会把整个 while 下载循环连同 return 一起抽出来 -> 'return' outside function。
i0 = FULL.index(u'        _bucket = G.dl_i // 2000')
# V2.6.97: 完成分支的 log 已改成两行(自带耗时后缀), 旧的"抽到第一条 log 行尾"会把括号截断
#   -> SyntaxError '(' was never closed。改为抽到外层 if 之前, 用带行首锚点的正则,
#   避免误配到内层同名的 12 空格缩进 if。
_m_i1 = re.search(r'\n {8}if G\.dl_i >= _u_tot:', FULL[i0:])
assert _m_i1, '未找到下载进度块结束位置'
i1 = i0 + _m_i1.start() + 1
BLOCK = textwrap.dedent(FULL[i0:i1])
chk('T2.0 代码块含桶号判定', 'dl_mark' in BLOCK and '_u_tot' in BLOCK, BLOCK[:0])


class _Clk(object):
    u"""V2.6.97(3) 完成行要读 time.time() 与 _f, 给个固定时钟(786 秒前开始下)"""
    t = 1000.0

    def time(self):
        return self.t


def run_prog(dl_i, total, mark=-1):
    logs = []

    class G(object):
        universe = ['x'] * total

    g = G()
    g.dl_i = dl_i
    g.dl_t0 = 214.0        # 1000 - 214 = 786 秒
    if mark is not None:
        g.dl_mark = mark
    ns = {'G': g, 'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
          '_u_tot': total,   # V2.6.96: 抽取起点已不含 _u_tot 赋值行, 由测试注入
          'time': _Clk(), '_f': lambda x: float(x or 0)}
    exec(compile(BLOCK, '<prog>', 'exec'), ns)
    return logs, g


lg, g = run_prog(250, 5226)
chk('T2.1 首轮250就打(旧版静默的关键)', lg == ['下载进度 250 / 5226'], repr(lg))
chk('T2.2 打完记下桶号0', g.dl_mark == 0, str(getattr(g, 'dl_mark', None)))
lg, g = run_prog(500, 5226, g.dl_mark)
chk('T2.3 同桶500不打', lg == [], repr(lg))
lg, g = run_prog(1750, 5226, g.dl_mark)
chk('T2.4 同桶1750不打', lg == [], repr(lg))
lg, g = run_prog(2000, 5226, g.dl_mark)
chk('T2.5 跨到2000打一行', lg == ['下载进度 2000 / 5226'], repr(lg))
lg, g = run_prog(4000, 5226, g.dl_mark)
chk('T2.6 跨到4000打一行', lg == ['下载进度 4000 / 5226'], repr(lg))
lg, g = run_prog(5226, 5226, g.dl_mark)
chk('T2.7 末尾终值必打', len(lg) == 1 and lg[0].startswith('下载进度 5226 / 5226'), repr(lg))
# V2.6.97(3): 完成行进补耗时与均速(786 秒 / 5226 只 ≈ 6.6 只每秒)
chk('T2.7b 完成行带耗时均速', '耗时786秒' in lg[0] and '均速6.6只/秒' in lg[0], repr(lg))
# 旧判定对照: 250 不是 2000 的整数倍 -> 旧版一行都不打
chk('T2.8 旧判定确实会漏(250 % 2000 != 0)', 250 % 2000 != 0)
# 超下界保护: dl_i 万一超过总数也不越界打印
lg, g = run_prog(6000, 5226, 2)
chk('T2.9 越界取 min 不打出 6000/5226',
    len(lg) == 1 and lg[0].startswith('下载进度 5226 / 5226'), repr(lg))

# ---------------------------------------------------------------- T3
print('=== T3 桶号字段与旧判定清理 ===')
chk('T3.1 G.dl_mark 已初始化', bool(re.search(r'^G\.dl_mark = -1', BODY, re.M)))
chk('T3.2 新一轮下载重置桶号', u'G.dl_mark = -1      # V2.6.95' in BODY)
chk('T3.3 旧 "% 2000 == 0" 已彻底移除', 'G.dl_i % 2000' not in BODY)
chk('T3.4 dl_mark 是大写以外的属性(不影响参数指纹)', 'G.dl_mark' in BODY and 'DL_MARK' not in BODY)

# ---------------------------------------------------------------- T4
print('=== T4 装载行 st 口径(真跑代码块) ===')
j0 = FULL.index(u"_sti = _src.get('st') if isinstance(_src, dict) else None")
j1 = FULL.index(u"os.path.basename(used) if used else u'(沿用旧表)', _st_note))", j0)
j1 = FULL.index('\n', j1) + 1
# 首行从 "_sti =" 起(已无前导空格), 其余行仍是 8 空格缩进 -> 逐行剥 8 格, dedent 在这里不管用
SBLOCK = '\n'.join(l[8:] if l.startswith(' ' * 8) else l for l in FULL[j0:j1].split('\n'))


def run_st(src, st_cnt):
    logs = []
    ns = {'_src': src, 'data': {'1': {}, '2': {}}, 'used': 'a.json',
          '_cnt': st_cnt, 'os': os, 'log': lambda *a: logs.append(' '.join(str(x) for x in a))}
    exec(compile(SBLOCK, '<st>', 'exec'), ns)
    return ns.get('_st_note'), logs


n1, lg1 = run_st({'st': {'ok': False, 'fallback_n': 145}}, {'st': 166})
chk('T4.1 166 = 本地145 + 公告21',
    u'st类=166只 = 本地清单兜底145 + 公告简称独有21' in n1, repr(n1))
chk('T4.2 装载行仍打印', any(u'已装载提前排雷清单2只' in x for x in lg1), repr(lg1))
n2, _ = run_st({'st': {'ok': False, 'fallback_n': 145}}, {'st': 145})
chk('T4.3 全等时 +0 且不出现负数', u'st类=145只 = 本地清单兜底145 + 公告简称独有0' in n2, repr(n2))
n3, _ = run_st({'st': {'ok': False, 'fallback_n': 145}}, {})
chk('T4.4 _cnt 缺 st -> 取 max, 不出现 "0只=145"', u'st类=145只' in n3 and u'0只 = ' not in n3, repr(n3))
n4, _ = run_st({'st': {'ok': False, 'err': 'x'}}, {'st': 80})
chk('T4.5 无兜底 -> 仍走公告提示', u'仅为公告简称兜底' in n4 and u'不等于市场ST总数' in n4, repr(n4))
n5, _ = run_st({'st': {'ok': True, 'n': 150}}, {'st': 150})
chk('T4.6 st 源正常 -> 不加注', n5 == u'', repr(n5))
n6, _ = run_st({'st': {'ok': False, 'fallback_n': 'bad'}}, {'st': 30})
chk('T4.7 fallback_n 非法 -> 回落公告提示', u'仅为公告简称兜底' in n6, repr(n6))
chk('T4.8 边界说明仍在(不含退字票)', u'不含"退"字票' in n1)

# ---------------------------------------------------------------- T5
print('=== T5 启动自检(真跑函数) ===')
k0 = [i for i, l in enumerate(LINES) if l.startswith('def startup_selftest')][0]
k1 = [i for i, l in enumerate(LINES) if l.startswith('def ') and i > k0][0]
FSRC = textwrap.dedent('\n'.join(LINES[k0:k1]))
TMP = tempfile.mkdtemp(prefix='v2695_')     # 仅给 T7 的 __file__ 用


def build_ns(exists):
    logs = []
    tmp = tempfile.mkdtemp(prefix='v2695_case_')   # 每个场景独立目录, 避免上一场景的文件串味
    paths = dict((k, os.path.join(tmp, k + '.json')) for k in
                 ('st_hist', 'black', 'rex_sfx', 'rex_plain', 'emerg', 'state', 'runlog'))
    for k in exists:
        io.open(paths[k], 'w').write(u'x')
    ns = {
        'log': lambda *a: logs.append(' '.join(str(x) for x in a)),
        'file_base_dir': lambda: tmp,
        'st_hist_path': lambda: paths['st_hist'],
        'blacklist_path': lambda: paths['black'],
        'risk_exclude_path': lambda: paths['rex_sfx'],
        '_risk_exclude_candidates': lambda: [paths['rex_sfx'], paths['rex_plain']],
        '_join_base': lambda n: os.path.join(tmp, n),
        'EMERGENCY_FILE': paths['emerg'],
        'state_path': lambda: paths['state'],
        'run_log_path': lambda: paths['runlog'],
        'EXCLUDE_ST_HIST': True,
        'RISK_EXCLUDE_ON': True,
        'os': os,
        'traceback': __import__('traceback'),
    }
    exec(compile(FSRC, '<selftest>', 'exec'), ns)
    ns['startup_selftest']()
    return logs, paths


allk = ('st_hist', 'black', 'rex_sfx', 'rex_plain', 'emerg', 'state', 'runlog')
lg, paths = build_ns(allk)
items = [x for x in lg if u'[启动自检] ' in x and u'文件基准目录' not in x]
chk('T5.1 自检项共6条(原5条+排雷清单)', len(items) == 6, 'got=%d: %s' % (len(items), items))
chk('T5.2 含提前排雷清单且带开关', any(u'提前排雷清单: 已就位' in x and u'功能开关=开' in x for x in items),
    repr([x for x in items if u'排雷' in x]))
chk('T5.3 有账号后缀时优先显示带后缀那份', any(u'rex_sfx.json' in x for x in items), repr(items))
chk('T5.4 六项全在 -> 不打"请复制"提示', not any(u'[启动自检][提示]' in x for x in lg), repr(lg))

lg2, paths2 = build_ns(('st_hist', 'black', 'rex_plain', 'emerg', 'state', 'runlog'))
items2 = [x for x in lg2 if u'[启动自检] ' in x and u'文件基准目录' not in x]
chk('T5.5 只有无后缀回退文件 -> 仍显示已就位', any(u'提前排雷清单: 已就位' in x and u'rex_plain.json' in x
                                                for x in items2), repr([x for x in items2 if u'排雷' in x]))
chk('T5.6 此时也不该报缺失', not any(u'[启动自检][提示]' in x for x in lg2))

lg3, paths3 = build_ns(('st_hist', 'black', 'emerg', 'state', 'runlog'))
chk('T5.7 排雷清单两份都缺 -> 报缺失', any(u'提前排雷清单: 缺失' in x for x in lg3), repr(lg3[-2:]))
tips = [x for x in lg3 if u'[启动自检][提示]' in x]
chk('T5.8 有缺失 -> 打印提示并点名', len(tips) == 1 and u'提前排雷清单' in tips[0], repr(tips))
chk('T5.9 提示仍保留"放错目录"原意', u'放错目录' in tips[0] and u'文件基准目录' in tips[0])

# ---------------------------------------------------------------- T6
print('=== T6 铁律体检 ===')
chk('T6.1 正文 stop_order 0 次', BODY.count('stop_order') == 0, str(BODY.count('stop_order')))
chk('T6.2 NEVER_STOP_LOSS 未动', 'NEVER_STOP_LOSS = True' in BODY)
chk('T6.3 threading.Thread 仍1处', BODY.count('threading.Thread(') == 1, str(BODY.count('threading.Thread(')))
chk('T6.4 _api( 仍52次', BODY.count('_api(') == 52, str(BODY.count('_api(')))
chk('T6.5 本次未新增全局大写常量', 'DL_MARK' not in BODY and 'PROG_BUCKET' not in BODY)

# ---------------------------------------------------------------- T7
print('=== T7 参数指纹 ===')
ns = {'__file__': os.path.join(TMP, 'fake_v2695.py'), '__name__': 'v2695_probe'}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(BODY, P, 'exec'), ns)
try:
    fp = ns['param_fingerprint']()
    fp = fp[0] if isinstance(fp, tuple) else fp
except Exception as e:
    fp = 'ERR:%r' % (e,)
chk('T7.1 参数指纹仍 8a4ab7e8', fp == '8a4ab7e8', 'got=%s' % fp)

print('\n========== %d PASS / %d FAIL ==========' % (len(PASS), len(FAIL)))
if FAIL:
    for f in FAIL:
        print('  FAILED: %s' % f)
    sys.exit(1)
print('ALL GREEN')
