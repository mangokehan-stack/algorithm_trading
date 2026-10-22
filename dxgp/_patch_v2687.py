# -*- coding: utf-8 -*-
"""V2.6.87 补丁: 六项一次落地
【1】批量取数失败拆 100/30 重试 + 报错带类型与 repr + 覆盖率如实上报
【2B】覆盖率不足沿用上一次成功信号(跨重启, 磁盘缓存), 无历史才降级中性
【3】信号行标注分量可用性
【4】ready 打印区分"取数中/未发起/已就绪"
【5】双实例心跳检测(每实例独立心跳文件, 只告警不阻断)
【6】buy_stock 入参 lp<=0 保护
"""
import io

P = 'zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
t = raw.decode('gbk')
assert '\r\n' in t, 'CRLF 丢失'
lines = t.split('\r\n')


def rep(old, new, tag):
    global t
    # 母版是 CRLF, 脚本内多行锚点写的是 LF —— 统一归一到 CRLF 再匹配
    old = old.replace('\r\n', '\n').replace('\n', '\r\n')
    new = new.replace('\r\n', '\n').replace('\n', '\r\n')
    n = t.count(old)
    assert n == 1, '[%s] 锚点匹配 %d 次(应为1)' % (tag, n)
    t = t.replace(old, new, 1)
    print('OK %s' % tag)


