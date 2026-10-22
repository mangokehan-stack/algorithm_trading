# -*- coding: utf-8 -*-
"""V2.6.158 -> V2.6.159 补丁: 审计问题 5/7/8/9/10 收尾。
全程二进制读写, 母版保持 GBK + CRLF。
"""
import io, os, sys, hashlib, datetime, ast

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
src = raw.decode('gbk')
assert src.encode('gbk') == raw, 'GBK 往返失败'
print('原文件 %d 字节' % len(raw))

OLD_VER, NEW_VER = 'V2.6.158', 'V2.6.159'
assert src.count("VERSION = '" + OLD_VER + "'") == 1
assert src.count('# 版本号: ' + OLD_VER) == 1

_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
print('落盘时间 =', _now)

EDITS = []


def add(name, old, new):
    EDITS.append((name, old, new))


def _crlf(s):
    return s.replace('\r\n', '\x00').replace('\n', '\r\n').replace('\x00', '\r\n')


# ============================================================
# ⑤ 止盈滞涨确认: 去掉与"放量"天然矛盾的涨幅硬条件(方案B)
# ============================================================
add('5a-docstring',
"""    \"\"\"卖出侧"滞涨确认"(2026-10-02 借鉴: 高位放量滞涨才是真派发)。
    滞涨 = ①涨不动(现价较昨收涨幅 <= STALL_MAX_GAIN_PCT) 且 ②未创新高
           (现价 < 近 STALL_NEWHIGH_DAYS 个【已完成】交易日最高价 x (1-STALL_NEWHIGH_GAP))。
    返回 (是否确认滞涨, 说明串, 是否因数据缺失而降级)。
    数据缺失时返回 (True, '', True) —— 退回纯量能口径, 不因缺数据改变既有卖出行为。\"\"\"""",
"""    \"\"\"卖出侧"滞涨确认"(2026-10-02 借鉴: 高位放量滞涨才是真派发)。
    V2.6.159(用户选方案B): 主判据改为 ②未创新高
           (现价 < 近 STALL_NEWHIGH_DAYS 个【已完成】交易日最高价 x (1-STALL_NEWHIGH_GAP))。
    ①涨幅门槛只在"近高取不到"时兜底。原因: 放量 1.9 倍通常伴随大涨, 与"涨幅<=1%"天然矛盾,
    两条同时要求等于几乎不触发 —— 实盘表现就是策略自本次上线以来从未自动止盈过。
    返回 (是否确认滞涨, 说明串, 是否因数据缺失而降级)。
    数据缺失时返回 (True, '', True) —— 退回纯量能口径, 不因缺数据改变既有卖出行为。\"\"\"""")

