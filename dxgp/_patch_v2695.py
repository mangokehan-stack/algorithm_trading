# -*- coding: utf-8 -*-
"""V2.6.95 补丁: 只改日志与账目口径(用户点选第 2、5、6 项), 不动任何交易/取数/风控逻辑。

第 2 项(P7): 下载进度按"千位桶号跨桶即打" —— 旧判定要求 G.dl_i 恰好是 2000 的整数倍,
  而每轮实际只推进约 250 只, 永远踩不到, 整场只在结束时打一行(甚至一行都没有)。
第 5 项: st 口径账目 —— 旧注解写死"st类=145只", 实际 st 标签 166 只(本地145 + 公告独有21)。
第 6 项: 启动自检补排雷清单项(优先显示真实命中的候选路径) + "缺失请复制"改为有缺失才打印。

做法: 全部按行号定位后整行拼接, 不重打空白与缩进, 避免 CRLF/缩进写坏。
"""
import io
import os
import shutil
import hashlib

P = 'zt_shrink_strategy_gbk.py'
BAK = os.path.join('_baseline', 'V2.6.94.py')

raw = io.open(P, 'rb').read()
t = raw.decode('gbk')
L = t.split('\r\n')
N0 = len(L)

if not os.path.exists(BAK):
    shutil.copy(P, BAK)
    print('  [备份] %s (%d 字节)' % (BAK, os.path.getsize(BAK)))
else:
    print('  [备份] 已存在, 未覆盖: %s' % BAK)


def find_one(sub, start=0, why=''):
    hits = [i for i in range(start, len(L)) if sub in L[i]]
    if len(hits) != 1:
        raise SystemExit('[中止] 锚点命中 %d 次(应为1): %r %s' % (len(hits), sub, why))
    return hits[0]


def find_prefix(pref, start=0):
    hits = [i for i in range(start, len(L)) if L[i].startswith(pref)]
    if len(hits) != 1:
        raise SystemExit('[中止] 前缀命中 %d 次(应为1): %r' % (len(hits), pref))
    return hits[0]


# ---------------------------------------------------------------- 1) G.dl_mark 字段
i = find_prefix('G.dl_i = 0')
assert 'dl_i' in L[i], L[i]
L[i + 1:i + 1] = [
    u'G.dl_mark = -1                # V2.6.95: 下载进度上次打印的"千位桶号"(-1=本轮还没打过); '
    u'配合跨桶打印, 见 step_day_init',
]
print('  [1/6] G.dl_mark 字段已加')

# ---------------------------------------------------------------- 2) 新一轮下载重置桶号
i = find_prefix('        G.dl_i = 0')
if L[i + 1].strip() != 'G.dl_phase = 1':
    raise SystemExit('[中止] 下载起始块上下文不匹配: %r' % L[i + 1])
L[i + 2:i + 2] = [
    u'        G.dl_mark = -1      # V2.6.95: 新一轮重新计桶, 保证首轮就打印进度(不再静默10分钟)',
]
print('  [2/6] 下载起始重置桶号已加')

# ---------------------------------------------------------------- 3) 进度打印改跨桶
i = find_one('if G.dl_i % 2000 == 0 or G.dl_i >= len(G.universe):')
if not L[i + 1].strip().startswith("log('下载进度'"):
    raise SystemExit('[中止] 进度打印上下文不匹配: %r' % L[i + 1])
L[i:i + 2] = [
    u"        _u_tot = len(G.universe)",
    u"        _bucket = G.dl_i // 2000      # V2.6.95(2): 千位桶号 —— 旧判定要求进度恰好踩在",
    u"        #   2000 的整数倍上, 但每轮实际只推进约 250 只(8秒预算被并发的情绪取数拖住), 于是",
    u"        #   250/500/750/1000... 永远踩不到 2000, 整场只在结束时打一行, 甚至一行都没有",
    u"        #   (2026-10-20 00:07 那次启动, 5226 只下完约10分钟里日志一个字都没打)。",
    u"        #   改成跨桶即打: 首轮就出进度, 之后每跨过 2000 只一行, 末尾补一行终值。",
    u"        if _bucket != getattr(G, 'dl_mark', -1) or G.dl_i >= _u_tot:",
    u"            G.dl_mark = _bucket",
    u"            log('下载进度', min(G.dl_i, _u_tot), '/', _u_tot)",
]
print('  [3/6] 下载进度改为跨桶打印')

