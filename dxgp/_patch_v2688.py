# -*- coding: utf-8 -*-
"""V2.6.88 功能补丁 —— 用户 2026-10-19 22:47 回"改"(四项全改):
【1】换手率闸门 100% 失效 -> 按流通股本自算
【2】心跳启动自证(旧版全程静默)
【3】亏损筛选文案: 已计入避雷风险, 不重复扣除
【4】"基准量不足1" 加空格
"""
P = 'zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
assert t.count('\r\n') == t.count('\n'), '存在孤立 LF, 拒绝处理'
t = t.replace('\r\n', '\n')
lines = t.split('\n')

# ---------- 锚点定位 ----------
def _only(sub):
    idx = [i for i, l in enumerate(lines) if sub in l]
    assert len(idx) == 1, '锚点 %r 命中 %d 次: %r' % (sub, len(idx), [lines[i][:60] for i in idx])
    return idx[0]

i_turn_start = _only('# 换手率过滤(涨停日): 5%-20%为合理')
i_turn_end = _only('st_turnover_missing += 1')
assert i_turn_end > i_turn_start and (i_turn_end - i_turn_start) < 30, (i_turn_start, i_turn_end)

i_init = _only('st_namefail = st_turnover_missing = 0')
i_funnel1 = _only("换手率不符%d(字段缺失%d)")
i_funnel2 = _only('% (st_turnover, st_turnover_missing, st_amt, st_excl, st_namefail')
i_basevol = _only("'基准量<=0 %d / 基准量不足%d'")
i_loss = _only("log('按亏损筛选剔除%d只(归母净利润<0 %d只, 数据缺失/查询异常 %d只)'")
# 心跳 except 段: 紧跟在 os.replace 之后的 except Exception: / pass
i_replace = _only('            os.replace(_tmp, _me)')
assert 'pass' in lines[i_replace + 2], repr(lines[i_replace + 1:i_replace + 4])
i_newfn = _only('def get_recent_net_profit_cached(s):')

# ---------- 替换块 ----------
new_turn = '''        # 换手率过滤(涨停日): 5%-20%为合理, 剔除一字板(<5%)和过热(>20%)
        if ZT_TURNOVER_MIN > 0 or ZT_TURNOVER_MAX > 0:
            # 重审20261005(P2-5/P2-6): load_history 已做百分数→小数归一, 此处不重复再除;
            # 删除无写入点的死标记 turnover_api_unavailable(换手率取不到=0, 由 _to>0 放行不误杀)
            _to = _f(t0row.get('turnover'))
            if _to <= 0:
                # V2.6.88(2026-10-19 实盘日志取证): QMT get_market_data_ex 的日线结果里
                #   根本没有 turnover / turnover_ratio 两列, load_history 写进去的恒为 0 ->
                #   旧版走到了下面"缺失即放行"分支, ZT_TURNOVER_MIN=0.05 / MAX=0.20 自上线起
                #   一次都没生效过(实测: 121 只进入换手率判定, 121 只全部"字段缺失",
                #   换手率不符恒为 0; 一字板与过热出货全被放行进候选)。
                #   现改按流通股本自算: 换手率 = 成交量(手) x 每股股数 / 流通股本(股)。
                #   口径说明: 流通股本取"当前"值, 历史增发/解禁会带偏差, 属可接受近似
                #   (只用于区间过滤, 不参与估值; 偏差远小于不做过滤的后果)。
                _sh_t = _float_share(s)
                _v_t0 = _f(t0row.get('volume'))
                if _sh_t > 0 and _v_t0 > 0:
                    _to = _v_t0 * float(DAILY_VOL_UNIT) / _sh_t
                    if _to > 0:
                        st_turnover_calc += 1
            if _to > 0:
                if ZT_TURNOVER_MIN > 0 and _to < ZT_TURNOVER_MIN:
                    st_turnover += 1
                    continue
                if ZT_TURNOVER_MAX > 0 and _to > ZT_TURNOVER_MAX:
                    st_turnover += 1
                    continue
            else:
                # 审计P1-2: 换手率字段缺失不再静默跳过整条过滤(旧逻辑全市场悄悄
                # 失效且漏斗无计数, 运维看到"过滤正常"假象); 计入缺失数并在汇总明示
                # V2.6.88: 只有"接口没给 + 自算也拿不到流通股本"才落到这里(放行不误杀)
                st_turnover_missing += 1'''

new_init = ('    st_namefail = st_turnover_missing = st_turnover_calc = 0'
            '   # 审计P1-1/P1-2: 名称取数失败保守剔除数 / 换手率字段缺失数(不再静默跳过)'
            ' / V2.6.88 换手率自算成功只数')

