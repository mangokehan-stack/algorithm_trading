# -*- coding: utf-8 -*-
"""V2.6.96 补丁: 落地用户点选的第 1、3、4 项。

第 1 项(P1): 日线下载期间不发起情绪取数 —— 两者都在打全市场批量行情接口, 实测 2026-10-20
  00:22:33 启动时同一秒并发, 下载每轮 8 秒只推进 153 只, 情绪取数从常态约 40 秒拖到 151 秒。
  改为串行(下载阶段1 期间推迟), 下载完成后下一轮定时器自动发起, 期间买入侧保持中性;
  推迟满 30 分钟强制发起并告警, 防止下载卡死把情绪一起拖死。
第 3 项(P5): 块大小 x5(400 -> 2000) + 单轮"下完一块预算还有剩就接着切下一块", 让 8 秒预算
  成为唯一上限(旧版不管预算剩多少都退出等下一个 30 秒节拍, 每轮空转 22 秒)。
第 4 项(P6): 预算命中即把覆盖率门槛从 90% 临时提到 98% —— 旧版砍掉最后 1 批仍有 94.3% >= 90%
  被静默采用, 而排序尾部正是科创板/北交所段, 会系统性带偏涨跌广度与涨停占比。

实现约束: 不新增任何模块级大写常量(_fp_keys 会全量收进参数指纹), 全部用局部变量与
SENT_STATE 运行时键; 块大小写成 DOWNLOAD_CHUNK * 5 的局部算式。参数指纹应仍为 8a4ab7e8。
"""
import io
import os
import shutil

P = 'zt_shrink_strategy_gbk.py'
BAK = os.path.join('_baseline', 'V2.6.95.py')

raw = io.open(P, 'rb').read()
t = raw.decode('gbk')
L = t.split('\r\n')
N0 = len(L)
CRLF0 = raw.count(b'\r\n')

if not os.path.exists(BAK):
    shutil.copy(P, BAK)
    print('  [备份] %s (%d 字节)' % (BAK, os.path.getsize(BAK)))
else:
    print('  [备份] 已存在, 未覆盖: %s' % BAK)


def find_one(sub, why=''):
    hits = [i for i in range(len(L)) if sub in L[i]]
    if len(hits) != 1:
        raise SystemExit('[中止] 锚点命中 %d 次(应为1): %r %s' % (len(hits), sub, why))
    return hits[0]


def find_prefix(pref, why=''):
    hits = [i for i in range(len(L)) if L[i].startswith(pref)]
    if len(hits) != 1:
        raise SystemExit('[中止] 前缀命中 %d 次(应为1): %r %s' % (len(hits), pref, why))
    return hits[0]


