# -*- coding: utf-8 -*-
"""V2.6.93 -> V2.6.94 补丁: 排雷命中数拆项 + 命中留痕 + st 口径说明

三项全部是日志口径, 不改任何交易/风控/选股判定:
  [1] 漏斗 "板块或名称排除N" 拆成 排雷清单/ST/板块/名称取数失败 四档
  [2] 排雷命中明细单独打印(最多40条), 独立列表不进 blocked 账目
  [3] 装载行补 st 口径注: st 源失败时那个数不等于市场 ST 总数
"""
import io
import os
import shutil

P = 'zt_shrink_strategy_gbk.py'
BK = os.path.join('_baseline', 'V2.6.93.py')

raw = io.open(P, 'rb').read()
t = raw.decode('gbk')
L = t.split('\r\n')
n0 = len(L)
print('[0] 原文件: %d 字节 / %d 行' % (len(raw), n0))

if not os.path.exists(BK):
    shutil.copy(P, BK)
    print('    备份 -> %s' % BK)
else:
    print('    备份已存在, 跳过: %s' % BK)

VER_HEAD = (
    u'版本号: V2.6.94              修改时间: 2026-10-20 00:35 (V2.6.94记录: '
    u'用户回"4项目全部做", 落地第1~4项, 起因是 2026-10-19 23:57 V2.6.93 首份实跑日志。'
    u'【1 排雷命中数被归并, 真问题】excluded() 内部调 risk_excluded(), 选股循环命中时只累加 '
    u'st_excl 一个变量, 于是"排雷清单命中"与"当前ST/创业板"共用漏斗里"板块或名称排除15"这同一个格子; '
    u'而"避雷风险"只对应 risk_blocked(名称/仙股/跌幅/财务亏损), 压根不含清单。结果: 提前排雷自 '
    u'V2.6.83 上线起拦了几只、拦了谁, 日志里一个字都查不到, 2026-10-19 两轮实盘我都在猜(先误判成"命中0")。'
    u'现拆成 排雷清单/ST/板块/名称取数失败 四档, 四者之和恒等于 st_excl, 并打印命中明细(最多40条)。'
    u'【2 命中留痕】命中明细存独立列表 risk_ex_hits, 不塞进 blocked —— 否则"按避雷/结构过滤剔除21只"'
    u'会变成36只, 破坏账目。'
    u'【3 st 口径】装载行补注: st 源失败时那个数字是"公告扫描窗口内发过公告的ST票"(20页35只/60页80只, '
    u'随 --ann-pages 线性变), 不等于市场ST总数; 工具侧已加本地清单兜底, 兜底成功则直接报 fallback_n。'
    u'【4 工具侧】st 源失败改读 zt_shrink_st_coef_note_<账号>.txt(实测145只), 该文件是策略按"当前名称含ST"'
    u'写入的本地快照。四项均为日志/兜底, 参数指纹不变。'
)


def sub1(old, new, tag):
    """全文件唯一替换, 命中数必须为 1"""
    c = t.count(old)
    if c != 1:
        raise SystemExit('[中止] %s 命中 %d 次(应为1): %r' % (tag, c, old[:70]))
    return t.replace(old, new)


# ---------------------------------------------------------------- A 版本头
hits = [i for i, l in enumerate(L) if l.startswith(u'版本号: V2.6.93')]
if len(hits) != 1:
    raise SystemExit('[中止] 版本头 V2.6.93 命中 %d 次' % len(hits))
L.insert(hits[0], VER_HEAD)
print('[A] 版本头已插入于 L%d' % (hits[0] + 1))

# ---------------------------------------------------------------- B VERSION
i_v = [i for i, l in enumerate(L) if l.startswith(u"VERSION = 'V2.6.93'")]
if len(i_v) != 1:
    raise SystemExit('[中止] VERSION 常量命中 %d 次' % len(i_v))
L[i_v[0]] = L[i_v[0]].replace(u"'V2.6.93'", u"'V2.6.94'")
print('[B] VERSION -> %s' % L[i_v[0]].strip()[:40])

# ---------------------------------------------------------------- C 计数器初始化
i_turn = [i for i, l in enumerate(L) if l.startswith(u'    st_turn_lo = st_turn_hi = 0')]
if len(i_turn) != 1:
    raise SystemExit('[中止] 换手率计数器行命中 %d 次' % len(i_turn))
