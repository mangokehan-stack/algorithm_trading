# -*- coding: utf-8 -*-
"""V2.6.89 功能补丁 —— 用户 2026-10-19 22:59 回"改"(三项全改):
【1】双实例告警分档: 心跳 120 秒内即判"活跃"太松, 把已退出的残留也算活跃 -> 每次重启必弹误告
【2】换手率可审计: 漏斗拆"过低/过高", 优选项打涨停日换手率
【3】_float_share 的裸 except 补一行节流提示
刻意不新增任何全局大写常量(会进 _fp_keys 改变参数指纹 8a4ab7e8), 分档阈值用 HEARTBEAT_SEC*1.5。
"""
P = 'zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
assert t.count('\r\n') == t.count('\n'), '存在孤立 LF, 拒绝处理'
t = t.replace('\r\n', '\n')
lines = t.split('\n')


def _only(sub):
    idx = [i for i, l in enumerate(lines) if sub in l]
    assert len(idx) == 1, '锚点 %r 命中 %d 次: %r' % (sub, len(idx), [lines[i][:70] for i in idx])
    return idx[0]


# ---------------- 锚点 ----------------
i_hbs = _only("_HB_STATE = {'last_ts': 0.0, 'last_alert_ts': 0.0, 'peer': '', 'boot': 0.0}")
i_sort = _only('        _peers.sort(key=lambda x: -x[1])')
i_notify_tail = _only("'下单、互相覆盖状态文件, 请立即关闭其中一个!' % _desc)")
assert lines[i_notify_tail + 1].strip() == 'except Exception:', repr(lines[i_notify_tail + 1:i_notify_tail + 3])
assert lines[i_notify_tail + 2].strip() == 'pass', repr(lines[i_notify_tail + 2])
i_peer_clear = _only("                _HB_STATE['peer'] = ''")

i_init = _only('st_namefail = st_turnover_missing = st_turnover_calc = 0')
i_gate = _only('        if ZT_TURNOVER_MIN > 0 or ZT_TURNOVER_MAX > 0:')
i_lo = _only('                if ZT_TURNOVER_MIN > 0 and _to < ZT_TURNOVER_MIN:')
i_hi = _only('                if ZT_TURNOVER_MAX > 0 and _to > ZT_TURNOVER_MAX:')
i_f1 = _only('换手率不符%d(自算%d/缺失放行%d)')
i_f2 = _only('% (st_turnover, st_turnover_calc, st_turnover_missing, st_amt')
assert i_f2 > i_f1 and (i_f2 - i_f1) <= 5, (i_f1, i_f2)
i_cand = _only("        G.candidates.append({'stock': s, 'name': inst_name(s), 't0': t0row['date'],")
i_print = _only("        log('  第%d优先 %s %s T0=%s 基准量=%.0f 昨量/基准量=%.2f")
assert lines[i_print + 2].strip().startswith("c['pullback'] * 100"), repr(lines[i_print + 2])

i_fsh = _only('        _c[stock] = (_now, _sh)')
assert lines[i_fsh + 1].strip() == 'return _sh', repr(lines[i_fsh + 1])
assert lines[i_fsh + 2].strip() == 'except Exception:', repr(lines[i_fsh + 2])
assert lines[i_fsh + 3].strip() == 'return 0.0', repr(lines[i_fsh + 3])

# ---------------- 新块 ----------------
new_hbs = '''_HB_STATE = {'last_ts': 0.0, 'last_alert_ts': 0.0, 'peer': '', 'boot': 0.0,
             'peer_kind': '', 'last_stale_ts': 0.0}'''

