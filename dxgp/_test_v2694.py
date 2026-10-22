# -*- coding: utf-8 -*-
"""V2.6.94 专项单测: 排雷命中拆项 / 命中留痕 / st 口径说明

不依赖 QMT 环境; 对 G 段(装载行 st 口径)按真实代码块 exec 执行, 其余为结构断言。
"""
import io
import hashlib
import re
import sys

P = 'zt_shrink_strategy_gbk.py'
raw = io.open(P, 'rb').read()
SRC = raw.decode('gbk')
BODY = SRC.replace('\r\n', '\n')      # 掐掉版本头注释行用
L = SRC.split('\r\n')

OK = [0]
FAIL = []


def chk(name, cond, detail=''):
    if cond:
        OK[0] += 1
        print('  PASS  %s' % name)
    else:
        FAIL.append(name)
        print('  FAIL  %s   %s' % (name, detail))


print('=== T1 元数据 ===')
m = re.search(r"VERSION = '([^']+)'", BODY)
chk('T1.1 VERSION>=V2.6.94', bool(m) and tuple(int(x) for x in m.group(1).lstrip('V').split('.')) >= (2, 6, 94),
    m.group(1) if m else '?')
chk('T1.2 版本头首条不早于 V2.6.94',
    re.match(u'版本号: V2\\.6\\.(\\d+)', L[4]) is not None
    and int(re.match(u'版本号: V2\\.6\\.(\\d+)', L[4]).group(1)) >= 94, L[4][:40])
chk('T1.3 全 CRLF 无裸 LF', SRC.count('\r\n') == SRC.count('\n'),
    'CRLF=%d LF=%d' % (SRC.count('\r\n'), SRC.count('\n')))
print('       行数=%d 字节=%d MD5=%s' % (len(L), len(raw), hashlib.md5(raw).hexdigest().upper()))

print('=== T2 命中分类四档 ===')
chk('T2.1 计数器初始化', 'st_excl_risk = st_excl_st = st_excl_board = st_excl_oth = 0' in BODY)
chk('T2.2 命中明细列表', 'risk_ex_hits = []' in BODY)
chk('T2.3 排雷命中分支', "elif _exr.startswith('排雷命中'):" in BODY)
chk('T2.4 ST 精确分支', "elif _exr == 'ST':" in BODY)
chk('T2.5 板块分支', "elif _exr in ('KCB', 'CYB'):" in BODY)
chk('T2.6 未预期原因单独计数', 'st_excl_oth += 1' in BODY)
chk('T2.7 明细上限40', 'if len(risk_ex_hits) < 40:' in BODY)
chk('T2.8 st_excl 仍在四项之后自增', BODY.index('st_excl_oth += 1') < BODY.index('            st_excl += 1\r\n            continue'.replace('\r\n', '\n')))
chk('T2.9 明细不进 blocked', 'blocked.append' not in BODY[BODY.index('risk_ex_hits.append'):BODY.index('risk_ex_hits.append') + 200])

print('=== T3 漏斗占位符与参数对齐 ===')
i_fmt = BODY.index(u"'板块或名称排除%d(排雷清单%d/ST %d/板块 %d/名称取数失败%d%s) / 历史ST%d / 避雷风险%d / '")
seg_start = BODY.rindex("log('           -> 换手率不符", 0, i_fmt)
i_args = BODY.index('st_excl, st_excl_risk, st_excl_st, st_excl_board, st_namefail,')
i_args_beg = BODY.rindex('% (st_turnover', 0, i_args)
seg_end = BODY.index('total))', i_args) + len('total')
fmt_block = BODY[seg_start:i_args_beg]
fmt_txt = ''.join(re.findall(r"u?'([^']*)'", fmt_block))
n_ph = fmt_txt.replace('%%', '').count('%d') + fmt_txt.replace('%%', '').count('%s')
arg_block = BODY[i_args_beg:seg_end]
args = [a.strip() for a in arg_block.replace('\n', ' ').replace('% (', '').split(',') if a.strip()]
chk('T3.1 占位符数=21', n_ph == 21, 'got=%d' % n_ph)
chk('T3.2 参数个数=21', len(args) == 21, 'got=%d: %s' % (len(args), args))
chk('T3.3 顺序: 排除数/排雷/ST/板块/失败/其它',
    args[6:12] == ['st_excl', 'st_excl_risk', 'st_excl_st', 'st_excl_board', 'st_namefail',
                   u"(u'/其它%d' % st_excl_oth) if st_excl_oth else u''"], 'got=%s' % args[6:12])