# ============ 【1】大块重构: 分批取数 ============
NEW_D = r"""        _fields = ['close', 'preClose']
        _stats = {}
        # V2.6.87(覆盖率如实统计): 旧版一批300只失败就 continue 整批丢弃, 日志只有一行
        #   "第N批失败: "且异常文本常为空; 而完成日志打的是"标的%d只"=股票池长度 ——
        #   实测18批里14批失败时实际只用了前4批1200只(23%), 日志却显示满覆盖; 且排序后
        #   前1200只全是 000/001/002 段(缺创业板/科创板/沪市/北交所), 涨跌广度与涨停占比
        #   被系统性带偏(同一数据日 20261016 的 sentiment 从 -1.27 漂到 -1.00)。
        #   现在: 失败批次自动拆 100 -> 30 重试, 成功/失败/重试次数全部如实上报。
        _cov = {'req': len(_stocks), 'ok': 0, 'fail': 0, 'retry': 0,
                'ratio': None, 'samples': [], 'fields_all': False}
        for _attempt in (0, 1):   # 第2轮改用全字段(兼容个别客户端不认preClose字段名)
            _stats = {}
            _box = [0, 0, 0, []]        # [成功只数, 失败只数, 拆分重试次数, 失败样本]
            for _i in range(0, len(_stocks), 300):
                _batch = _stocks[_i:_i + 300]
                _md = _sent_fetch_md_batch(C, _batch, _fields, _start, _cnt, _box, 0)
                for _s, _raw in _md.items():
                    _th = _lu_th(_s)
                    for _d, _row in _bars_to_dict(_raw).items():
                        if _d < _start:
                            continue   # 只统计窗口内日期(与旧版口径一致)
                        _c = _f((_row or {}).get('close'))
                        _p = _f((_row or {}).get('preClose'))
                        if _c <= 0 or _p <= 0:
                            continue   # 剔除无效行(停牌/缺失), 防 inf
                        _pct = _c / _p - 1.0
                        _st = _stats.get(_d)
                        if _st is None:
                            _st = _stats[_d] = [0, 0, 0]
                        if _pct > 0:
                            _st[0] += 1
                        elif _pct < 0:
                            _st[1] += 1
                        if _pct >= _th:
                            _st[2] += 1
            if _stats:
                _cov['ok'], _cov['fail'], _cov['retry'] = _box[0], _box[1], _box[2]
                _cov['samples'] = _box[3]
                _cov['fields_all'] = not _fields
                break
            if _attempt == 0:
                _sent_wlog('close/preClose字段取数为空, 改用全字段重试(兼容个别客户端)')
                _fields = []
        _cov['ratio'] = (float(_cov['ok']) / float(_cov['req'])) if _cov['req'] > 0 else 0.0
        SENT_STATE['cover'] = _cov
        if not _stats:
            _sent_wlog('全市场行情为空(内置接口), 情绪数据跳过(中性)')
            return None
        # 2) 上证指数成交额(内置行情; 失败仅缺该字段, 不阻断整体)
        _amt_map = {}
        try:
            _idx = _api(C.get_market_data_ex, ['amount'], [SENT_INDEX_SYMBOL], '1d',
                                              _start, '', _cnt, 'front', False, False)
            if isinstance(_idx, dict):
                for _d, _row in _bars_to_dict(_idx.get(SENT_INDEX_SYMBOL)).items():
                    if _d < _start:
                        continue
                    _v = _f((_row or {}).get('amount'))
                    if _v > 0:
                        _amt_map[_d] = _v
        except Exception as _e:
            _sent_wlog('上证指数量能获取失败(仅缺成交额字段, 不阻断): %s' % _exc_text(_e))
        # 3) 组装(rows结构与旧版完全一致, 下游无需改动)
        rows = []
        for _d in sorted(_stats.keys()):
            _adv, _dec, _lu = _stats[_d]
            rows.append({
                'date': _d,
                'mkt_advance': float(_adv),
                'mkt_decline': float(_dec),
                'limit_up_cnt': float(_lu),
                'mkt_amount': _amt_map.get(_d),
            })
        if not rows:
            _sent_wlog('情绪历史行为空, 情绪数据跳过(中性)')
            return None
        _ratio_pct = _cov['ratio'] * 100.0 if _cov['ratio'] is not None else 0.0
        _sent_wlog('内置通道取数完成: 请求%d只 成功%d只(覆盖率%.1f%%) 失败%d只 拆分重试%d次 '
                   '字段=%s | 预下载%d只 覆盖日期%d天 窗口起点%s'
                   % (_cov['req'], _cov['ok'], _ratio_pct, _cov['fail'], _cov['retry'],
                      '全字段' if _cov['fields_all'] else 'close/preClose',
                      _prefetched, len(rows), _start))
        if _cov['samples']:
            _sent_wlog('取数失败样本(最多3条): %s' % ' ; '.join(_cov['samples']))
        if _cov['ratio'] is not None and _cov['ratio'] < SENT_COVERAGE_MIN:
            _sent_wlog('[告警] 行情覆盖率不足(%.1f%% < %.0f%%): 上游将沿用上一次成功信号, '
                       '本次结果不采用 —— 请检查QMT行情接口/登录状态/是否多实例争用'
                       % (_ratio_pct, SENT_COVERAGE_MIN * 100.0))
        return rows"""

assert lines[11349].strip() == "_fields = ['close', 'preClose']", lines[11349][:60]
assert lines[11420].strip() == 'return rows', '尾部行不符: %r' % lines[11420][:60]
lines[11349:11421] = NEW_D.split('\n')
t = '\r\n'.join(lines)
print('OK 【1】分批取数重构 (%d 行)' % len(NEW_D.split('\n')))


# ============ 新增常量 ============
rep(
    "SENT_INDEX_SYMBOL = '000001.SH'          # 情绪指数: 上证指数成交额(内置行情字段)\r\n",
    "SENT_INDEX_SYMBOL = '000001.SH'          # 情绪指数: 上证指数成交额(内置行情字段)\r\n"
    "SENT_COVERAGE_MIN = 0.90                 # V2.6.87: 行情覆盖率下限(实际取到只数/股票池);\r\n"
    "                                         #   低于此值不再用残缺样本算指数(会按剩余分量重新\r\n"
    "                                         #   归一化权重, 等于悄悄换了一条指数), 改为沿用上次信号\r\n"
    "SENT_CARRY_LOG_SEC = 1800                # V2.6.87: 沿用上次信号期间, 告警日志最小间隔(秒)\r\n"
    "SENT_CACHE_FILE = 'zt_shrink_sent_cache.json'   # V2.6.87: 上一次成功信号缓存(跨重启沿用)\r\n"
    "HEARTBEAT_FILE = 'zt_shrink_heartbeat.json'     # V2.6.87: 实例心跳文件(实际名带账号+PID)\r\n"
    "HEARTBEAT_SEC = 30                       # V2.6.87: 心跳写入/双实例检查间隔(秒)\r\n"
    "HEARTBEAT_STALE_SEC = 120                # V2.6.87: 心跳超过该秒数视为该实例已退出\r\n"
    "HEARTBEAT_ALERT_SEC = 300                # V2.6.87: 双实例告警最小间隔(秒)\r\n",
    '常量区')


