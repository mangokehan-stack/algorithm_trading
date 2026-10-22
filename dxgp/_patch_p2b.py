# -*- coding: utf-8 -*-
"""P2 第二批补丁: P2-1 / P2-4 / P2-5 / P2-13
GBK 安全编辑法: encoding='gbk', newline='' + split/join('\r\n'), 全部锚点带命中计数断言
"""
P = 'zt_shrink_strategy_gbk.py'
raw = open(P, encoding='gbk', newline='').read()
lines = raw.split('\r\n')
BASE = len(lines)
assert BASE == 11114, 'base line count %d' % BASE
delta = 0

def find_seq(seq, start=0):
    """返回 seq(行列表)在 lines 中首次出现的起始下标, 未命中返回 None"""
    n = len(seq)
    for i in range(start, len(lines) - n + 1):
        if lines[i:i + n] == seq:
            return i
    return None

def replace_seq(old, new, expect=1):
    global delta
    cnt = 0
    i = 0
    while True:
        j = find_seq(old, i)
        if j is None:
            break
        lines[j:j + len(old)] = new
        delta += len(new) - len(old)
        cnt += 1
        i = j + len(new)
    assert cnt == expect, 'replace_seq hits=%d expect=%d :: %r' % (cnt, expect, old[0][:60])
    print('ok: replaced %d x %r' % (cnt, old[0][:60]))

# ================= P2-1: used_capital 异常分支 fail-open -> fail-safe =================
replace_seq(
    ['    except Exception:',
     '        return 0.0',
     '    return inv'],
    ['    except Exception as _e:',
     '        # P2-1修复(2026-10-19): 原异常分支 return 0.0 是 fail-open——占用资金算成0,',
     '        # abs_cap_left/calc_size 的 n5 会认为"额度全是空的"而放大可买量, 极端情况',
     '        # 下突破 STRATEGY_CASH_CAP 总投资上限; 改为返回超大哨兵值, 两个下游全部',
     '        # fail-safe(算成已用满, 不开新仓), 并强告警',
     "        log('[安全][资金占用] used_capital 计算异常, 按已用满处理(拒开新仓): %s' % repr(_e)[:150])",
     '        return 1e18',
     '    return inv'])
print('P2-1 done')

# ================= P2-13a: _keep_partial_hold 助手(插在 _safe_rollback_placeholder 之后) =================
i_srp = find_seq(['    G.state[\'hold\'].pop(s, None)',
                  '    return True',
                  '',
                  'def is_own_position(h):'])
assert i_srp is not None, 'P2-13a anchor not found'
helper = [
    '',
    'def _keep_partial_hold(s):',
    '    """P2-13修复(2026-10-19): A3保留路径——买单管理放弃但已有部分成交时, 保留真实',
    '    持仓记录并清理挂单残留状态, 置 buy_abandoned 使 handle_unfilled_buy 后续调用直接',
    '    早返回; 该记录交由主循环按正常持仓管理(pos_total>0 时走卖出信号/金字塔), 或次日',
    '    由空持仓结算逻辑清理(estimate_close 补记账)。不做当日买入数扣减——买入确实发生',
    '    了(部分成交), 名额不退; 也不加回名义额度(防同一笔钱算两次, 沿用既定设计)。"""',
    '    try:',
    '        _h = (G.state.get(\'hold\') or {}).get(s)',
    '    except Exception:',
    '        return',
    '    if not isinstance(_h, dict):',
    '        return',
    '    _fv = int(_f(_h.get(\'fill_vol\', 0)) or 0)',
    '    _h[\'buy_abandoned\'] = True',
    '    _h[\'pend_vol\'] = 0',
    '    _h[\'order_ts\'] = 0',
    '    _h[\'cancel_sent\'] = False',
    '    _h[\'order_retries\'] = 0',
    '    _h[\'buy_submit_unknown\'] = False',
    '    if _fv > 0:',
    '        _h[\'buy_vol\'] = _fv',
    '    save_state()',
    '    log(disp(s), \'A3保留: 买单管理放弃但已有部分成交(%d股), 保留持仓记录转正常持仓管理, \'',
    '                 \'挂单状态已清理, 当日买入名额不退回\' % _fv)',
]
lines[i_srp + 3:i_srp + 3] = helper
delta += len(helper)
print('P2-13a done: helper inserted')

