# -*- coding: utf-8 -*-
"""排雷功能策略侧单测：清单装载容错 + 双重拦截挂点行为。"""
import ast
import datetime
import json
import os
import shutil
import sys
import tempfile

SRC = 'zt_shrink_strategy_gbk.py'
text = open(SRC, 'rb').read().decode('gbk', errors='strict')
tree = ast.parse(text)

WANT = ('risk_exclude_path', '_risk_exclude_candidates', 'load_risk_exclude',
        'risk_excluded', 'excluded',
        # V2.6.92: 当日重载用到两个指纹工具函数, 漏抽会导致 NameError → 装载整体失败
        '_risk_ex_sig_of', '_risk_ex_cur_sig')
nodes = {}
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name in WANT:
        nodes[n.name] = n
missing = [w for w in WANT if w not in nodes]
if missing:
    print('MISSING FUNCS:', missing)
    sys.exit(1)

BASE = tempfile.mkdtemp(prefix='riskex_')


class _G(object):
    pass


G = _G()
G.today = '20261019'
G.risk_ex = {}
G.risk_ex_date = ''
G.accid = 'T1'

LOGS = []
ALERTS = []


def log(*a):
    LOGS.append(' '.join(str(x) for x in a))


def pnl_alert(t):
    ALERTS.append(str(t))


def _join_base(name):
    return os.path.join(BASE, name)


def _split_name(raw):
    stem, ext = os.path.splitext(raw)
    if not ext:
        ext = '.json'
    return stem, ext


def _account_suffix():
    return '_' + str(G.accid)


def name_known(s):
    return not str(s).startswith('FAIL')


def inst_name(s):
    return 'ST测试' if str(s).startswith('ST') else '正常股份'


def is_st_name(nm):
    return 'ST' in str(nm).upper()


ns = {
    'os': os, 'json': json, 'datetime': datetime, 'time': __import__('time'),
    'G': G, 'log': log, 'pnl_alert': pnl_alert,
    '_join_base': _join_base, '_split_name': _split_name,
    '_account_suffix': _account_suffix,
    'name_known': name_known, 'inst_name': inst_name, 'is_st_name': is_st_name,
    'RISK_EXCLUDE_ON': True,
    'RISK_EXCLUDE_FILE': 'zt_shrink_risk_exclude.json',
    'RISK_EXCLUDE_MAX_AGE_DAYS': 10,
    'EXCLUDE_ST': True, 'EXCLUDE_KCB': False, 'EXCLUDE_CYB': False,
    '_f': (lambda v, d=0.0: (float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else d)),
}
for nm in WANT:
    mod = ast.Module(body=[nodes[nm]], type_ignores=[])
    exec(compile(mod, SRC, 'exec'), ns)

risk_excluded = ns['risk_excluded']
load_risk_exclude = ns['load_risk_exclude']
excluded = ns['excluded']
risk_exclude_path = ns['risk_exclude_path']

OK = []


def chk(name, cond, detail=''):
    OK.append((name, bool(cond), detail))
    print('%s %s %s' % ('PASS' if cond else 'FAIL', name, ('' if cond else detail)))


def write_json(fn, obj, enc='utf-8'):
    with open(os.path.join(BASE, fn), 'w', encoding=enc) as f:
        json.dump(obj, f, ensure_ascii=False)


def reset():
    G.risk_ex = {}
    G.risk_ex_date = ''
    G.risk_ex_try_ts = 0.0
    G.risk_ex_note_date = ''      # V2.6.84: 每日一次的日志去重标记, 用例间必须复位
    del LOGS[:]
    del ALERTS[:]


def good_obj(asof='20261019', codes=None):
    return {
        'schema': 1, 'asof': asof, 'window_days': 45,
        'stocks': codes if codes is not None else {
            '002142.SZ': {'tags': ['lift', 'ann'], 'reasons': ['临近解禁(2026-11-02)', '立案(2026-10-10 公告)']},
            '600000.SH': {'tags': ['st'], 'reasons': []},
            '000001.SZ': {'tags': [], 'reasons': []},
        },
    }