INS_C = [
    u'    # V2.6.94(1): 拆解"板块或名称排除" —— 旧版这一个计数混装 ST/板块/排雷清单三种原因,',
    u'    #   导致"提前排雷清单到底拦了几只"从 V2.6.83 上线起无法从日志看出(2026-10-19 两轮',
    u'    #   实盘都只能靠猜, 且我先误判成"命中0")。以下四个计数器之和恒等于 st_excl。',
    u'    st_excl_risk = st_excl_st = st_excl_board = st_excl_oth = 0',
    u'    risk_ex_hits = []   # V2.6.94(2): 排雷命中明细(纯日志, 不进账目/不参与筛选)',
]
L[i_turn[0] + 1:i_turn[0] + 1] = INS_C
print('[C] 计数器初始化已插入(5行)')

t = '\r\n'.join(L)

# ---------------------------------------------------------------- D excluded 分支
OLD_D = (
    u"        _exr = excluded(s)\r\n"
    u"        if _exr:\r\n"
    u"            if _exr.startswith('名称取数失败'):\r\n"
    u"                st_namefail += 1\r\n"
    u"            st_excl += 1\r\n"
    u"            continue"
)
NEW_D = (
    u"        _exr = excluded(s)\r\n"
    u"        if _exr:\r\n"
    u"            # V2.6.94(1): 按 excluded() 的返回原因分类计数, 四项之和恒等于 st_excl\r\n"
    u"            if _exr.startswith('名称取数失败'):\r\n"
    u"                st_namefail += 1\r\n"
    u"            elif _exr.startswith('排雷命中'):\r\n"
    u"                st_excl_risk += 1\r\n"
    u"                if len(risk_ex_hits) < 40:      # 上限40条, 防清单异常时日志爆量\r\n"
    u"                    risk_ex_hits.append('%s | %s | %s' % (s, inst_name(s), _exr))\r\n"
    u"            elif _exr == 'ST':\r\n"
    u"                st_excl_st += 1\r\n"
    u"            elif _exr in ('KCB', 'CYB'):\r\n"
    u"                st_excl_board += 1\r\n"
    u"            else:\r\n"
    u"                st_excl_oth += 1                # 未预期原因单独计数, 绝不并入其它档\r\n"
    u"            st_excl += 1\r\n"
    u"            continue"
)
t = sub1(OLD_D, NEW_D, 'D excluded 分支')
print('[D] excluded 命中分类已拆四档')

# ---------------------------------------------------------------- E 漏斗打印(两处单行)
t = sub1(
    u"'板块或名称排除%d(名称取数失败%d) / 历史ST%d / 避雷风险%d / '",
    u"'板块或名称排除%d(排雷清单%d/ST %d/板块 %d/名称取数失败%d%s) / 历史ST%d / 避雷风险%d / '",
    'E1 漏斗格式串')
print('[E1] 漏斗格式串已改')

L = t.split('\r\n')
i_arg = [i for i, l in enumerate(L) if u'st_excl, st_namefail, st_sthist, st_risk, st_ma10, st_lowhold, st_hot,' in l]
if len(i_arg) != 1:
    raise SystemExit('[中止] 漏斗参数行命中 %d 次' % len(i_arg))
_ind = L[i_arg[0]][:len(L[i_arg[0]]) - len(L[i_arg[0]].lstrip())]
L[i_arg[0]:i_arg[0] + 1] = [
    _ind + u'st_excl, st_excl_risk, st_excl_st, st_excl_board, st_namefail,',
    _ind + u"(u'/其它%d' % st_excl_oth) if st_excl_oth else u'',",
    _ind + u'st_sthist, st_risk, st_ma10, st_lowhold, st_hot,',
]
print('[E2] 漏斗参数行已改(1行->3行)')
t = '\r\n'.join(L)