add('5b-判据',
"""        c1 = gain <= STALL_MAX_GAIN_PCT
        c2 = True
        hi_note = '近高不可得'
        n = int(STALL_NEWHIGH_DAYS)
        # 只用【已完成】日线(剔除当日行), 避免盘中未完成数据干扰"是否创新高"
        rows = [r for r in (G.hist.get(s) or []) if str(r.get('date', '')) != str(G.today)]
        if n > 0 and rows:
            hi = max([_f(r.get('high', 0.0)) for r in rows[-n:]])
            if hi > 0:
                c2 = lp < hi * (1 - STALL_NEWHIGH_GAP)
                hi_note = '近%d日最高%.2f' % (min(n, len(rows)), hi)
        if c1 and c2:
            return True, ('滞涨确认(放量当日仅涨%.2f%%<=%.2f%%, 且未创%s)'
                          % (gain * 100, STALL_MAX_GAIN_PCT * 100, hi_note)), False
        if not c1:
            return False, ('现价较昨收涨%.2f%%>%.2f%%(价还在涨, 疑换手后再上攻)'
                           % (gain * 100, STALL_MAX_GAIN_PCT * 100)), False
        return False, ('已创%s(价在新高, 疑换手后再上攻)' % hi_note), False""",
"""        c1 = gain <= STALL_MAX_GAIN_PCT
        c2 = True
        c2_ok = False       # V2.6.159: 近高是否真的取到 —— 取不到才退回看涨幅
        hi_note = '近高不可得'
        n = int(STALL_NEWHIGH_DAYS)
        # 只用【已完成】日线(剔除当日行), 避免盘中未完成数据干扰"是否创新高"
        rows = [r for r in (G.hist.get(s) or []) if str(r.get('date', '')) != str(G.today)]
        if n > 0 and rows:
            hi = max([_f(r.get('high', 0.0)) for r in rows[-n:]])
            if hi > 0:
                c2 = lp < hi * (1 - STALL_NEWHIGH_GAP)
                c2_ok = True
                hi_note = '近%d日最高%.2f' % (min(n, len(rows)), hi)
        # V2.6.159(方案B): 只要近高取到, 就只按"有没有创出近N日新高"判 —— 放量却过不了前高,
        #   无论当日涨了多少都算派发。涨幅门槛仅在近高缺失时兜底, 仍可作最后一道判据。
        if c2_ok:
            if c2:
                return True, ('滞涨确认(放量当日涨%.2f%%, 未创%s)' % (gain * 100, hi_note)), False
            return False, ('已创%s(价在新高, 疑换手后再上攻)' % hi_note), False
        if c1:
            return True, ('滞涨确认(近高不可得, 退用涨幅%.2f%%<=%.2f%%)'
                          % (gain * 100, STALL_MAX_GAIN_PCT * 100)), False
        return False, ('现价较昨收涨%.2f%%>%.2f%%(价还在涨, 疑换手后再上攻; 近高不可得)'
                       % (gain * 100, STALL_MAX_GAIN_PCT * 100)), False""")

add('5c-模块说明',
"""     滞涨 = ①现价较昨收涨幅<=STALL_MAX_GAIN_PCT(默认1%) 且 ②未创近STALL_NEWHIGH_DAYS
     (默认5)个已完成交易日的新高。数据不足时退回纯量能口径。该确认只会让止盈更难触发
     (持有更久), 不新增任何亏损卖出; 置 STALL_CONFIRM_ON=False 即回到纯量能口径。""",
"""     滞涨 = 未创近STALL_NEWHIGH_DAYS(默认5)个已完成交易日的新高; 涨幅门槛
     (STALL_MAX_GAIN_PCT, 默认1%) 只在近高取不到时兜底。V2.6.159 之前的旧口径要求
     "涨幅<=1% 且 未创新高"两条同时成立 —— 放量1.9倍通常伴随大涨, 与前者天然矛盾,
     实盘表现就是从不自动止盈。数据不足时退回纯量能口径, 不新增任何亏损卖出;
     置 STALL_CONFIRM_ON=False 即回到纯量能口径。""")

add('5d-启动横幅',
"""    log('[风控] 卖出滞涨确认=%s(放量【且】滞涨才止盈: 涨幅<=%.2f%% 且未创近%d日新高; '
        '数据缺失时退回纯量能口径) | 该确认只让止盈更难触发, 不新增亏损卖出'
        % (STALL_CONFIRM_ON, STALL_MAX_GAIN_PCT * 100, STALL_NEWHIGH_DAYS))""",
"""    log('[风控] 卖出滞涨确认=%s(放量【且】滞涨才止盈: 未创近%d日新高; '
        '近高取不到时才退回看涨幅<=%.2f%%; 两者都取不到则退回纯量能口径) | '
        '该确认只让止盈更难触发, 不新增亏损卖出'
        % (STALL_CONFIRM_ON, STALL_NEWHIGH_DAYS, STALL_MAX_GAIN_PCT * 100))""")