# ---------------------------------------------------------------- 1) 版本头 + VERSION
i = find_prefix('版本号: V2.6.95')
head = (
    u'版本号: V2.6.96              修改时间: 2026-10-20 00:31 (V2.6.96记录: 用户回"完成第 1、3、4 项", '
    u'三项都是"下载与情绪取数抢接口"这条线上的收口 —— 起因是 2026-10-20 00:22 V2.6.95 的启动日志: '
    u'5226 只日线下载与 5226 只情绪取数在同一秒(00:22:33)并发打行情接口, 结果下载每轮 8 秒只推进 153 只'
    u'(正常 400), 情绪取数耗时 151 秒(常态约 40 秒), 两边互相拖慢, 5226 只下完要 17 分钟。'
    u'【1 串行化】旧版 sent_daily_refresh 完全不看 G.dl_phase, 只要今日没刷新过就发起取数。'
    u'现下载阶段1 期间只推迟不发起(每轮定时器重新判一次, 不写 last_try_ts 所以不会被 300 秒节流卡住), '
    u'下载结束后的下一轮(30 秒内)自动发起; 推迟期间买入侧维持中性, 不拦买也不缩放仓位, 与"情绪未就绪"同档。'
    u'推迟满 30 分钟则明确告警并强行发起 —— 下载若卡死不能把情绪一起拖死, 明早的闸门判断更要紧。'
    u'【3 预算用满】旧版每轮只切一块 400 只, 不管 8 秒预算还剩多少都退出等下一个 30 秒节拍, 每轮空转约 22 秒; '
    u'块大小也卡死了单轮上限(接口快起来时反而成了瓶颈)。现块大小 x5(2000, 局部算式 DOWNLOAD_CHUNK*5, '
    u'不改常量以免参数指纹漂移), 且"一块下完预算还有剩就接着切下一块", 单轮对轮询线程的占用仍严格受 '
    u'DOWNLOAD_TIME_BUDGET_SEC(8 秒)约束, 不多占 1 毫秒。顺带把 8 秒预算下"至少推进一只"的死循环保护保留。'
    u'【4 预算命中即降级】旧版 _budget_hit 只打一行日志, 覆盖率仍按 SENT_COVERAGE_MIN=90% 判: '
    u'砍掉最后 1 批 = 4926/5226 = 94.3% >= 90% 会被静默采用, 而按代码排序最尾部正是科创板/北交所段, '
    u'缺了它涨跌广度与涨停占比被系统性带偏(同一数据日 sentiment 曾在 -1.27/-1.00 之间漂移, 正好跨过 '
    u'panic 阈值 -1.0)。现预算命中即把本轮门槛临时提到 98%, 砍 1 批即被拒并沿用上次成功信号; '
    u'未命中仍按 90%, 常态不受影响。取数侧(_sent_fetch_sync)与应用侧(_sent_apply_rows)两处口径必须一致, '
    u'已同步改, 避免"取数侧说不采用、应用侧照用"的矛盾。'
    u'【不变项】三个改动都不碰买卖判据: 1 只影响取数发起时机(推迟期间仍是中性), 3 只影响下载节奏, '
    u'4 只让残缺样本更容易被拒(更保守)。绝不只损/扣费净利为正才卖/移交释放双额度三项铁律未触碰, '
    u'stop_order 仍为 0, NEVER_STOP_LOSS=True 未动。参数指纹应仍为 8a4ab7e8, 仅版本指纹变化。)'
)
L.insert(i, head)
print('  [1/6] 版本头已插入 V2.6.96 记录')

i = find_prefix('VERSION = ')
L[i] = u"VERSION = 'V2.6.96'    # 当前版本号(与启动日志和横幅展示一致; 改版需同步文件头版本注释)"
print('  [1/6] VERSION -> V2.6.96')

# ---------------------------------------------------------------- 2) 下载阶段1 整块重写
i_s = find_one('    if G.dl_phase == 1:')
i_e = find_one('    # 阶段2: 加载历史 + 选股')
if i_s >= i_e:
    raise SystemExit('[中止] 下载块定位反了')
for _k in range(i_s, i_e):
    if L[_k].startswith('    # 阶段2'):
        raise SystemExit('[中止] 下载块区间内出现阶段2注释')
blk = L[i_s:i_e]
if not blk[-1].startswith('        return'):
    raise SystemExit('[中止] 下载块末行不是 return: %r' % blk[-1])
if not any('chunk = G.universe' in x for x in blk):
    raise SystemExit('[中止] 下载块内未找到 chunk 切片行')
