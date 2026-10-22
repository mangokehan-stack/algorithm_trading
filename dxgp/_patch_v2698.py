# -*- coding: utf-8 -*-
"""V2.6.98 补丁: 1 项真风险(补选股无下载兜底) + 4 项日志口径

全部按行区间替换, 每块先做内容校验; 从后往前替换保证行号不漂移。
目标文件 GBK + CRLF, 写回前 compile() 熔断。
"""
import io
import hashlib

P = 'zt_shrink_strategy_gbk.py'
raw = io.open(P, 'rb').read()
L = raw.decode('gbk').split('\r\n')


def chk(idx, must):
    line = L[idx - 1]
    if must not in line:
        raise SystemExit('锚点 %d 不匹配: %r' % (idx, line[:140]))


# ---------------- 校验五个区间 ----------------
chk(3422, "_ds = '' if bool(getattr(G, 'loss_data_ok', True)) else")
chk(3423, "log('策略状态更新 | 时段=%s | 初始化阶段=%d |")
chk(3427, 'pnl_brief(), sig[7], sig[8], _ds))')
chk(3428, 'return True')

chk(7322, 'for _rlc in G.candidates[MAX_DAILY_PICKS:]:')
chk(7323, '落选(超出每日优选上限')
chk(7328, 'G.candidates = G.candidates[:MAX_DAILY_PICKS]')

chk(7422, '今日低吸候选共%d只')
chk(7423, '(total, len(G.candidates)))')

chk(7437, '第%d优先')
chk(7439, "_tt_txt, _fin_txt))")

chk(7460, 'if len(G.hist) >= MIN_UNIVERSE_FOR_SCREEN:')
chk(7461, 'screen_candidates()')
chk(7462, "log('补选股完成, 有效股票数:', len(G.hist))")

# ---------------- 块 D: 7460~7462 补选股下载兜底 ----------------
D = [
    "    if len(G.hist) >= MIN_UNIVERSE_FOR_SCREEN:",
    "        screen_candidates()",
    "        log('补选股完成, 有效股票数:', len(G.hist))",
    "        G.rescreen_tries = 0        # V2.6.98(2): 补齐即清零, 下次再残缺时重新从 0 计数",
    "        return",
    "    # V2.6.98(2) 修复: 旧版到这里就结束了 —— 只 load_history() 读本地缓存, 从不下载。",
    "    #   load_history() 走 get_market_data_ex(纯读), 本地没有的股票它永远返回空;",
    "    #   而 stage2 在 5496 行无条件写 last_init_date=today, 之后每轮 step_day_init 在 5344",
    "    #   行直接 return —— 于是'某天首轮只读到 500 只'会变成: 当天不重下、每 300 秒纯读重试、",
    "    #   永远补不上, 整天空仓, 日志里只留一条重复的'补选股: 当前有效历史仅N只'。",
    "    #   修法: 连续 3 次(约 15 分钟)仍不足, 就清空 last_dl_date/last_init_date 并重置阶段机,",
    "    #   让 step_day_init 下一轮按正常流程重下 —— 复用既有下载段(8 秒预算/跨桶进度/耗时/串行化),",
    "    #   不另写一套下载。重置次数上限 2 次, 防止接口真坏时整天反复下 5226 只。",
    "    _tries = int(getattr(G, 'rescreen_tries', 0)) + 1",
    "    G.rescreen_tries = _tries",
    "    if _tries < 3:",
    "        return",
    "    if G.no_download:",
    "        log('[数据告警] 补选股连续%d次不足%d只, 且本机无 download_history_data 接口; '",
    "            '请手动下载沪深A股日线(数据管理/历史数据下载), 否则本日无候选' %",
    "            (_tries, MIN_UNIVERSE_FOR_SCREEN))",
    "        return",
    "    _rs_n = int(getattr(G, 'rsdl_reset_n', 0))",
    "    if _rs_n >= 2:",
    "        log('[数据告警] 补选股连续%d次不足%d只, 已重置下载%d次仍未补齐; 本日不再自动重下, '",
    "            '请人工检查行情连接与数据目录' % (_tries, MIN_UNIVERSE_FOR_SCREEN, _rs_n))",
    "        return",
    "    G.rsdl_reset_n = _rs_n + 1",
    "    G.rescreen_tries = 0",
    "    G.state['last_dl_date'] = ''",
    "    G.state['last_init_date'] = ''",
    "    G.dl_phase = 0",
    "    G.dl_i = 0",
    "    G.dl_mark = -1",
    "    save_state()",
    "    log('[数据告警] 补选股连续%d次加载不足%d只(实际仅%d只), 判定本地日线缓存残缺 -> '",
    "        '重置下载状态机, 下一轮重新下载全市场日线(第%d/2次); 期间无候选属预期' %",
    "        (_tries, MIN_UNIVERSE_FOR_SCREEN, len(G.hist), G.rsdl_reset_n))",
]