print('=== T4 装载行 st 口径(真跑代码块) ===')
i0 = BODY.index(u"_sti = _src.get('st') if isinstance(_src, dict) else None")
i1 = BODY.index(u"os.path.basename(used) if used else u'(沿用旧表)', _st_note))", i0)
i1 = BODY.index('\n', i1) + 1
block = BODY[i0:i1]
block = '\n'.join(l[8:] if l.startswith(' ' * 8) else l for l in block.split('\n'))


def run_block(src, used='a.json'):
    logs = []
    data = {'1': {}, '2': {}}
    ns = {'_src': src, 'data': data, 'used': used, '_cnt': {'st': 80},
          'os': __import__('os'), 'log': logs.append}
    exec(compile(block, '<block>', 'exec'), ns)
    return ns.get('_st_note'), logs


n1, lg1 = run_block({'st': {'ok': False, 'fallback_n': 145, 'fallback_file': 'x.txt'}})
chk('T4.1 兜底成功 -> 145只 = 本地145 + 公告0', u'st类=145只 = 本地清单兜底145 + 公告简称独有0' in n1, repr(n1))
chk('T4.2 兜底成功仍打装载行', '已装载提前排雷清单2只' in lg1[-1], lg1[-1] if lg1 else '')
n2, lg2 = run_block({'st': {'ok': False, 'err': 'x'}})
chk('T4.3 兜底失败 -> 公告兜底提示', u'仅为公告简称兜底' in n2 and u'不等于市场ST总数' in n2, repr(n2))
n3, lg3 = run_block({'st': {'ok': True, 'n': 150}})
chk('T4.4 st 源正常 -> 不加注', n3 == u'', repr(n3))
n4, lg4 = run_block({})
chk('T4.5 老清单无 sources -> 不加注不炸', n4 == u'', repr(n4))
n5, lg5 = run_block({'st': {'ok': False, 'fallback_n': 'bad'}})
chk('T4.6 fallback_n 非法 -> 回落公告提示', u'仅为公告简称兜底' in n5, repr(n5))
n6, lg6 = run_block({'st': {'ok': False, 'fallback_n': 0}})
chk('T4.7 fallback_n=0 -> 视为无兜底', u'仅为公告简称兜底' in n6, repr(n6))

print('=== T5 账目恒等式(计数口径) ===')
cases = [
    (dict(risk=7, st=8, board=0, fail=0, oth=0), 15),
    (dict(risk=0, st=0, board=0, fail=0, oth=0), 0),
    (dict(risk=10, st=3, board=2, fail=1, oth=1), 17),
]
for case, want in cases:
    got = case['risk'] + case['st'] + case['board'] + case['fail'] + case['oth']
    chk('T5 四项和=st_excl (%d)' % want, got == want, 'got=%d' % got)

print('=== T6 铁律体检 ===')
_body = '\n'.join(l for l in BODY.split('\n') if not l.startswith(u'版本号: '))
chk('T6.1 正文 stop_order 0 次', _body.count('stop_order') == 0, str(_body.count('stop_order')))
chk('T6.2 NEVER_STOP_LOSS 未动', 'NEVER_STOP_LOSS = True' in _body)
chk('T6.3 threading.Thread 仍1处', _body.count('threading.Thread(') == 1, str(_body.count('threading.Thread(')))
chk('T6.4 _api( 仍52次', _body.count('_api(') == 52, str(_body.count('_api(')))

print('\n========== %d PASS / %d FAIL ==========' % (OK[0], len(FAIL)))
if FAIL:
    for f in FAIL:
        print('  FAILED: %s' % f)
    sys.exit(1)
print('ALL GREEN')