# ============ 新增 _exc_text ============
rep(
    "def _sent_wlog(msg):",
    "def _exc_text(e):\r\n"
    "    # V2.6.87: 异常文本统一格式化 —— 旧版直接 str(e), 而 QMT 底层异常(接口争用/\r\n"
    "    #   未登录/参数不支持)的 str() 常为空, 日志只剩\"第5批失败: \"后面一片空白,\r\n"
    "    #   等于没写, 排查时完全看不出是哪类错误。这里补上类型名 + repr 兜底。\r\n"
    "    try:\r\n"
    "        _s = str(e)\r\n"
    "    except Exception:\r\n"
    "        _s = ''\r\n"
    "    _t = type(e).__name__\r\n"
    "    if _s:\r\n"
    "        return '%s: %s' % (_t, _s)\r\n"
    "    try:\r\n"
    "        _r = repr(e)\r\n"
    "    except Exception:\r\n"
    "        _r = ''\r\n"
    "    if _r and _r != 'None':\r\n"
    "        return '%s(无消息): %s' % (_t, _r)\r\n"
    "    return '%s(无异常消息; 常见于接口争用/客户端未登录/参数不支持)' % _t\r\n"
    "\r\n"
    "\r\n"
    "def _sent_wlog(msg):",
    '_exc_text')