# ============================================================
# ⑦ 情绪 bootstrap: 刷新标记与信号本体必须同进同出
# ============================================================
add('7a-快照',
"""        _keep_fetch_date = SENT_STATE.get('last_fetch_date')
        _keep_sig_date = SENT_STATE.get('date')
        SENT_STATE.clear()""",
"""        _keep_fetch_date = SENT_STATE.get('last_fetch_date')
        _keep_sig_date = SENT_STATE.get('date')
        # V2.6.159: 旧版只留"今天已刷新"标记、不留信号本体 —— 这是个死锁:
        #   标记留着 -> 刷新入口首句"今天刷过"直接返回, 当天不再取数;
        #   信号本体却被 clear 清空, 就绪开关又是关着的 -> 没人能把它打开。
        #   V2.6.151 起"未就绪即不许买", 于是整天一笔不买, 日志只有一句"还没就绪"。
        #   现在把信号本体一起快照, 标记与本体同进同出。
        _keep_sig = {}
        for _k in ('sentiment', 'regime', 'gate_skip', 'size_mult',
                   'overrides', 'events', 'carried', 'last_sig_ts'):
            if _k in SENT_STATE:
                _keep_sig[_k] = SENT_STATE[_k]
        _keep_ready = bool(_SENTIMENT_READY)
        SENT_STATE.clear()""")

add('7b-恢复',
"""        # V2.6.110: 把 clear 前的刷新标记原样放回(见上方 _keep_* 注释)
        if _keep_fetch_date:
            SENT_STATE['last_fetch_date'] = _keep_fetch_date
        if _keep_sig_date:
            SENT_STATE['date'] = _keep_sig_date
        SENT_STATE['rows'] = []
        _SENTIMENT_READY = False""",
"""        # V2.6.159: 只有"当天已成功刷新 + 信号本体完整 + 当时确实就绪"才把标记放回,
        #   并同时恢复就绪; 任何一项不满足就丢弃标记, 让刷新入口当天正常重取一次 ——
        #   多取一轮最多几十秒, 也绝不能整天卡在未就绪。
        _restored = False
        _drop_note = False
        if _keep_fetch_date and _keep_fetch_date == _sent_today() \\
                and _keep_sig_date and _keep_ready \\
                and _keep_sig.get('sentiment') is not None:
            SENT_STATE['last_fetch_date'] = _keep_fetch_date
            SENT_STATE['date'] = _keep_sig_date
            for _k2 in _keep_sig:
                SENT_STATE[_k2] = _keep_sig[_k2]
            _restored = True
        elif _keep_fetch_date or _keep_sig_date:
            _drop_note = True
        SENT_STATE['rows'] = []
        _SENTIMENT_READY = _restored""")

add('7c-日志',
"""        _sent_wlog('情绪模块初始化: 版本=%s 阶段=%d 参数校验码=%s (数据没准备好前暂停开新仓)'
                   % (SENT_VERSION, _SENTIMENT_PHASE, sent_fingerprint()))""",
"""        _sent_wlog('情绪模块初始化: 版本=%s 阶段=%d 参数校验码=%s (数据没准备好前暂停开新仓)'
                   % (SENT_VERSION, _SENTIMENT_PHASE, sent_fingerprint()))
        if _restored:
            _sent_wlog('情绪信号沿用本进程已算好的结果(日期=%s, 情绪值=%.2f): '
                       '不重取、直接就绪' % (_keep_sig_date, _f(_keep_sig.get('sentiment'))))
        elif _drop_note:
            _sent_wlog('上次的"今日已刷新"标记已丢弃(信号本体不完整), 当天将重新取数一次')""")

# ============================================================
# ⑧ 口径澄清: 两条通道共用同一门槛, 真正要改的是名字
# ============================================================
add('8a-分量名',
"""    _meta = {'z_advpct': '涨跌广度', 'z_limit_up': '涨停家数', 'z_turnover': '成交额'}""",
"""    # V2.6.159: 名字按实际口径改准 —— 这一项统计的是"涨幅>=4.9%的家数"(ST与非ST统一门槛),
    #   不是真涨停家数。旧名会让人拿它对真涨停数比, 一对就差5~10倍, 误以为数据错了。
    _meta = {'z_advpct': '涨跌广度', 'z_limit_up': '强势股家数(涨幅>=4.9%)',
             'z_turnover': '成交额'}""")

add('8b-权重注释',
"""    ('z_limit_up', 0.33),                # 涨停家数占比 z-score""",
"""    ('z_limit_up', 0.33),                # 强势股(涨幅>=4.9%)占比 z-score, 见 _lu_th 的统一门槛""")