# ---------------------------------------------------------------- F 命中明细
ANCH_F = u"        log('按避雷/结构过滤剔除%d只(风险信号/MA10破位/非热门板块)' % len(blocked))"
INS_F = (
    u"\r\n"
    u"    # V2.6.94(2): 排雷清单命中明细 —— 旧版命中被 excluded() 吞进\"板块或名称排除\",\r\n"
    u"    #   拦了谁、为什么拦, 日志里一个字都没有(2026-10-19 两轮实盘都只能靠猜)。\r\n"
    u"    if risk_ex_hits:\r\n"
    u"        log('排雷清单命中%d只(已计入上方\"板块或名称排除\", 不重复计入\"避雷风险\"), 明细:'\r\n"
    u"            % len(risk_ex_hits))\r\n"
    u"        for _rxr in risk_ex_hits:\r\n"
    u"            log('  %s' % _rxr)"
)
t = sub1(ANCH_F, ANCH_F + INS_F, 'F 命中明细')
print('[F] 排雷命中明细已插入')

# ---------------------------------------------------------------- G 装载行 st 口径
OLD_G = (
    u"        log('[排雷] 已装载提前排雷清单%d只(%s) 文件=%s'\r\n"
    u"            % (len(data), ', '.join('%s=%d' % (k, v) for k, v in sorted(_cnt.items())) or '-',\r\n"
    u"               os.path.basename(used) if used else u'(沿用旧表)'))"
)
NEW_G = (
    u"        # V2.6.94(3): st 口径说清 —— st 源失败时这个数字不是\"市场ST总数\", 而是\"公告扫描\r\n"
    u"        #   窗口内发过公告的ST票\"(20页=35只 / 60页=80只, 随 --ann-pages 线性变), 与本地\r\n"
    u"        #   真名单(zt_shrink_st_coef_note, 实测145只)无关。2026-10-19 两轮日志都只打\r\n"
    u"        #   st=35 / st=80, 极易被读成\"覆盖率达标\"。工具侧已加本地清单兜底(同批改动),\r\n"
    u"        #   兜底成功时这里直接报兜底只数, 兜底失败才提示\"仅为公告兜底\"。\r\n"
    u"        _sti = _src.get('st') if isinstance(_src, dict) else None\r\n"
    u"        _stfb = 0\r\n"
    u"        if isinstance(_sti, dict):\r\n"
    u"            try:\r\n"
    u"                _stfb = int(_sti.get('fallback_n') or 0)\r\n"
    u"            except Exception:\r\n"
    u"                _stfb = 0\r\n"
    u"        if _stfb > 0:\r\n"
    u"            _st_note = (u' [st类=%d只来自本地清单兜底(生成端数据源失败); '\r\n"
    u"                        u'该清单只含名称带ST的票, 不含\"退\"字票(退市由实时名称闸门拦)]'\r\n"
    u"                        % _stfb)\r\n"
    u"        elif isinstance(_sti, dict) and _sti.get('ok') is False:\r\n"
    u"            _st_note = (u' [st类仅为公告简称兜底, 数量随--ann-pages波动, '\r\n"
    u"                        u'不等于市场ST总数, 需重跑工具补全]')\r\n"
    u"        else:\r\n"
    u"            _st_note = u''\r\n"
    u"        log('[排雷] 已装载提前排雷清单%d只(%s) 文件=%s%s'\r\n"
    u"            % (len(data), ', '.join('%s=%d' % (k, v) for k, v in sorted(_cnt.items())) or '-',\r\n"
    u"               os.path.basename(used) if used else u'(沿用旧表)', _st_note))"
)
t = sub1(OLD_G, NEW_G, 'G 装载行 st 口径')
print('[G] 装载行 st 口径已补')

# ---------------------------------------------------------------- 落盘校验
if t.count('\r\n') != t.count('\n'):
    raise SystemExit('[中止] 出现裸 LF: CRLF=%d LF=%d' % (t.count('\r\n'), t.count('\n')))
try:
    t.encode('gbk')
except Exception as e:
    raise SystemExit('[中止] GBK 编码失败: %r' % (e,))

out = t.encode('gbk')
if out.count(b'\r\n') != n0 + len(INS_C) + 5 + 2 + 1 + 6 + 22 - 3:
    pass   # 行数另行打印, 不做硬编码断言
compile(t, P, 'exec')
print('    compile() 通过 | 行数 %d -> %d (+%d)' % (n0, len(t.split('\r\n')), len(t.split('\r\n')) - n0))
io.open(P, 'wb').write(out)
print('    已写入 %s (%d 字节)' % (P, len(out)))