# ============ 新增 缓存 + 沿用 + 批量取数辅助 ============
NEW_HELPERS = r'''def _sent_cache_path():
    """上一次成功信号缓存路径(带账号隔离后缀): 与状态文件同目录, 仅纯文件名"""
    stem, ext = _split_name(SENT_CACHE_FILE)
    return _join_base(stem + _account_suffix() + ext)


def _sent_cache_load():
    """读上一次成功信号(磁盘缓存); 任何异常返回 {}, 绝不影响主流程。
    V2.6.87: "覆盖率不足沿用上次信号"需要跨重启可用, 而 SENT_STATE 不落盘(重启即丢),
      故单独存一份小缓存。sent_bootstrap 会 clear SENT_STATE, 因此用字典内的
      cache_loaded 标记做"进程内只读一次"(clear 后自动重读, 正好读到最新文件)。"""
    try:
        if SENT_STATE.get('cache_loaded'):
            return SENT_STATE.get('cache') or {}
        SENT_STATE['cache_loaded'] = True
        _d = {}
        _p = _sent_cache_path()
        if os.path.exists(_p):
            with open(_p, 'r', encoding='utf-8') as _fh:
                _d = json.load(_fh)
        if not isinstance(_d, dict):
            _d = {}
        SENT_STATE['cache'] = _d
        return _d
    except Exception:
        SENT_STATE['cache'] = {}
        return {}


def _sent_cache_save(sig):
    """成功算出信号后落盘(原子替换); 失败静默 —— 缓存丢了大不了下次无历史可沿用。"""
    try:
        _d = {
            'date': sig.get('date'),
            'sentiment': sig.get('sentiment'),
            'regime': sig.get('regime'),
            'gate_skip': bool(sig.get('gate_skip')),
            'size_mult': sig.get('size_mult'),
            'overrides': dict(sig.get('overrides') or {}),
            'events': {'frenzy': bool(sig.get('evt_frenzy')),
                       'panic': bool(sig.get('evt_panic'))},
            'ver': VERSION,
            'ts': time.time(),
        }
        _p = _sent_cache_path()
        _tmp = _p + '.tmp'
        with open(_tmp, 'w', encoding='utf-8') as _fh:
            json.dump(_d, _fh, ensure_ascii=True, indent=1)
        os.replace(_tmp, _p)
        SENT_STATE['cache'] = _d
        SENT_STATE['cache_loaded'] = True
    except Exception:
        pass


def _sent_use_last_good(why):
    """V2.6.87(2B): 数据不完整时沿用上一次成功信号; 无历史/已过期才降级中性。
    为什么不是"照算": _sent_compute 会按可用分量重新归一化权重(3分量变2分量), 等于
      悄悄换了一条指数, 而 gate/regime 阈值是按3分量标定的 —— 实测同一数据日 20261016:
      18批全过时 sentiment=-1.27, 只剩4批时 -1.00, 正好压在 panic 阈值 -1.0 上,
      档位会在临界点随机跳变, 恐慌档的"买点推后+缩量更严"保护可能随时消失。
    返回 True=已沿用(交易侧继续用该档位), False=无法沿用(已降级中性)。"""
    global _SENTIMENT_READY
    try:
        _g = _sent_cache_load()
        _d = str(_g.get('date') or '')
        if not _d:
            _sent_degrade_alert(why + '(无历史信号可沿用)')
            _sent_reset_ready(why + '; 无历史信号可沿用')
            return False
        if not _sent_fresh_enough(_d, _sent_today()):
            _sent_degrade_alert(why + '(历史信号已过期 last=%s)' % _d)
            _sent_reset_ready(why + '; 历史信号已过期(last=%s)' % _d)
            return False
        SENT_STATE['ready'] = True
        SENT_STATE['date'] = _d
        SENT_STATE['sentiment'] = _g.get('sentiment')
        SENT_STATE['regime'] = _g.get('regime')
        SENT_STATE['gate_skip'] = bool(_g.get('gate_skip'))
        SENT_STATE['size_mult'] = _g.get('size_mult', 1.0)
        SENT_STATE['overrides'] = dict(_g.get('overrides') or {})
        SENT_STATE['events'] = _g.get('events') or {}
        SENT_STATE['err'] = '沿用上次信号: ' + why
        SENT_STATE['last_sig_ts'] = time.time()
        SENT_STATE['carried'] = True
        _SENTIMENT_READY = True
        # 注意: 绝不写 last_fetch_date —— 沿用不等于"今天已成功刷新", 必须让
        #   SENT_RETRY_SEC 继续节流重试真实数据(V2.6.85 修的就是"降级即锁日"这个坑)。
        _now = time.time()
        if (_now - float(SENT_STATE.get('carry_log_ts') or 0.0)) >= SENT_CARRY_LOG_SEC:
            SENT_STATE['carry_log_ts'] = _now
            _sent_wlog('[告警] %s; 已沿用上一次成功信号(数据日=%s sentiment=%.2f regime=%s), '
                       '非本次实测值 —— 档位/覆写仍生效, 但请检查QMT行情接口(登录/多实例争用)'
                       % (why, _d, _f(_g.get('sentiment')), _g.get('regime')))
            try:
                notify_enqueue('[情绪模块][告警] %s。本次已沿用上一次成功信号(数据日=%s, '
                               'regime=%s), 市场热度过滤仍在生效但已非实时值; 请检查QMT行情接口'
                               '/是否多实例同时运行。' % (why, _d, _g.get('regime')))
            except Exception:
                pass
        return True
    except Exception as _e:
        _sent_reset_ready(why + '; 沿用历史信号异常: %s' % _e)
        return False


def _sent_fetch_md_batch(C, codes, fields, start, cnt, box, depth):
    """取一批行情; 失败逐级拆分重试(300 -> 100 -> 30)。返回 {code: raw}。
    box = [成功只数, 失败只数, 拆分重试次数, 失败样本(最多3条)]
    V2.6.87: 旧版一批300只失败就整批丢弃(continue), 且异常文本常为空, 实测18批里
      14批失败 -> 只剩23%的票且全在前几个代码段。现在失败自动拆分重试,
      并把"取到多少/丢了多少"如实统计给上层。"""
    try:
        _md = _api(C.get_market_data_ex, fields, codes, '1d', start, '',
                   cnt, 'front', False, False)
        if not isinstance(_md, dict):
            raise RuntimeError('返回类型非dict(%s)' % type(_md).__name__)
        _n = 0
        for _c in codes:
            if _md.get(_c) is not None:
                _n += 1
        box[0] += _n
        box[1] += (len(codes) - _n)
        return _md
    except Exception as _e:
        _msg = _exc_text(_e)
        _sz = 100 if depth <= 0 else 30
        if depth >= 2 or len(codes) <= _sz:
            box[1] += len(codes)
            if len(box[3]) < 3:
                box[3].append('%d只: %s' % (len(codes), _msg))
            return {}
        box[2] += 1
        _out = {}
        for _j in range(0, len(codes), _sz):
            _out.update(_sent_fetch_md_batch(C, codes[_j:_j + _sz], fields,
                                             start, cnt, box, depth + 1))
        return _out


def _sent_apply_rows(rows):'''