new_peer = '''        _peers.sort(key=lambda x: -x[1])
        _pid, _ts, _ver, _fn = _peers[0]
        _age = _now - _ts
        _desc = 'PID=%d 版本=%s 最后心跳=%.0f秒前 文件=%s 活跃同伴共%d个' % (
            _pid, _ver, _age, _fn, len(_peers))
        _HB_STATE['peer'] = _desc
        # V2.6.89: 告警分档 —— 旧版把"算不算活跃"和"该不该喊告警"绑在同一个 HEARTBEAT_STALE_SEC=120 上,
        #   可一个真正在跑的实例最多只落后 HEARTBEAT_SEC=30 秒(丢一拍也就约 60 秒)。
        #   实证 2026-10-19 22:55:28: 同伴 PID 18792 的心跳文件 ts 与 boot 完全相同(1792421628.992773),
        #   说明它从启动到消失只写过一拍(22:53:48 那次启动, 30 秒内就没了), 告警时已 99 秒未更新,
        #   却仍被判"活跃"并弹"[告警] 请立即关闭其中一个" —— 每次重启策略都必弹一次, 属纯噪声,
        #   喊多了真出双实例也会被当成"又是重启的误报"而忽略, 反而更危险。
        #   现按 age 分两档: <= 1.5 个心跳周期(45秒) 才算真活着, 喊告警+手机推送;
        #   45~120 秒降为"[提示] 疑似残留心跳", 文案不喊"立即关闭", 只请顺手确认进程。
        #   刻意用 HEARTBEAT_SEC * 1.5 而不新增大写常量: 新增全局常量会进 _fp_keys() 改变参数指纹
        #   (当前 8a4ab7e8), 让 verified_fp 比对凭空失效, 为一个日志分档付这个代价不值得。
        _live_max = HEARTBEAT_SEC * 1.5
        _kind = 'live' if _age <= _live_max else 'stale'
        _prev_kind = _HB_STATE.get('peer_kind') or ''
        _HB_STATE['peer_kind'] = _kind
        if _kind == 'live':
            if (_now - _HB_STATE['last_alert_ts']) >= HEARTBEAT_ALERT_SEC:
                _HB_STATE['last_alert_ts'] = _now
                log('[安全][告警] 检测到另一个策略实例正在运行: %s —— 两个实例会重复下单并互相'
                    '覆盖状态文件/分批计划/额度, 请立即关闭其中一个(本策略只告警, 不阻断下单)' % _desc)
                try:
                    notify_enqueue('[安全][告警] 检测到另一个策略实例正在运行(%s)。双实例会重复'
                                   '下单、互相覆盖状态文件, 请立即关闭其中一个!' % _desc)
                except Exception:
                    pass
        else:
            # 残留档: 只在"刚进入该档"时提示一次(离开再回来才重置), 否则每 30 秒刷一行同样是噪声
            if _prev_kind != 'stale' and (_now - _HB_STATE['last_stale_ts']) >= HEARTBEAT_ALERT_SEC:
                _HB_STATE['last_stale_ts'] = _now
                log('[安全][提示] 检测到疑似残留心跳(非活跃): %s —— 该同伴已超过 %.0f 秒未刷新'
                    '(约 %.1f 个心跳周期), 进程很可能已退出或正在退出, 多见于上次重启没干净退出留下的'
                    'json 文件; 请顺手在任务管理器确认无 PID=%d, 本实例继续运行; 若它确实还在跳, '
                    '下一轮会自动升级为[告警]'
                    % (_desc, _live_max, _live_max / max(HEARTBEAT_SEC, 1), _pid))
                try:
                    notify_enqueue('[安全][提示] 检测到疑似残留心跳(非活跃): %s。若确认无此进程可忽略, '
                                   '若它仍在运行请立即关闭其中一个。' % _desc)
                except Exception:
                    pass'''

new_peer_clear = """                _HB_STATE['peer'] = ''
                _HB_STATE['peer_kind'] = ''"""

new_init = ('    st_namefail = st_turnover_missing = st_turnover_calc = 0'
            '   # 审计P1-1/P1-2: 名称取数失败保守剔除数 / 换手率字段缺失数(不再静默跳过)'
            ' / V2.6.88 换手率自算成功只数\n'
            '    st_turn_lo = st_turn_hi = 0   # V2.6.89: 换手率不符拆两向(低于下限=一字板/流动性不足,'
            ' 高于上限=过热出货) —— 只给总数看不出闸门卡在哪一侧, 调阈值时无从下手')

new_gate = '''        _to = 0.0   # V2.6.89: 先兜底 —— 下方"候选 dict 带上涨停日换手率"要读它,
        #   闸门两个阈值都为 0(关闭)时原代码不会给 _to 赋值, 直接引用会 NameError 打断整轮选股
        if ZT_TURNOVER_MIN > 0 or ZT_TURNOVER_MAX > 0:'''

new_lo = '''                if ZT_TURNOVER_MIN > 0 and _to < ZT_TURNOVER_MIN:
                    st_turn_lo += 1
                    st_turnover += 1
                    continue'''