new_blk = [
    u"    if G.dl_phase == 1:",
    u"        start = G.dl_start",
    u"        end = G.today",
    u"        _u_tot = len(G.universe)",
    u"        # P1-3修复(2026-10-02): 单轮下载加时间预算 —— 旧版固定400只/轮, 单只下载慢时本轮会",
    u"        #   长时间占用轮询线程(成交回报回调被延迟)。超预算即让出线程, 下一轮从 G.dl_i 续下。",
    u"        # V2.6.96(3): 块大小 x5(400 -> 2000/块), 且\"一块下完预算还有剩就接着切下一块\"。",
    u"        #   旧版每轮只切一块 400 只, 不管 8 秒预算还剩多少都退出等下一个 30 秒节拍 ——",
    u"        #   2026-10-20 00:23 实测: 情绪取数并发抢接口, 8 秒只下 153 只, 余下约 22 秒纯空转,",
    u"        #   5226 只被拖成 17 分钟。现在把\"时间预算\"当成唯一上限: 8 秒内能下多少下多少,",
    u"        #   下完就停, 单轮对轮询线程的占用仍严格受 DOWNLOAD_TIME_BUDGET_SEC 约束, 不多占 1 毫秒。",
    u"        #   块大小写成局部算式 DOWNLOAD_CHUNK*5 而不是改常量: DOWNLOAD_CHUNK 是大写模块级",
    u"        #   常量, 改动会让参数指纹漂移, 使状态文件 verified_fp 的比对凭空失效。",
    u"        _chunk_n = DOWNLOAD_CHUNK * 5",
    u"        _t0 = time.time()",
    u"        _n = 0",
    u"        while G.dl_i < _u_tot and not G.no_download:",
    u"            if DOWNLOAD_TIME_BUDGET_SEC > 0 and (time.time() - _t0) >= DOWNLOAD_TIME_BUDGET_SEC:",
    u"                break           # 预算用完: 让出轮询线程, 下一轮从 G.dl_i 续下",
    u"            _chunk = G.universe[G.dl_i:G.dl_i + _chunk_n]",
    u"            if not _chunk:",
    u"                break",
    u"            _got = 0",
    u"            for s in _chunk:",
    u"                if G.no_download:",
    u"                    break",
    u"                if DOWNLOAD_TIME_BUDGET_SEC > 0 and (time.time() - _t0) >= DOWNLOAD_TIME_BUDGET_SEC:",
    u"                    break",
    u"                try:",
    u"                    _api(download_history_data, s, '1d', start, end)",
    u"                except NameError:",
    u"                    G.no_download = True",
    u"                    break",
    u"                except Exception:",
    u"                    pass",
    u"                _n += 1",
    u"                _got += 1",
    u"            G.dl_i += _got",
    u"            if G.no_download:",
    u"                break           # 交给下面的 no_download 分支处置(dl_i 不再推进, 保住\"是否首轮\"的判断)",
    u"            if _got <= 0:",
    u"                G.dl_i += 1     # 单只下载即超预算: 至少推进一只, 保证不死循环",
    u"                break",
    u"            if _got < len(_chunk):",
    u"                break           # 预算在本块内用完",
    u"            if DOWNLOAD_TIME_BUDGET_SEC <= 0:",
    u"                break           # 预算关闭(0=不限)时保持旧行为: 一轮只下一块, 不长时间占用轮询线程",
    u"        if G.no_download:",
    u"            if G.dl_i == 0:",
    u"                log('本QMT无download_history_data接口: 请在客户端手动批量下载沪深A股'",
    u"                    '日线历史数据(数据管理/历史数据下载), 否则无数据可选股')",
    u"            G.dl_i = len(G.universe)   # 跳过下载阶段, 直接读取本地已有数据",
    u"            G.state['last_dl_date'] = G.today",
    u"            save_state()",
    u"            G.dl_phase = 2",
    u"            return",
    u"        _bucket = G.dl_i // 2000      # V2.6.95(2): 千位桶号 —— 旧判定要求进度恰好踩在",
    u"        #   2000 的整数倍上, 但每轮实际只推进约 250 只(8秒预算被并发的情绪取数拖住), 于是",
    u"        #   250/500/750/1000... 永远踩不到 2000, 整场只在结束时打一行, 甚至一行都没有",
    u"        #   (2026-10-20 00:07 那次启动, 5226 只下完约10分钟里日志一个字都没打)。",
    u"        #   改成跨桶即打: 首轮就出进度, 之后每跨过 2000 只一行, 末尾补一行终值。",
    u"        if _bucket != getattr(G, 'dl_mark', -1) or G.dl_i >= _u_tot:",
    u"            G.dl_mark = _bucket",
    u"            log('下载进度', min(G.dl_i, _u_tot), '/', _u_tot)",
    u"        if G.dl_i >= _u_tot:",
    u"            G.state['last_dl_date'] = G.today",
    u"            save_state()",
    u"            G.dl_phase = 2",
    u"        return",
]
L[i_s:i_e] = new_blk
print('  [2/6] 下载阶段1 已重写(块x5 + 预算用满 + 无 no_download 语义变化), 原 %d 行 -> 新 %d 行'
      % (len(blk), len(new_blk)))