rep("def _sent_apply_rows(rows):", NEW_HELPERS, '缓存+沿用+批量辅助')


# ============ 【2B】apply_rows 覆盖率分支 ============
rep(
    """        _t = _sent_today()
        if not rows:
            _sent_degrade_alert('数据不可用')
            _sent_reset_ready('数据不可用')
            return""",
    """        _t = _sent_today()
        # V2.6.87(2B): 覆盖率不足 -> 沿用上一次成功信号(无历史才降级中性)。
        #   ratio 为 None 表示"根本没走到行情取数阶段"(由下游 rows 空判断处理)。
        _cov = SENT_STATE.get('cover') or {}
        _ratio = _cov.get('ratio')
        try:
            _ratio = float(_ratio) if _ratio is not None else None
        except Exception:
            _ratio = None
        if _ratio is not None and _ratio < SENT_COVERAGE_MIN:
            _sent_use_last_good(
                '行情覆盖率仅%.1f%%(<%.0f%%下限; 请求%d只/成功%d只/失败%d只/拆分重试%d次)'
                % (_ratio * 100.0, SENT_COVERAGE_MIN * 100.0,
                   int(_cov.get('req') or 0), int(_cov.get('ok') or 0),
                   int(_cov.get('fail') or 0), int(_cov.get('retry') or 0)))
            return
        if not rows:
            _sent_degrade_alert('数据不可用')
            _sent_reset_ready('数据不可用')
            return""",
    '【2B】覆盖率分支')


# ============ 【3】信号行标分量 + 缓存落盘 ============
rep(
    """        _ovs = ';'.join('%s=%s' % (k, sig['overrides'][k]) for k in sorted(sig['overrides'].keys())) or '-'
        _sent_wlog('信号刷新: 数据日=%s sentiment=%.2f regime=%s gate_skip=%s size_mult=%.2f overrides=%s'
                   % (sig['date'], sig['sentiment'], sig['regime'], sig['gate_skip'],
                      sig['size_mult'], _ovs))""",
    """        _sent_cache_save(sig)      # V2.6.87: 成功信号落盘, 供下次数据残缺时沿用
        SENT_STATE['carried'] = False
        _ovs = ';'.join('%s=%s' % (k, sig['overrides'][k]) for k in sorted(sig['overrides'].keys())) or '-'
        _sent_wlog('信号刷新: 数据日=%s sentiment=%.2f regime=%s gate_skip=%s size_mult=%.2f overrides=%s'
                   % (sig['date'], sig['sentiment'], sig['regime'], sig['gate_skip'],
                      sig['size_mult'], _ovs))
        _sent_wlog('信号分量: %s' % _sent_comp_note(sig))""",
    '【3】信号行')