add('8c-信号行文案',
"""        _sent_wlog('信号详细构成(涨跌比例z值,涨停比例z值,成交额z值): %s' % _sent_comp_note(sig))""",
"""        _sent_wlog('信号详细构成(涨跌比例z值,强势股比例z值,成交额z值): %s' % _sent_comp_note(sig))""")

add('8d-门槛注释',
"""        def _lu_th(_code):
            return 0.049""",
"""        def _lu_th(_code):
            # V2.6.159: 主路(分批取数)与累积池全量重算都调用本函数, 口径天然一致,
            #   不存在"两条通道各算一套"的问题; 唯一要留心的是它统计的是"涨幅>=4.9%的家数",
            #   比真涨停家数多5~10倍。这是刻意的保守选择(情绪偏高 -> 更易触狂热闸门 -> 少买),
            #   阈值也是按这个口径标定的, 不要单独改这里。
            return 0.049""")

# ============================================================
# ⑨ 委托号表按方向分别登记
# ============================================================
add('9a-辅助函数',
"""def _oid_sort_key(oid):""",
"""def _oid_rec(s, side):
    \"\"\"V2.6.159: 取某只票【指定方向】的委托登记。
    兼容 V2.6.158 及以前的单条结构 {'side','id','ts'} —— 那种结构每只票只留最后一条,
    买与卖互相覆盖, 备注缺失时按方向兜底就会拿到反方向的单号。新结构 {'buy':{},'sell':{}}。\"\"\"
    d = G.state.get('ordids') or {}
    v = d.get(s) if isinstance(d, dict) else None
    if not isinstance(v, dict):
        return {}
    _slot = v.get(side)
    if isinstance(_slot, dict):
        return _slot
    if str(v.get('side', '')) == side:
        return v
    return {}


def _oid_side_of(s, oid):
    \"\"\"V2.6.159: 按委托号反查方向(成交回报备注丢失时的兜底)。返回 'buy'/'sell'/''。\"\"\"
    oid = str(oid or '')
    if not oid:
        return ''
    d = G.state.get('ordids') or {}
    v = d.get(s) if isinstance(d, dict) else None
    if not isinstance(v, dict):
        return ''
    for _sd in ('buy', 'sell'):
        _slot = v.get(_sd)
        if isinstance(_slot, dict) and str(_slot.get('id', '') or '') == oid:
            return _sd
    if str(v.get('id', '') or '') == oid:
        return str(v.get('side', '') or '')
    return ''


def _oid_known(s, oid):
    \"\"\"V2.6.159: 该委托号是否登记在本策略该股的任一方向(对账撤遗留单用, 只判存在)。\"\"\"
    return bool(_oid_side_of(s, oid))


def _oid_sort_key(oid):""")

add('9b-写入口',
"""        d = G.state.get('ordids')
        if not isinstance(d, dict):
            d = {}
            G.state['ordids'] = d
        d[code] = {'side': side, 'id': oid, 'ts': time.time()}""",
"""        d = G.state.get('ordids')
        if not isinstance(d, dict):
            d = {}
            G.state['ordids'] = d
        # V2.6.159: 按方向分开存 —— 旧结构 d[code] 只留最后一条, 买入登记会被卖出覆盖,
        #   备注缺失时按方向兜底就查到反方向的单号(轻微: 柜台正常回传备注时不触发)。
        _cur = d.get(code)
        if isinstance(_cur, dict) and (isinstance(_cur.get('buy'), dict)
                                       or isinstance(_cur.get('sell'), dict)):
            _slot = _cur
        else:
            _slot = {'buy': {}, 'sell': {}}
            if isinstance(_cur, dict) and str(_cur.get('side', '')) in ('buy', 'sell') \\
                    and str(_cur.get('id', '') or ''):
                _slot[str(_cur['side'])] = {'id': str(_cur['id']),
                                            'ts': _f(_cur.get('ts', 0.0))}
        _slot[side] = {'id': oid, 'ts': time.time()}
        d[code] = _slot""")

add('9c-own_order',
"""    rec = (G.state.get('ordids') or {}).get(s) or {}
    return str(rec.get('side', '')) == side""",
"""    # V2.6.159: 按方向取登记(旧结构自动兼容) —— 原来是整条记录比对方向, 买卖一覆盖就判错
    return bool(str(_oid_rec(s, side).get('id', '') or ''))""")