# ================= P2-13b: handle_unfilled_buy 顶部 buy_abandoned 早返回 =================
i_hub = None
for i, ln in enumerate(lines):
    if ln.startswith('def handle_unfilled_buy(s, h, ords_snap=None):'):
        i_hub = i
        break
assert i_hub is not None, 'P2-13b def not found'
i_now = None
for i in range(i_hub, i_hub + 8):
    if lines[i] == '    now = time.time()':
        i_now = i
        break
assert i_now is not None, 'P2-13b now anchor not found'
early = [
    '    # P2-13修复(2026-10-19): 已有部分成交但放弃挂单管理的占位记录(A3保留路径),',
    '    # 直接早返回, 不再走超时撤单/重试/删除流程; 该记录由主循环按正常持仓管理',
    '    # (pos_total>0 时走卖出信号/金字塔), 或次日按空持仓结算清理',
    '    if h.get(\'buy_abandoned\'):',
    '        return',
]
lines[i_now + 1:i_now + 1] = early
delta += len(early)
print('P2-13b done: early return inserted')

# ================= P2-13c: 两处 del G.state['hold'][s] 改走 A3 守卫 =================
old_del = ['        del G.state[\'hold\'][s]',
           '        b = daily_buy_state()',
           '        b[\'n\'] = max(0, b[\'n\'] - 1)',
           '        if s in (b.get(\'codes\') or []):',
           '            b[\'codes\'].remove(s)',
           '        _disk_adjust_daily_buy(-1, s)   # P2-21: 同步修正磁盘计数(防合并逻辑把退额改回)',
           '        save_state()',
           '        return']
new_del = ['        if _safe_rollback_placeholder(s):',
           '            # 确认无成交也无残留挂单量: 执行原删除+退回当日买入名额逻辑',
           '            b = daily_buy_state()',
           '            b[\'n\'] = max(0, b[\'n\'] - 1)',
           '            if s in (b.get(\'codes\') or []):',
           '                b[\'codes\'].remove(s)',
           '            _disk_adjust_daily_buy(-1, s)   # P2-21: 同步修正磁盘计数(防合并逻辑把退额改回)',
           '            save_state()',
           '        else:',
           '            # P2-13修复(2026-10-19): 原为直接 del G.state[\'hold\'][s]——该笔买入',
           '            # 委托已有部分成交(fill_vol>0)时会把真实持仓记录删掉, 仓位从管理中消失',
           '            # (无法止盈/金字塔/卖出); _safe_rollback_placeholder 已拒绝删除并日志,',
           '            # 这里保留记录转正常持仓管理(详见 _keep_partial_hold)',
           '            _keep_partial_hold(s)',
           '        return']
replace_seq(old_del, new_del, expect=2)
print('P2-13c done')

# ================= P2-4: handle_unfilled_sell 顶部对称消费 sell_submit_unknown =================
i_hus = None
for i, ln in enumerate(lines):
    if ln.startswith('def handle_unfilled_sell(s, h, pos_avail, lp, tick=None, ords_snap=None):'):
        i_hus = i
        break
assert i_hus is not None, 'P2-4 def not found'
i_now2 = None
for i in range(i_hus, i_hus + 20):
    if lines[i] == '    now = time.time()':
        i_now2 = i
        break