# ---------------- 块 C3: 7437~7439 优选行回撤符号 + 落选块挪到其后 ----------------
C3 = [
    "        # V2.6.98(5): 回撤为负 = 昨收高于涨停收盘(即昨收涨), 旧版印成 '昨收回撤=-1.9%',",
    "        #   读着别扭还容易被当成数据错误; 负数直接换算成上涨幅度, 不用读者在脑子里翻符号。",
    "        _pb_raw = c['pullback'] * 100.0",
    "        _pb_txt = (u'昨收上涨%.1f%%' % (-_pb_raw)) if _pb_raw < 0 else (u'%.1f%%' % _pb_raw)",
    "        log('  第%d优先 %s %s T0=%s 基准量=%.0f 昨量/基准量=%.2f 昨收回撤=%s 涨停收盘=%.2f 第%d天 %s | %s' %",
    "            (i + 1, c['stock'], c['name'], c['t0'], c['base_vol'], c['shrink_rank'],",
    "             _pb_txt, c['zt_close'], c['offset'], _tt_txt, _fin_txt))",
    "    # V2.6.98(4): 落选明细移到优选行之后 —— 旧顺序是 落选 -> 漏斗'候选4只' -> 市值 -> 亏损表",
    "    #   -> 优选, 先看落选再看候选总数, 读起来是反的。列表在切片前存进 _rej, 此处才打印。",
    "    for _rlc in _rej:",
    "        _rb_raw = _rlc['pullback'] * 100.0",
    "        _rb_txt = (u'昨收上涨%.1f%%' % (-_rb_raw)) if _rb_raw < 0 else (u'%.1f%%' % _rb_raw)",
    "        log('  落选(超出每日优选上限%d只, 按量比升序越小越优) %s %s '",
    "            '昨量/基准量=%.2f 昨收回撤=%s 第%d天'",
    "            % (MAX_DAILY_PICKS, _rlc['stock'], _rlc.get('name') or u'(名称缺失)',",
    "               _rlc['shrink_rank'], _rb_txt, _rlc['offset']))",
]

# ---------------- 块 C2: 7422~7423 候选数口径注 ----------------
C2 = [
    "    log('今日低吸候选共%d只(近7日恰好1个涨停且处于T0+3~T0+7窗口), 优选保留%d只:' %",
    "        (total, len(G.candidates)))",
    "    if total > len(G.candidates):",
    "        # V2.6.98(3): 两个数口径不同必须点明 —— 漏斗那行打的是截断前计数 total,",
    "        #   状态行'候选N只'打的是 len(G.candidates)(已截断)。2026-10-20 00:48 的日志里",
    "        #   同时出现 '候选4只' 和 '候选2只', 不说明会误判成丢股。",
    "        log('  注: 上方漏斗\"候选%d只\"为截断前计数, 状态行\"候选N只\"只统计实际入库的%d只; '",
    "            '差出的%d只已按每日优选上限落选(明细见本行下方)' %",
    "            (total, len(G.candidates), total - len(G.candidates)))",
]

# ---------------- 块 C1: 7322~7328 只存不打印 ----------------
C1 = [
    "        # V2.6.98(4): 这里只把落选者存进局部 _rej, 打印挪到优选行之后(见本函数末尾)。",
    "        #   旧版在切片前就地打印, 日志顺序成了 落选 -> 漏斗'候选4只' -> ... -> 优选。",
    "        _rej = list(G.candidates[MAX_DAILY_PICKS:])",
    "        # P2-6: 构建纪律 —— 整表截断替换(原子引用换新列表), 不局部删改",
    "        G.candidates = G.candidates[:MAX_DAILY_PICKS]",
    "    else:",
    "        _rej = []                   # V2.6.98(4): 未触发截断时也要有名字, 末尾循环统一处理",
]