add('9d-find_order',
"""    rec = (G.state.get('ordids') or {}).get(s) or {}
    rec_id = str(rec.get('id', '')) if str(rec.get('side', '')) == side else ''""",
"""    # V2.6.159: 按方向取登记单号(旧结构自动兼容)
    rec_id = str(_oid_rec(s, side).get('id', '') or '')""")

add('9e-对账撤遗留单',
"""                        _od = (G.state.get('ordids') or {}).get(ocode) or {}
                        if str(_od.get('id', '') or '') == oid:
                            continue          # ordids 精确登记: 正常在途, 不动""",
"""                        # V2.6.159: 任一方向登记过就算正常在途(此处不区分方向, 只判存在)
                        if _oid_known(ocode, oid):
                            continue          # ordids 精确登记: 正常在途, 不动""")

add('9f-成交回报反查方向',
"""                _rec_q = (G.state.get('ordids') or {}).get(code) or {}
                if str(_rec_q.get('id', '') or '') == _oid_q:
                    _qside = str(_rec_q.get('side', '') or '')
                    if _qside == 'buy':
                        side = 'BUY'
                    elif _qside == 'sell':
                        side = 'SELL'""",
"""                # V2.6.159: 按委托号在两个方向里反查(旧结构自动兼容)
                _qside = _oid_side_of(code, _oid_q)
                if _qside == 'buy':
                    side = 'BUY'
                elif _qside == 'sell':
                    side = 'SELL'""")

add('9g-下单异常回调',
"""        current = (G.state.get('ordids') or {}).get(code) or {}
        current_oid = str(current.get('id', '') or '')""",
"""        # V2.6.159: 按本笔方向取登记; 方向不明时退回"两个方向里取较新的那条"(与旧行为等价)
        if op == 23:
            current = _oid_rec(code, 'buy')
        elif op == 24:
            current = _oid_rec(code, 'sell')
        else:
            _cb, _cs = _oid_rec(code, 'buy'), _oid_rec(code, 'sell')
            current = _cb if _f(_cb.get('ts', 0.0)) >= _f(_cs.get('ts', 0.0)) else _cs
        current_oid = str(current.get('id', '') or '')""")

# ============================================================
# ⑩ 死代码清理
# ============================================================
add('10a-不可达return',
"""        return False



    return data

def risk_excluded(s):""",
"""        return False

def risk_excluded(s):""")

add('10b-ready死写入1',
"""        SENT_STATE['ready'] = True
        SENT_STATE['date'] = _d""",
"""        SENT_STATE['date'] = _d""")

add('10c-ready死写入2',
"""        SENT_STATE['ready'] = True
        SENT_STATE['date'] = sig['date']""",
"""        SENT_STATE['date'] = sig['date']""")

add('10d-ready死写入3',
"""        SENT_STATE['ready'] = False
        SENT_STATE['gate_skip'] = False""",
"""        SENT_STATE['gate_skip'] = False""")

add('10e-ready死写入4',
"""    SENT_STATE['ready'] = False
    SENT_STATE['err'] = why""",
"""    SENT_STATE['err'] = why""")

add('10f-注释与代码对齐',
"""        # V2.6.106: 整批一次成功 -> 直接并入累积容器(acc); 空 DataFrame 不算取到。
        if acc is not None and _n > 0:""",
"""        # V2.6.106: 整批一次成功 -> 直接并入累积容器(acc)。
        # V2.6.159: 原注释写"空 DataFrame 不算取到", 但代码只判 is not None —— 空对象会被
        #   计入 box[0](成功只数), 覆盖率的分子因此偏乐观; 真正的剔除发生在解析段(取不到
        #   收盘价/昨收的行被跳过, 不进涨跌统计)。此处按实际行为改注释, 不动判据。
        if acc is not None and _n > 0:""")