# ---------------------------------------------------------------- 4) st 口径账目拆分
i = find_one("        if _stfb > 0:")
if "_st_note = (u' [st类=" not in L[i + 1]:
    raise SystemExit('[中止] st 注解上下文不匹配: %r' % L[i + 1])
if L[i + 3].strip() != '% _stfb)':
    raise SystemExit('[中止] st 注解结尾不匹配: %r' % L[i + 3])
L[i:i + 4] = [
    u"        _st_tot = _cnt.get('st', 0)     # V2.6.95(5): 清单里 st 标签的实际只数(本地兜底+公告独有)",
    u"        _st_ann_only = (_st_tot - _stfb) if _st_tot > _stfb else 0",
    u"        if _stfb > 0:",
    u"            _st_note = (u' [st类=%d只 = 本地清单兜底%d + 公告简称独有%d(生成端st源失败); '",
    u"                        u'本地清单只含名称带ST的票, 不含\"退\"字票(退市由实时名称闸门拦)]'",
    u"                        % (max(_st_tot, _stfb), _stfb, _st_ann_only))",
]
print('  [4/6] st 口径拆成 本地兜底 + 公告独有')

# ---------------------------------------------------------------- 5) 启动自检: 补排雷清单项
i0 = find_prefix('        _items = (')
i1 = find_prefix('        for _lb, _p, _on in _items:')
if i1 - i0 != 7:
    raise SystemExit('[中止] _items 元组行数变化(期望7行, 实际%d)' % (i1 - i0))
L[i0:i1] = [
    u"        # V2.6.95(6): 排雷清单(zt_shrink_risk_exclude)此前不在自检范围 —— 2026-10-19 一晚",
    u"        #   改了三版的那个文件, 启动时是“活着还是缺失”反而没人报。这里补入, 并按装载器的",
    u"        #   真实顺序(带账号后缀 -> 无后缀回退)挑出实际会被读到的那一份打印, 避免“有回退文件”",
    u"        #   却显示缺失”。",
    u"        _rex_p = risk_exclude_path()",
    u"        try:",
    u"            for _c in _risk_exclude_candidates():",
    u"                if os.path.exists(_c):",
    u"                    _rex_p = _c",
    u"                    break",
    u"        except Exception:",
    u"            pass",
    u"        _items = (",
    u"            ('历史ST清单', st_hist_path(), EXCLUDE_ST_HIST),",
    u"            ('人工黑名单', blacklist_path(), None),",
    u"            ('提前排雷清单', _rex_p, RISK_EXCLUDE_ON),",
    u"            ('应急开关文件', _join_base(EMERGENCY_FILE), None),",
    u"            ('状态文件', state_path(), None),",
    u"            ('运行日志', run_log_path(), None),",
    u"        )",
]
print('  [5/6] 启动自检补排雷清单项')

# ---------------------------------------------------------------- 6) 缺失项收集 + 提示改条件打印
i = find_one("                    _st = '缺失'")
if L[i + 1].strip() != 'except Exception:':
    raise SystemExit('[中止] 缺失分支上下文不匹配: %r' % L[i + 1])
L[i + 1:i + 1] = [u"                    _miss.append(_lb)"]

i = find_one("        for _lb, _p, _on in _items:")
if '_items' not in L[i] or '_lb, _p, _on' not in L[i]:
    raise SystemExit('[中止] for 锚点异常')
L[i:i] = [u"        _miss = []"]

i = find_one("[启动自检][提示] 上面显示缺失的文件若你其实已创建")
if "请把它们复制到'" not in L[i]:
    raise SystemExit('[中止] 提示行上下文不匹配')