PNG = 'zt_shrink_risk_exclude_T1.json'
MAIN = 'zt_shrink_risk_exclude.json'

# ---------------- 1 正常装载 ----------------
reset()
write_json(PNG, good_obj())
d = load_risk_exclude()
chk('1.1 后缀文件装载3只', len(d) == 3, 'n=%d' % len(d))
chk('1.2 risk_excluded命中返回原因', risk_excluded('002142.SZ').startswith('排雷命中: 临近解禁'),
    risk_excluded('002142.SZ'))
chk('1.3 只有tags时返回tags', 'st' in risk_excluded('600000.SH'), risk_excluded('600000.SH'))
chk('1.4 空reasons空tags返回兜底文案', risk_excluded('000001.SZ') == '排雷命中(清单内)',
    risk_excluded('000001.SZ'))
chk('1.5 未命中返回空串', risk_excluded('999999.SZ') == '', risk_excluded('999999.SZ'))
chk('1.6 装载日志含只数', any('[排雷] 已装载提前排雷清单3只' in l for l in LOGS), LOGS[:2])

# ---------------- 2 每日只装载一次 ----------------
reset()
write_json(PNG, good_obj())
load_risk_exclude()
n_log = len(LOGS)
write_json(PNG, good_obj(codes={'111111.SZ': {'tags': ['st'], 'reasons': []}}))
d2 = load_risk_exclude()
chk('2.1 同日重复调用不再读盘', len(d2) == 3 and len(LOGS) == n_log, 'n=%d logs=%d' % (len(d2), len(LOGS) - n_log))
G.today = '20261020'
d3 = load_risk_exclude()
chk('2.2 换日重新装载', len(d3) == 1 and '111111.SZ' in d3, 'n=%d' % len(d3))
G.today = '20261019'

# ---------------- 3 后缀优先于主文件 ----------------
reset()
write_json(PNG, good_obj(codes={'222222.SZ': {'tags': ['st'], 'reasons': ['后缀']}}))
write_json(MAIN, good_obj(codes={'333333.SZ': {'tags': ['st'], 'reasons': ['主文件']}}))
d = load_risk_exclude()
chk('3.1 账号后缀文件优先', '222222.SZ' in d and '333333.SZ' not in d, list(d.keys()))

# ---------------- 4 后缀缺失回退主文件 ----------------
reset()
os.remove(os.path.join(BASE, PNG))
d = load_risk_exclude()
chk('4.1 后缀缺失回退无后缀主文件', '333333.SZ' in d, list(d.keys()))
os.remove(os.path.join(BASE, MAIN))

# ---------------- 5 清单缺失: 不阻断, 留痕 ----------------
reset()
d = load_risk_exclude()
chk('5.1 清单缺失返回空且不抛', d == {}, d)
chk('5.2 缺失有提示日志', any('[排雷][待办]' in l for l in LOGS), LOGS[:2])
chk('5.3 缺失时不推强提醒(避免每天骚扰)', len(ALERTS) == 0, ALERTS)
chk('5.4 缺失时risk_excluded返回空串', risk_excluded('002142.SZ') == '', risk_excluded('002142.SZ'))
# V2.6.84: 文案必须说清"功能已开启"(旧版说"可选功能"会让人以为没启用)
chk('5.5 提示写明功能已开启', any('RISK_EXCLUDE_ON=True' in l for l in LOGS), LOGS[:2])
chk('5.6 提示写明生成后无需重启', any('无需重启策略' in l for l in LOGS), LOGS[:2])
chk('5.7 不再出现"可选功能"误导措辞', not any('可选功能' in l for l in LOGS), LOGS[:2])
# 每日一次: 60秒节流到期后再调用, 不应重复刷屏
G.risk_ex_try_ts = 0.0
del LOGS[:]
load_risk_exclude()
chk('5.8 同一日重复装载不重复打提示', len(LOGS) == 0, LOGS[:2])