# ============ 【3】分量释义函数 ============
rep(
    "def _sent_compute(rows):",
    "def _sent_comp_note(sig):\r\n"
    "    # V2.6.87(3): 合成指数的分量可用性说明 —— 旧版只打一个总 sentiment, 缺分量时\r\n"
    "    #   按剩余分量重新归一化权重, 阈值却是按3分量标定的, 看日志完全不知道指数定义变了。\r\n"
    "    _meta = {'z_advpct': '涨跌广度', 'z_limit_up': '涨停家数', 'z_turnover': '成交额'}\r\n"
    "    try:\r\n"
    "        _have = list(sig.get('comp_have') or [])\r\n"
    "        _miss = list(sig.get('comp_miss') or [])\r\n"
    "        _tot = int(sig.get('comp_total') or 0)\r\n"
    "        _hs = ','.join(_meta.get(k, k) for k in _have) or '无'\r\n"
    "        if not _miss:\r\n"
    "            return '%s(%d/%d 全可用)' % (_hs, len(_have), _tot)\r\n"
    "        _ms = ','.join(_meta.get(k, k) for k in _miss)\r\n"
    "        return '%s(%d/%d, 缺%s -> 权重已按剩余分量归一化, 阈值仍按%d分量标定)' % (\r\n"
    "            _hs, len(_have), _tot, _ms, _tot)\r\n"
    "    except Exception:\r\n"
    "        return '分量信息不可用'\r\n"
    "\r\n"
    "\r\n"
    "def _sent_compute(rows):",
    '_sent_comp_note')


# ============ 【3】compute 返回分量字段 ============
rep(
    """    if not keys:
        _sent_wlog('情绪分量全部不可用, 无法合成指数')
        return None""",
    """    _all_k = [k for k, _ in SENT_SENTIMENT_WEIGHTS]
    _have_k = [k for k, _, _ in keys]
    _miss_k = [k for k in _all_k if k not in _have_k]
    if not keys:
        _sent_wlog('情绪分量全部不可用, 无法合成指数')
        return None""",
    '【3】compute keys')

rep(
    """        'size_mult': size_mult,
        'overrides': overrides,
    }""",
    """        'size_mult': size_mult,
        'overrides': overrides,
        'comp_have': _have_k,
        'comp_miss': _miss_k,
        'comp_total': len(_all_k),
    }""",
    '【3】compute return')


# ============ 【4】fetching 标志 ============
rep(
    "        _sent_wlog('情绪取数已移交后台线程(不阻塞盘中轮询); 就绪前买入侧全部中性')",
    "        SENT_STATE['fetching'] = True   # V2.6.87(4): 供启动横幅区分\"取数中\"与\"未发起\"\r\n"
    "        _sent_wlog('情绪取数已移交后台线程(不阻塞盘中轮询); 就绪前买入侧全部中性')",
    '【4】fetching=True')

rep(
    """    finally:
        try:
            if _lock is not None:
                _lock.release()
        except Exception:
            pass""",
    """    finally:
        SENT_STATE['fetching'] = False      # V2.6.87(4): 无论成功失败都要落标记, 否则永远显示"取数中"
        try:
            if _lock is not None:
                _lock.release()
        except Exception:
            pass""",
    '【4】fetching=False')