if L[i + 2].strip() != "'当天补放不会立即生效, 次日或重启策略后生效。')":
    raise SystemExit('[中止] 提示行结尾不匹配: %r' % L[i + 2])
L[i:i + 3] = [
    u"        # V2.6.95(6): 旧版这句是无条件打印的 —— 6 项全“已就位”时它照样出现, 每天每条启动",
    u"        #   日志都带一句“上面显示缺失的文件若你其实已创建”, 纯噪音, 反而稀释了真缺失的提示。",
    u"        #   现在只在真有缺失时打印, 并把缺哪几项点出来。",
    u"        if _miss:",
    u"            log('[启动自检][提示] 缺失项: %s —— 若你其实已创建, 说明它放错目录了: 请把它们'",
    u"                '复制到上面文件基准目录下(相对路径一律按该目录解析); 清单类文件按日加载, '",
    u"                '当天补放不会立即生效, 次日或重启策略后生效。' % (', '.join(_miss)))",
]
print('  [6/6] 缺失提示改为条件打印')

# ---------------------------------------------------------------- 版本头 + VERSION
i = find_one(u'版本号: V2.6.94              修改时间:')
if not L[i].startswith(u'版本号: V2.6.94'):
    raise SystemExit('[中止] 版本头行不匹配')
L[i:i] = [
    u'版本号: V2.6.95              修改时间: 2026-10-20 00:42 (V2.6.95记录: 用户回"2 + 5 + 6(纯日志, '
    u'零风险)", 三项全是日志与账目口径, 不改任何交易/取数/风控行为 —— 起因是 2026-10-20 00:07 V2.6.94 '
    u'启动日志。【2 下载进度从不打印, P7】旧判定 G.dl_i % 2000 == 0 要求进度恰好踩在 2000 的整数倍, 但'
    u'每轮实际只推进约 250 只(8 秒预算被并发的情绪取数拖住), 250/500/750/1000 永远踩不到 2000, 于是 '
    u'5226 只下完的约 10 分钟里日志一个字都没有, 外面看像卡死(顺带说明: 那 10 分钟里也没有"下载进度"'
    u'可贴, 不是我漏读)。现按"千位桶号跨桶即打": 首轮 250 就出一行, 之后每跨 2000 只一行, 末尾补终值。'
    u'【5 st 口径账目缺口】V2.6.94 注解写死"st类=145只来自本地清单兜底", 而清单 st 标签实测 166 只'
    u'(本地兜底145 + 公告简称独有21), 差的 21 只没有出处。现按 tags 实数拆成 '
    u'"st类=166只 = 本地清单兜底145 + 公告简称独有21", 并保留"不含退字票"的边界说明。'
    u'【6 启动自检】①提前排雷清单(昨晚改了三版的那个文件)压根不在自检范围, 现补入, 并按装载器的真实'
    u'顺序(带账号后缀 -> 无后缀回退)显示实际会被读到的那一份, 避免"有回退文件却报缺失"; '
    u'②"上面显示缺失的文件若你其实已创建..." 旧版无条件打印, 6 项全已就位也照打, 纯噪音, 现改为仅在有'
    u'缺失时打印并点名缺哪几项。)',
]
i = find_one(u"VERSION = 'V2.6.94'")
L[i] = L[i].replace(u"'V2.6.94'", u"'V2.6.95'")
print('  [版本] 头注释 + VERSION 已升到 V2.6.95')

# ---------------------------------------------------------------- 落盘
out = '\r\n'.join(L)
if out.count('\r\n') != len(L) - 1:
    raise SystemExit('[中止] 行尾异常')
if '\n\n' in out.replace('\r\n', '\n\n') and False:
    pass
compile(out, P, 'exec')
b = out.encode('gbk')
io.open(P, 'wb').write(b)
print('  [OK] compile() 通过 | 行数 %d -> %d | %d 字节 | MD5 %s'
      % (N0, len(L), len(b), hashlib.md5(b).hexdigest().upper()))