new_funnel1 = ("    log('           -> 换手率不符%d(自算%d/缺失放行%d) / 成交额不足%d / "
               "板块或名称排除%d(名称取数失败%d) / 历史ST%d / 避雷风险%d / '")
new_funnel2 = ('        % (st_turnover, st_turnover_calc, st_turnover_missing, st_amt, '
               'st_excl, st_namefail, st_sthist, st_risk, st_ma10, st_lowhold, st_hot,')
new_basevol = "        '基准量<=0 %d / 基准量不足 %d'"
new_loss = ("            log('其中财务亏损剔除%d只(归母净利润<0 %d只, 数据缺失/查询异常 %d只; "
            "已计入上方漏斗\"避雷风险\", 不重复扣除)'")

new_hb = '''            # V2.6.88: 启动时自证一次 —— 旧版全程静默, 心跳到底在不在跑、文件有没有写失败,
            #   日志里一个字都没有, 只能靠人去 bin.x64 翻 json 文件数个数, 等于把可观测性转嫁给运维。
            if force:
                log('[安全] 心跳已就绪: %s (PID=%d, 双实例检测生效, 检测间隔%d秒, 同伴心跳%d秒内视为活跃)'
                    % (os.path.basename(_me), os.getpid(), HEARTBEAT_SEC, HEARTBEAT_STALE_SEC))
        except Exception as _e2:
            # 写失败不再静默: 否则"确实没有同伴"与"检测功能坏了"在日志上完全一样
            # (与 V2.6.87 自查踩到的 _f 遮蔽坑同一类型)
            if force:
                log('[安全][提示] 心跳文件写入失败(双实例检测将不可用): %s' % _exc_text(_e2))'''

new_fn = '''def _float_share(stock):
    """V2.6.88: 取流通股本(股) —— 供换手率自算使用。
    动机: QMT get_market_data_ex 日线不返回 turnover/turnover_ratio 列, load_history 里取到的
      换手率恒为 0, 使 ZT_TURNOVER_MIN=0.05 / ZT_TURNOVER_MAX=0.20 自上线起从未生效
      (20261019 实盘: 121 只进入换手率判定, 121 只全部"字段缺失"), 一字板与过热出货全被放行。
    算法: 换手率(小数) = 成交量(手) x DAILY_VOL_UNIT(股/手) / 流通股本(股)。
    字段拼写与 _float_market_cap_yi 一致(CirculatingVolume / FloatVolume / FloatVolumn),
      不猜客户端等级。
    缓存 1 小时(流通股本日内不变); 取不到返回 0, 调用方按"缺失放行"处理, 绝不误杀。"""
    try:
        _c = getattr(G, '_fshare_cache', None)
        if not isinstance(_c, dict):
            _c = {}
            G._fshare_cache = _c
        _now = time.time()
        _hit = _c.get(stock)
        if isinstance(_hit, tuple) and len(_hit) == 2 and (_now - _f(_hit[0])) < 3600.0:
            return _f(_hit[1])
        _sh = 0.0
        _C = getattr(G, 'C', None)
        if _C is not None and hasattr(_C, 'get_instrument_detail'):
            _det = _api(_C.get_instrument_detail, stock) or {}
            if isinstance(_det, dict):
                for _fld in ('CirculatingVolume', 'FloatVolume', 'FloatVolumn'):
                    _v = _f(_det.get(_fld) or 0)
                    if _v > 0:
                        _sh = _v
                        break
        _c[stock] = (_now, _sh)
        return _sh
    except Exception:
        return 0.0


'''

# ---------- 倒序应用 ----------
edits = []
edits.append((i_newfn, i_newfn - 1, new_fn.split('\n')[:-1]))      # 插入新函数(空区间)
edits.append((i_replace + 1, i_replace + 2, new_hb.split('\n')))   # 心跳(替换 except 两行)
edits.append((i_loss, i_loss, [new_loss]))
edits.append((i_basevol, i_basevol, [new_basevol]))
edits.append((i_funnel2, i_funnel2, [new_funnel2]))
edits.append((i_funnel1, i_funnel1, [new_funnel1]))
edits.append((i_init, i_init, [new_init]))
edits.append((i_turn_start, i_turn_end, new_turn.split('\n')))

edits.sort(key=lambda x: -x[0])
for s, e, blk in edits:
    lines[s:e + 1] = blk
    print('  [OK] 行 %d-%d -> %d 行' % (s + 1, e + 1, len(blk)))

t = '\n'.join(lines).replace('\n', '\r\n')
open(P, 'wb').write(t.encode('gbk'))
compile(t, P, 'exec')
print('OK V2.6.88 功能补丁, 行数 %d' % len(lines))