# ---------------------------------------------------------------- 3) 情绪取数: 下载期间推迟
i = find_one("        SENT_STATE['last_try_ts'] = _now")
if not L[i + 1].strip().startswith('# 发起后台取数'):
    raise SystemExit('[中止] last_try_ts 上下文不匹配: %r' % L[i + 1])
L[i:i] = [
    u"        # V2.6.96(1): 日线下载期间不发起情绪取数 —— 两者都是\"全市场批量打行情接口\"。",
    u"        #   2026-10-20 00:22:33 那次启动, 5226 只日线下载与 5226 只情绪取数同一秒并发:",
    u"        #   下载每轮 8 秒只推进 153 只(正常 400), 情绪取数从常态约 40 秒拖到 151~195 秒,",
    u"        #   互相抢接口, 谁也跑不快, 5226 只下完要 17 分钟。现改为串行: 下载阶段1",
    u"        #   (G.dl_phase==1)期间只推迟、不发起; 下载完成后的下一轮定时器(30 秒内)自动发起,",
    u"        #   推迟期间买入侧维持中性(不拦买、不缩放仓位), 与\"情绪未就绪\"同档。",
    u"        #   注意这里不写 last_try_ts, 所以每轮都会重新判一次 dl_phase, 不会被 300 秒节流卡住。",
    u"        #   但下载卡死不能把情绪一起拖死: 推迟满 30 分钟就告警并强行发起。",
    u"        if int(getattr(G, 'dl_phase', 0) or 0) == 1:",
    u"            _dl_since = SENT_STATE.get('dl_wait_ts') or 0.0",
    u"            if _dl_since <= 0:",
    u"                SENT_STATE['dl_wait_ts'] = _now",
    u"                _dl_since = _now",
    u"            if (_now - _dl_since) < 1800.0:",
    u"                if (_now - (SENT_STATE.get('dl_wait_log_ts') or 0.0)) >= 300.0:",
    u"                    SENT_STATE['dl_wait_log_ts'] = _now",
    u"                    _sent_wlog('日线下载进行中(阶段1), 情绪取数本轮推迟: 两者并发会互相抢行情接口'",
    u"                               '(实测下载每轮8秒只推进153只、情绪取数从约40秒拖到151秒以上)。'",
    u"                               '下载结束后的下一轮定时器(30秒内)自动发起, 期间买入侧保持中性')",
    u"                return",
    u"            _sent_wlog('[告警] 日线下载已持续%d分钟仍未完成, 不再等它: 本轮情绪取数照常发起'",
    u"                       '(两者并发会互相拖慢, 但情绪迟迟不就绪对明早的闸门判断影响更大)'",
    u"                       % int((_now - _dl_since) / 60.0))",
    u"        else:",
    u"            SENT_STATE['dl_wait_ts'] = 0.0",
]
print('  [3/6] 情绪取数已加"下载期间推迟"闸门')

# ---------------------------------------------------------------- 4) 取数侧: 预算命中门槛
i = find_one("        _cov['ratio'] = (float(_cov['ok']) / float(_cov['req'])) if _cov['req'] > 0 else 0.0")
if L[i + 1].strip() != "SENT_STATE['cover'] = _cov":
    raise SystemExit('[中止] _cov ratio 上下文不匹配: %r' % L[i + 1])
L[i + 1:i + 1] = [
    u"        # V2.6.96(4): 预算命中 = 本轮数据\"被截断\", 即便覆盖率 94% 也不算完整。",
    u"        #   2026-10-20 00:12 实测: 预算命中砍掉最后 1 批 -> 4926/5226 = 94.3% >= 90% 门槛",
    u"        #   -> 残缺数据被静默采用; 而按代码排序最尾部正是科创板/北交所段, 缺了它涨跌广度",
    u"        #   与涨停占比会被系统性带偏(同一数据日 sentiment 曾在 -1.27 / -1.00 之间漂移,",
    u"        #   正好跨过 panic 阈值 -1.0)。现把\"预算命中\"记进 cover, 供应用侧把门槛临时提到 98%;",
    u"        #   砍 1 批(94.3%)即被拒并沿用上次成功信号, 未命中仍按 SENT_COVERAGE_MIN(90%)。",
    u"        _cov['budget_hit'] = bool(_budget_hit)",
]
print('  [4/6] cover 已记 budget_hit')