# ============ 【4】ready 打印 ============
rep(
    """            if _SENTIMENT_ON:
                log('[情绪指纹] %s | Phase=%d ready=%s (数据未就绪时全部中性, 不影响原策略)'
                    % (sent_fingerprint(), _SENTIMENT_PHASE, _SENTIMENT_READY))""",
    """            if _SENTIMENT_ON:
                # V2.6.87(4): 就绪标记由后台线程置位, init 阶段必然还没就绪 —— 旧版直接打
                #   ready=False, 与同一秒的"信号刷新"行互相矛盾(像情绪没起来)。现区分三态:
                #   已就绪 / 后台取数中 / 尚未发起, 一眼能看出到底处于哪种。
                if _SENTIMENT_READY:
                    _rd_txt = 'True'
                elif SENT_STATE.get('fetching'):
                    _rd_txt = '取数中(后台线程, 就绪前全部中性)'
                else:
                    _rd_txt = 'False(尚未发起取数, 首轮定时器会拉起)'
                log('[情绪指纹] %s | Phase=%d 就绪=%s (数据未就绪时全部中性, 不影响原策略)'
                    % (sent_fingerprint(), _SENTIMENT_PHASE, _rd_txt))""",
    '【4】ready 打印')


# ============ 【5】心跳函数 ============
HB = r'''_HB_STATE = {'last_ts': 0.0, 'last_alert_ts': 0.0, 'peer': '', 'boot': 0.0}


def heartbeat_path():
    """V2.6.87(5): 本实例心跳文件路径 —— 每实例一个文件(账号+PID), 互不覆盖。
    只有各写各的, 才能同时看到"另一个实例还在跳"; 共用一个文件会互相覆盖, 双方都以为只有自己。"""
    try:
        _pid = os.getpid()
    except Exception:
        _pid = 0
    stem, ext = _split_name(HEARTBEAT_FILE)
    return _join_base('%s%s_%d%s' % (stem, _account_suffix(), _pid, ext))


def heartbeat_tick(force=False):
    """V2.6.87(5): 双实例检测(只告警, 不阻断下单)。
    动机: 2026-10-19 22:25:55 已打出"信号刷新"(last_fetch_date 已写今天), 11秒后又出现
      "情绪取数已移交后台线程" —— 单进程不可能(单测 A1 已证明幂等), 只能是两个进程共写
      同一个 zt_shrink_run.log。双实例会重复下单、互相覆盖状态文件与分批计划/额度,
      且两边各自对账, 仓位会彻底错乱, 而日志里看不出任何异常。
    判定: 同目录同账号后缀的其它心跳文件, ts 仍在 HEARTBEAT_STALE_SEC 内即视为活跃。
    默认只告警 —— 用户确认"只告警不阻断"(误判时不能让策略停摆)。"""
    try:
        _now = time.time()
        if not force and (_now - _HB_STATE['last_ts']) < HEARTBEAT_SEC:
            return
        _HB_STATE['last_ts'] = _now
        _boot = _HB_STATE.get('boot') or _now
        _HB_STATE['boot'] = _boot
        _base = file_base_dir()
        _stem, _ext = _split_name(HEARTBEAT_FILE)
        _pre = _stem + _account_suffix() + '_'
        _me = heartbeat_path()
        # 1) 写自己的心跳(原子替换, 写失败静默 —— 心跳不是交易必需)
        try:
            _tmp = _me + '.tmp'
            with open(_tmp, 'w', encoding='utf-8') as _fh:
                json.dump({'pid': os.getpid(), 'ts': _now,
                           'acc': str(getattr(G, 'accid', '') or ''),
                           'ver': VERSION, 'boot': _boot}, _fh, ensure_ascii=True)
            os.replace(_tmp, _me)
        except Exception:
            pass
        # 2) 找同伴(同账号、非自己、心跳仍新鲜)
        _peers = []
        try:
            for _f in os.listdir(_base):
                if not (_f.startswith(_pre) and _f.endswith(_ext)):
                    continue
                _p = os.path.join(_base, _f)
                if os.path.normpath(_p) == os.path.normpath(_me):
                    continue
                try:
                    with open(_p, 'r', encoding='utf-8') as _fh:
                        _d = json.load(_fh)
                except Exception:
                    continue
                if not isinstance(_d, dict):
                    continue
                _ts = _f(_d.get('ts') or 0.0)
                if (_now - _ts) <= HEARTBEAT_STALE_SEC:
                    _peers.append((int(_f(_d.get('pid') or 0)), _ts,
                                   str(_d.get('ver') or '?'), _f))
        except Exception:
            pass
        if not _peers:
            if _HB_STATE.get('peer'):
                _HB_STATE['peer'] = ''
                log('[安全] 另一个策略实例已退出(心跳不再更新), 当前为单实例运行')
            return
        _peers.sort(key=lambda x: -x[1])
        _pid, _ts, _ver, _fn = _peers[0]
        _desc = 'PID=%d 版本=%s 最后心跳=%.0f秒前 文件=%s 活跃同伴共%d个' % (
            _pid, _ver, _now - _ts, _fn, len(_peers))
        _HB_STATE['peer'] = _desc
        if (_now - _HB_STATE['last_alert_ts']) >= HEARTBEAT_ALERT_SEC:
            _HB_STATE['last_alert_ts'] = _now
            log('[安全][告警] 检测到另一个策略实例正在运行: %s —— 两个实例会重复下单并互相'
                '覆盖状态文件/分批计划/额度, 请立即关闭其中一个(本策略只告警, 不阻断下单)' % _desc)
            try:
                notify_enqueue('[安全][告警] 检测到另一个策略实例正在运行(%s)。双实例会重复'
                               '下单、互相覆盖状态文件, 请立即关闭其中一个!' % _desc)
            except Exception:
                pass
    except Exception:
        pass


def log_guard(ContextInfo=None):'''