# ---------------- 6 损坏容错 ----------------
reset()
with open(os.path.join(BASE, PNG), 'w', encoding='utf-8') as f:
    f.write('{ this is not json ')
d = load_risk_exclude()
chk('6.1 非法JSON返回空且不抛', d == {}, d)
chk('6.2 非法JSON有强提醒', len(ALERTS) >= 1, ALERTS)

reset()
write_json(PNG, {'schema': 1, 'asof': '20261019', 'stocks': ['002142.SZ']})
d = load_risk_exclude()
chk('6.3 stocks为list判结构不符', d == {}, d)
chk('6.4 结构不符有强提醒', len(ALERTS) >= 1 and '结构不符' in ALERTS[0], ALERTS)

reset()
write_json(PNG, {'schema': 1, 'asof': '20261019',
                 'stocks': {'002142.SZ': 'not-a-dict', '600000.SH': {'tags': ['st'], 'reasons': ['x']}}})
d = load_risk_exclude()
chk('6.5 单条非dict被跳过, 其余保留', list(d.keys()) == ['600000.SH'], list(d.keys()))

# ---------------- 7 过期清单仍生效 ----------------
reset()
write_json(PNG, good_obj(asof='20250101'))
d = load_risk_exclude()
chk('7.1 过期清单仍装载(偏紧)', len(d) == 3, len(d))
chk('7.2 过期有强提醒', any('已过期' in a for a in ALERTS), ALERTS)

# ---------------- 8 excluded() 双重拦截 ----------------
reset()
write_json(PNG, good_obj())
r = excluded('002142.SZ')
chk('8.1 excluded命中排雷返回原因', r.startswith('排雷命中'), r)
r2 = excluded('600519.SH')
chk('8.2 未命中排雷的普通票通过', r2 == '', r2)
r3 = excluded('ST000001.SZ')
chk('8.3 原有ST过滤仍生效(排雷未命中走ST)', r3 == 'ST', r3)
r4 = excluded('FAIL001.SZ')
chk('8.4 P1-1名称失败保守剔除仍生效', r4.startswith('名称取数失败'), r4)

# ---------------- 9 开关关闭 ----------------
reset()
ns['RISK_EXCLUDE_ON'] = False
write_json(PNG, good_obj())
chk('9.1 开关关闭不装载', load_risk_exclude() == {}, G.risk_ex)
chk('9.2 开关关闭不拦截', risk_excluded('002142.SZ') == '', risk_excluded('002142.SZ'))
ns['RISK_EXCLUDE_ON'] = True

# ---------------- 10 文件存在但清单为空(V2.6.84 新增区分) ----------------
reset()
write_json(PNG, good_obj(codes={}))
d = load_risk_exclude()
chk('10.1 空清单返回空字典', d == {}, d)
chk('10.2 空清单提示"内容为空"而非"文件不存在"',
    any('内容为空' in l for l in LOGS) and not any('清单文件不存在' in l for l in LOGS), LOGS[:2])
chk('10.3 空清单不误推强提醒', len(ALERTS) == 0, ALERTS)
chk('10.4 空清单不锁定当日(allow retry)', G.risk_ex_date == '', G.risk_ex_date)
G.risk_ex_try_ts = 0.0
del LOGS[:]
load_risk_exclude()
chk('10.5 空清单提示每日一次', len(LOGS) == 0, LOGS[:2])
os.remove(os.path.join(BASE, PNG))

# ---------------- 11 汇总 ----------------
shutil.rmtree(BASE, ignore_errors=True)
fails = [n for (n, c, d) in OK if not c]
print('\nRESULT: %d passed, %d failed' % (len(OK) - len(fails), len(fails)))
if fails:
    print('FAILED:', fails)
    sys.exit(1)