assert i_now2 is not None, 'P2-4 now anchor not found'
consume = [
    '    # P2-4修复(2026-10-19): 对称消费 sell_submit_unknown(镜像买入侧 buy_submit_unknown',
    '    # 处理)。原代码 place_sell_order 抛异常时置位该标记(委托状态未知, 可能已到柜台),',
    '    # 但全文件无人读取它, 成为死标记: 该笔卖出永远停留在刚提交状态, 既不撤单也不',
    '    # 重试, 挂单可能残留到收盘。现在入口处立即重查委托: 查询失败->刷新 sell_ts 下轮',
    '    # 再查; 委托在途->刷新 sell_ts 继续等待(由超时逻辑撤单); 委托已终态->落入下方',
    '    # 常规流程(撤单重试/放弃), 消除买卖两侧不对称',
    '    if h.get(\'sell_submit_unknown\'):',
    '        h[\'sell_submit_unknown\'] = False',
    '        _o0 = sell_order_obj(s, ords_snap)',
    '        if _o0 == \'_ERR\':',
    '            h[\'sell_ts\'] = now',
    '            return \'wait\'',
    '        if _o0 is not None:',
    '            h[\'sell_err_n\'] = 0           # 查询恢复: 清零连续查询失败计数',
    '        if _o0 is not None and int(getattr(_o0, \'m_nOrderStatus\', -1)) in ACTIVE_ORDER_STATUS:',
    '            h[\'sell_ts\'] = now            # 委托确实在途: 继续等待, 超时后走撤单',
    '            return \'wait\'',
]
lines[i_now2 + 1:i_now2 + 1] = consume
delta += len(consume)
print('P2-4 done')

# ================= P2-5: FIXED_BUY_VOL 回退分支双帽防御 =================
replace_seq(
    ['    elif FIXED_BUY_VOL > 0:',
     '        vol = int(FIXED_BUY_VOL / _lot) * _lot     # 每次固定手数'],
    ['    elif FIXED_BUY_VOL > 0:',
     '        # P2-5修复(2026-10-19): 固定量回退分支补双帽防御。该分支正常不可达(plan 总',
     '        # 提供 want_vol), 但一旦被走到(计划缺失/异常), 原逻辑会绕过 abs_cap_left 与',
     '        # MAX_POS_VALUE_ABS 全部仓位帽按固定量直接下单, 存在超限风险; 这里用限价',
     '        # 折算后的双帽收紧, 超帽即拒单(与下方资金不足拒单同一风格)',
     '        vol = int(FIXED_BUY_VOL / _lot) * _lot     # 每次固定手数',
     '        _px_g = _round2(lp * (1.0 + _slippage_for(lp)))',
     '        if _px_g <= 0:',
     '            _px_g = _round2(lp)',
     '        _caps_g = []',
     '        if MAX_POS_VALUE_ABS and MAX_POS_VALUE_ABS > 0:',
     '            _caps_g.append(MAX_POS_VALUE_ABS / _px_g)',
     '        _cl_g = abs_cap_left(_px_g)',
     '        if _cl_g is not None:',
     '            _caps_g.append(_cl_g)',
     '        if _caps_g:',
     '            _cv_g = int(min(_caps_g) / _lot) * _lot',
     '            if _cv_g < _lot:',
     '                log(disp(s), \'固定量回退: 仓位帽折算不足一手(帽=%.0f股 价格=%.2f), 拒单\'',
     '                    % (min(_caps_g), _px_g))',
     '                return None',
     '            if vol > _cv_g:',
     '                log(disp(s), \'固定量回退: %d股超仓位帽, 收紧为%d股\' % (vol, _cv_g))',
     '                vol = _cv_g'])
print('P2-5 done')

# ================= 写回 =================
assert len(lines) == BASE + delta, 'delta mismatch: %d vs %d' % (len(lines), BASE + delta)
open(P, 'w', encoding='gbk', newline='').write('\r\n'.join(lines))
print('written. base=%d delta=+%d new=%d' % (BASE, delta, len(lines)))
print('ALL P2-BATCH-B OK')