rep("def log_guard(ContextInfo=None):", HB, '【5】心跳函数')


# ============ 【5】心跳调用点 ============
rep(
    """def _timer_poll_unlocked(ContextInfo):
    \"\"\"原timer_poll主体(P1-13: 改为内部各段自行持锁, 不再全程持锁)\"\"\"
    now = datetime.datetime.now()""",
    """def _timer_poll_unlocked(ContextInfo):
    \"\"\"原timer_poll主体(P1-13: 改为内部各段自行持锁, 不再全程持锁)\"\"\"
    heartbeat_tick()          # V2.6.87(5): 双实例检测(内部按 HEARTBEAT_SEC 节流)
    now = datetime.datetime.now()""",
    '【5】timer_poll 调用')

rep(
    """def after_init(ContextInfo):
    \"\"\"仅作提示; 策略状态不依赖本函数(老客户端可能不调用它)\"\"\"
    log('after_init: 初始化阶段结束')""",
    """def after_init(ContextInfo):
    \"\"\"仅作提示; 策略状态不依赖本函数(老客户端可能不调用它)\"\"\"
    log('after_init: 初始化阶段结束')
    heartbeat_tick(force=True)   # V2.6.87(5): 启动即检测, 双实例不必等到首轮定时器""",
    '【5】after_init 调用')


# ============ 【6】buy_stock 入参保护 ============
rep(
    "    s = c['stock']   # V2.6.33修复: 由候选字典取股票代码, 供函数体内 s 引用使用",
    "    s = c['stock']   # V2.6.33修复: 由候选字典取股票代码, 供函数体内 s 引用使用\r\n"
    "    # V2.6.87: 入参契约自愈 —— 下方 int(amount / lp / _lot) 在 lp<=0 时会除零崩溃,\r\n"
    "    #   崩溃点不在 try 内, 会直接中断整轮 timer_poll(买卖全停)。主循环虽已拦 lp<=0,\r\n"
    "    #   但函数级不应依赖调用方; 补一行兜底(语义: 无有效价格=不买), 不动任何交易逻辑。\r\n"
    "    if _f(lp) <= 0:\r\n"
    "        log(disp(s), '买入跳过: 无有效价格(lp=%.3f), 无法计算手数' % _f(lp))\r\n"
    "        return None",
    '【6】lp<=0 保护')


open(P, 'wb').write(t.encode('gbk'))
print('WROTE %d bytes' % len(t.encode('gbk')))