i = find_one("        _ratio_pct = _cov['ratio'] * 100.0 if _cov['ratio'] is not None else 0.0")
L[i + 1:i + 1] = [
    u"        # V2.6.96(4): 与本轮实际采用门槛保持一致(预算命中 -> 98%, 否则 90%)",
    u"        _min_cov = 0.98 if _budget_hit else SENT_COVERAGE_MIN",
]
print('  [4/6] 取数侧 _min_cov 已加')

i = find_one("        if _cov['ratio'] is not None and _cov['ratio'] < SENT_COVERAGE_MIN:")
if L[i + 1].strip() != "_sent_wlog('[告警] 行情覆盖率不足(%.1f%% < %.0f%%): 上游将沿用上一次成功信号, '":
    raise SystemExit('[中止] 覆盖率告警首行不匹配: %r' % L[i + 1])
if L[i + 3].strip() != "% (_ratio_pct, SENT_COVERAGE_MIN * 100.0))":
    raise SystemExit('[中止] 覆盖率告警末行不匹配: %r' % L[i + 3])
L[i:i + 4] = [
    u"        if _cov['ratio'] is not None and _cov['ratio'] < _min_cov:",
    u"            _sent_wlog('[告警] 行情覆盖率不足(%.1f%% < %.0f%%%s): 上游将沿用上一次成功信号, '",
    u"                       '本次结果不采用 —— 请检查QMT行情接口/登录状态/是否多实例争用'",
    u"                       % (_ratio_pct, _min_cov * 100.0,",
    u"                          ('; 本轮触发取数总预算(数据被截断), 门槛已临时从90%提高到98%')",
    u"                          if _budget_hit else ''))",
]
print('  [4/6] 取数侧覆盖率告警已改按 _min_cov')

# ---------------------------------------------------------------- 5) 应用侧: 同一口径
i = find_one("        if _ratio is not None and _ratio < SENT_COVERAGE_MIN:")
if not L[i + 1].strip().startswith('_sent_use_last_good('):
    raise SystemExit('[中止] 应用侧上下文不匹配: %r' % L[i + 1])
if L[i + 5].strip() != "int(_cov.get('fail') or 0), int(_cov.get('retry') or 0)))":
    raise SystemExit('[中止] 应用侧末行不匹配: %r' % L[i + 5])
L[i:i + 6] = [
    u"        # V2.6.96(4): 预算命中时门槛临时提到 98%(见 _sent_fetch_sync 同名注释)。",
    u"        #   两处必须用同一个口径, 否则会出现\"取数侧说不采用、应用侧照用\"的自相矛盾。",
    u"        _min_cov = 0.98 if _cov.get('budget_hit') else SENT_COVERAGE_MIN",
    u"        if _ratio is not None and _ratio < _min_cov:",
    u"            _sent_use_last_good(",
    u"                '行情覆盖率仅%.1f%%(<%.0f%%下限%s; 请求%d只/成功%d只/失败%d只/拆分重试%d次)'",
    u"                % (_ratio * 100.0, _min_cov * 100.0,",
    u"                   (', 本轮触发取数总预算故门槛临时从90%提高到98%')",
    u"                   if _cov.get('budget_hit') else '',",
    u"                   int(_cov.get('req') or 0), int(_cov.get('ok') or 0),",
    u"                   int(_cov.get('fail') or 0), int(_cov.get('retry') or 0)))",
    u"            return",
]
print('  [5/6] 应用侧门槛已同步')

# ---------------------------------------------------------------- 6) 落盘
out = '\r\n'.join(L)
data = out.encode('gbk')
io.open(P, 'wb').write(data)
print('  [6/6] 已写回: %d 行(原 %d) / %d 字节 / CRLF %d(原 %d)'
      % (len(L), N0, len(data), data.count(b'\r\n'), CRLF0))

try:
    compile(out, P, 'exec')
    print('  [校验] compile() 通过')
except SyntaxError as e:
    print('  [校验][失败] %s: line %s %s' % (type(e).__name__, e.lineno, e.text))
    raise SystemExit(1)