new_hi = '''                if ZT_TURNOVER_MAX > 0 and _to > ZT_TURNOVER_MAX:
                    st_turn_hi += 1
                    st_turnover += 1
                    continue'''

new_f = '''    log('           -> 换手率不符%d(过低%d/过高%d/自算%d/缺失放行%d) / 成交额不足%d / '
        '板块或名称排除%d(名称取数失败%d) / 历史ST%d / 避雷风险%d / '
        'MA10破位%d / 低点破位%d / 非热门板块%d / 去重%d / 停牌日%d / 市值不符%d -> 候选%d只'
        % (st_turnover, st_turn_lo, st_turn_hi, st_turnover_calc, st_turnover_missing, st_amt,
           st_excl, st_namefail, st_sthist, st_risk, st_ma10, st_lowhold, st_hot,'''.split('\n')

new_cand = ("        G.candidates.append({'stock': s, 'name': inst_name(s), 't0': t0row['date'],\n"
            "                             'turn_t0': _to,   # V2.6.89: 涨停日换手率(小数, 0=字段缺失已放行)"
            " —— 供优选项日志审计, 不参与任何买卖判定")

new_print = '''        # V2.6.89: 把涨停日换手率打进优选项。V2.6.88 首日实跑(20261019)证明闸门确实生效了
        #   (换手率不符50 / 自算121 / 缺失放行0), 但日志只有"总数+自算只数", 候选各自算出来多少看不到,
        #   复核时只能从"它过了闸"倒推 —— 当时据此把 603466 估成约30%属误判, 真实值必须能直接读出来。
        _tt = _f(c.get('turn_t0') or 0)
        _tt_txt = ('涨停日换手=%.1f%%' % (_tt * 100)) if _tt > 0 else '涨停日换手=缺失(已放行)'
        log('  第%d优先 %s %s T0=%s 基准量=%.0f 昨量/基准量=%.2f 昨收回撤=%.1f%% 涨停收盘=%.2f 第%d天 %s | %s' %
            (i + 1, c['stock'], c['name'], c['t0'], c['base_vol'], c['shrink_rank'],
             c['pullback'] * 100, c['zt_close'], c['offset'], _tt_txt, _fin_txt))'''

new_fsh = '''        _c[stock] = (_now, _sh)
        return _sh
    except Exception as _e:
        # V2.6.89: 原来裸 except 直接 return 0.0, 于是"接口抛异常"和"这只票确实没有流通股本字段"
        #   在日志上完全一样(都是 0 -> 走"缺失放行"), 排查时只能靠猜 ——
        #   与 V2.6.87 的 _f 遮蔽、V2.6.88 的心跳静默属同一类"异常被吞"的坑。节流 30 分钟提示一次。
        try:
            if (time.time() - _f(getattr(G, '_fshare_err_ts', 0) or 0)) >= 1800:
                G._fshare_err_ts = time.time()
                log('[提示] 流通股本取数异常(该票换手率退化为"缺失放行", 不误杀也不过滤): %s'
                    % _exc_text(_e))
        except Exception:
            pass
        return 0.0'''

# ---------------- 倒序应用 ----------------
edits = [
    (i_fsh, i_fsh + 3, new_fsh.split('\n')),
    (i_print, i_print + 2, new_print.split('\n')),
    (i_cand, i_cand, [new_cand]),
    (i_f1, i_f2, new_f),
    (i_hi, i_hi + 2, new_hi.split('\n')),
    (i_lo, i_lo + 2, new_lo.split('\n')),
    (i_gate, i_gate, new_gate.split('\n')),
    (i_init, i_init, new_init.split('\n')),
    (i_peer_clear, i_peer_clear, new_peer_clear.split('\n')),
    (i_sort, i_notify_tail + 2, new_peer.split('\n')),
    (i_hbs, i_hbs, new_hbs.split('\n')),
]
edits.sort(key=lambda x: -x[0])
for s, e, blk in edits:
    lines[s:e + 1] = blk
    print('  [OK] 原行 %d-%d -> %d 行' % (s + 1, e + 1, len(blk)))

t = '\n'.join(lines).replace('\n', '\r\n')
open(P, 'wb').write(t.encode('gbk'))
compile(t, P, 'exec')
print('OK V2.6.89 功能补丁, 行数 %d' % len(lines))