# ---------------- 块 A: 3422~3427 数据阶段中文 ----------------
A = [
    "    _ds = '' if bool(getattr(G, 'loss_data_ok', True)) else ' | 财务数据=【不可用】(缺失股票已保守剔除，待补数重筛)'",
    "    # V2.6.98(1): 这一位原来直接把 dl_phase 的整数印成'初始化阶段', 但它在代码里的含义是",
    "    #   0=阶段机空闲 / 1=下载中 / 2=待加载, 而初始化完成后(5497)恰好把 dl_phase 重置为 0 ——",
    "    #   于是'已完成'被印成 '初始化阶段=0', 字面像'还没开始'。2026-10-20 两份日志正好相反:",
    "    #   00:22:35(下载中)打 =1, 00:47:54(已完成)打 =0, 看日志的人会以为后者没准备好。",
    "    _ph_map = {0: u'已完成', 1: u'下载中', 2: u'待加载'}",
    "    _ph_val = int(sig[2] or 0)",
    "    _ph_txt = _ph_map.get(_ph_val, u'未知%d' % _ph_val)",
    "    log('策略状态更新 | 时段=%s | 数据阶段=%s(dl_phase=%d) | 账号=%s | 状态文件=%s | 持仓%d只 候选%d只 | %s | 买入%d笔 卖出%d笔%s'",
    "        % (PHASE_NAME.get(sig[1], sig[1]), _ph_txt, _ph_val,",
    "           '就绪' if G.acct_ok is not False else '异常',",
    "           '异常' if G.state_broken else '正常', len(sig[6]), len(sig[5]),",
    "           pnl_brief(), sig[7], sig[8], _ds))   # V2.6.50b: 当日买卖笔数(账本口径, sig第7/8位)",
]

# ---------------- 从后往前替换 ----------------
for tag, i0, i1, new in (('D', 7460, 7462, D), ('C3', 7437, 7439, C3),
                         ('C2', 7422, 7423, C2), ('C1', 7322, 7328, C1),
                         ('A', 3422, 3427, A)):
    old = L[i0 - 1:i1]
    L[i0 - 1:i1] = new
    print('[%s] %d 行 -> %d 行' % (tag, len(old), len(new)))

# ---------------- 版本头 + VERSION ----------------
HDR = (
    "版本号: V2.6.98              修改时间: 2026-10-20 00:55 (V2.6.98记录: 用户回\"全部修复, 根据你的推荐思路\", "
    "落地 5 项 —— 1 项真风险 + 4 项零风险日志, 不改任何交易/风控/取数逻辑, 参数指纹 8a4ab7e8 不变。"
    "【2 真风险,P2】rescreen_if_needed 只 load_history() 读本地缓存、从不下载, 而 stage2 无条件写 "
    "last_init_date=today, 于是'某天首轮只读到500只'= 当天不重下 + 每300秒纯读重试 + 永远补不上 = 整天空仓"
    "(2026-10-20 00:47 日志首次走到这条路径, 拿到5222只故未触发) -> 连续3次(约15分钟)仍不足则清空 "
    "last_dl_date/last_init_date 重置阶段机, 让 step_day_init 按正常流程重下(最多重置2次; 无下载接口时只告警)。"
    "【1 日志】'初始化阶段=0'字面是反的(dl_phase 完成后被重置为0, 但0本义是'未开始') -> 改印 已完成/下载中/待加载(dl_phase=N)。"
    "【3 日志】漏斗'候选4只'是截断前计数、状态行'候选2只'是截断后, 同份日志两个数字不说明会误判丢股 -> 补一行口径注。"
    "【4 日志】落选明细原打在切片前, 日志顺序成 落选->漏斗->优选, 读着是反的 -> 改存 _rej 后在优选行之后打。"
    "【5 日志】回撤为负(昨收高于涨停收盘)原印成'昨收回撤=-1.9%' -> 换算成'昨收上涨1.9%'。)"
)
if not L[4].startswith('版本号: V2.6.97'):
    raise SystemExit('版本头第5行不是 V2.6.97: %r' % L[4][:60])
L.insert(4, HDR)
print('[HDR] 已插入 V2.6.98 记录')

if not L[348].startswith("VERSION = 'V2.6.97'"):
    raise SystemExit('VERSION 行不在 349: %r' % L[348][:60])
L[348] = L[348].replace("VERSION = 'V2.6.97'", "VERSION = 'V2.6.98'", 1)
print('[VER] VERSION -> V2.6.98')

out = '\r\n'.join(L)
compile(out, P, 'exec')      # 熔断
b = out.encode('gbk')
io.open(P, 'wb').write(b)
print('已写回: %d 行 / %d 字节 / MD5 %s / CRLF %d'
      % (len(L), len(b), hashlib.md5(b).hexdigest().upper(), b.count(b'\r\n')))