# ============================================================
# 版本号
# ============================================================
HEAD = (
    "# 版本号: " + NEW_VER + "             修改时间: " + _now + " ("
    + NEW_VER + ": 收尾审计问题 5/7/8/9/10, 交易参数一个未动, 无新增模块级大写常量, "
    "参数指纹必仍为 efb96534。★ 本版唯一的策略行为变化是 ⑤ 止盈口径, 其余四项均为"
    "逻辑纠错或清理。 ⑤ 放量止盈原先要求「放量1.9倍 且 涨幅<=1% 且 未创近5日新高」三条同时成立, "
    "而放量1.9倍通常伴随大涨, 与「涨幅<=1%」天然矛盾 —— 实盘结果就是策略自上线以来从未自动止盈过, "
    "唯一稳定出口只剩「持有满33个交易日且盈利」。按用户选定的方案B改为: 主判据只看「未创近5日新高」, "
    "涨幅门槛只在近5日高点取不到时兜底; 放量+盈利+没创出前高即视为派发, 该卖就卖。"
    "扣完全部费用净利为正才卖这道闸门一行未动。 "
    "⑦ 情绪模块启动时的死锁: 旧版 clear 后只把「今天已刷新」标记放回、却把信号本体清空了 —— "
    "刷新入口首句见「今天刷过」直接返回, 当天不再取数, 而就绪开关是关着的没人能打开, "
    "于是整天未就绪、一笔不买。现改为标记与信号本体同进同出: 信号完整才放回标记并恢复就绪, "
    "任何一项缺失就丢弃标记让当天重取一次。 "
    "⑧ 两条情绪取数通道的涨停口径经复核其实完全一致(都调同一个门槛函数), 上一轮「差5~10倍」的"
    "结论是把「4.9%门槛与真涨停的差距」误当成了「两条通道不一致」。真正要改的是名字: "
    "这一项统计的是涨幅>=4.9%的家数, 现把「涨停家数」改称「强势股家数(涨幅>=4.9%)」, "
    "避免拿它跟真涨停数比而误判数据出错。 "
    "⑨ 委托号登记表原来每只票只留一条, 买入登记会被卖出覆盖; 改为按买/卖两个方向分开存, "
    "读取处全部换成按方向取(旧结构自动兼容), 柜台不回传备注时按方向兜底不再拿到反方向的单号。 "
    "⑩ 清理: 删掉一处永远走不到的返回、四处只写不读的就绪字段, 并把一处与代码不符的注释改准。 "
    "仍未处理(等用户拍板): 601595 少记的5元无法自动恢复; 若干处重复但可读的赋值块保留不动。)"
)

add('ver-const', "VERSION = '" + OLD_VER + "'", "VERSION = '" + NEW_VER + "'")

# ---------- 执行 ----------
out = src
for name, old, new in EDITS:
    o = _crlf(old)
    n = _crlf(new)
    c = out.count(o)
    if c != 1:
        print('[FAIL] %-18s 锚点命中 %d 次(应为1)' % (name, c))
        sys.exit(1)
    out = out.replace(o, n, 1)
    print('[OK] %-18s 命中 1 次' % name)

_pos = out.index('# 版本号: ' + OLD_VER)
out = out[:_pos] + _crlf(HEAD) + '\r\n' + out[_pos:]
print('[OK] %-18s 已插入' % 'ver-head')

assert len(NEW_VER) == len(OLD_VER)
assert out.count("VERSION = '" + NEW_VER + "'") == 1
assert out.count('# 版本号: ' + NEW_VER) == 1

enc = out.encode('gbk')
assert enc.decode('gbk') == out, 'GBK 往返失败'
ast.parse(out)

nseg = out.count('\r\n')
bare_lf = out.count('\n') - nseg
bare_cr = out.count('\r') - nseg
print('段数 = %d, 裸LF = %d, 裸CR = %d' % (len(out.split('\r\n')), bare_lf, bare_cr))
if bare_lf or bare_cr:
    sys.exit('换行不干净')

tmp = P + '.tmp'
open(tmp, 'wb').write(enc)
os.replace(tmp, P)
d2 = open(P, 'rb').read()
print('落盘 %d 字节 MD5=%s' % (len(d2), hashlib.md5(d2).hexdigest()[:8]))
