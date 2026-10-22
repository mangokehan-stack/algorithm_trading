# -*- coding: utf-8 -*-
"""AUD27 补丁阶段D：新增 manual_sell 手工仓卖出路径 + handlebar 接入"""
import io, shutil, sys

P = "gf_qmt_native_multi_gbk.py"
txt = io.open(P, "rb").read().decode("gbk")


def sub_once(old, new, tag):
    global txt
    n = txt.count(old)
    if n != 1:
        print("[ABORT] %s 匹配数=%d（要求1）" % (tag, n))
        sys.exit(1)
    txt = txt.replace(old, new, 1)
    print("[OK] %s" % tag)


# ==================================================== P14 新增 manual_sell 函数
MANUAL_SELL = '''# ---------------------------------------------------------------------------
# 9.9 AUD27(2026-10-20 用户拍板)：手工仓卖出路径
#   用户原话：「手工买入的宁波银行股票，不占用策略持仓名额和投资金额。但是任何针对
#   宁波银行的卖出，都要检查亏损不卖和扣除税费之后赚钱的铁律，这个不要忘记了。」
#   本路径只做「卖不卖」的判断，买入侧一个字不碰：
#     · 不受策略冷却/首仓窗口/大盘过滤/F2/情绪门影响（那些是买入门的，与卖出无关）；
#     · 不写 tier / first_batch_* / deployed，策略账本原样不动；
#     · 铁律三重保障：先在 manual_sell 内判阈值 -> sell_all 内再走 _r1_net_profit_gate
#       统一闸门 -> sell_all 的 R1 拦截是最后一道，任何一层判「不赚」都不会有委托发出。
#   触发条件（二者取"或"，且都必须净赚 >= manual_takeover_tp_pct）：
#     ① 固定阈值：按保守成交价扣完三费后浮盈 >= manual_takeover_tp_pct（默认 4%）；
#     ② 移动止盈（manual_takeover_trailing=True）：曾达激活线(3%)后，从观察到的最高
#        成本价回落 >= 2% 且仍净赚，即触发（锁住已到手的利润）。
#   两本账并存时（策略自己也有仓）：本路径不接手，交策略止盈链接管 —— 避免「手工仓
#   一触发就把整个账户一键全平」。
# ---------------------------------------------------------------------------
def manual_sell(C, code, acct, price, state, up=0.0, dn=0.0):
    """手工仓卖出（AUD27）。返回 True=本根 bar 已发出卖单（调用方无需再处理）。"""
    if not _manual_takeover_on(code):
        return False
    _mvol = int(state.get("manual_shares", 0) or 0)
    if _mvol <= 0 or price <= 0:
        return False
    # 两本账并存：策略自己有仓时本路径让位，避免一键全平账户
    if int(state.get("position_shares", 0) or 0) > 0:
        return False
    # 手工仓卖单在途冻结：防同一份仓位连续挂卖单
    if time.time() < float(state.get("manual_sell_pending_until", 0.0) or 0.0):
        if _diag_due(code):
            log("[%s] 手工仓卖单在途(未确认落账)，本根bar不再重复挂卖单" % _cn(code))
        return False
    # 跌停：禁止卖出（挂着也是废单；与策略侧同口径）
    if dn and dn > 0 and price <= dn:
        if _diag_due(code):
            log("[%s] 手工仓触及跌停价%.2f，禁止卖出，等待打开" % (_cn(code), dn))
        return False
    _avg = 0.0
    try:
        _q_ok, _q_vol, _q_avg, _q_cu = query_position_safe(C, acct, code)
        if _q_ok and _q_vol > 0:
            _mvol = _q_vol
            _avg = float(_q_avg or 0.0)
    except Exception as _dq:
        log("[%s] 手工仓持仓查询异常(%s)，本根bar不卖（拿不准就不动手）" % (_cn(code), _dq))
        return False
    if _mvol <= 0:
        return False
    _tp = float(_manual_cfg(code, "manual_takeover_tp_pct", 0.04) or 0.04)
    _tr_on = bool(_manual_cfg(code, "manual_takeover_trailing", True))
    _tr_act = float(_manual_cfg(code, "manual_takeover_trailing_activate_pct", 0.03) or 0.03)
    _tr_dd = float(_manual_cfg(code, "manual_takeover_trailing_dd_pct", 0.02) or 0.02)
    # 记录观察到的最高成本价（用于移动止盈；只上不下）
    _peak = float(state.get("manual_peak_cost", 0.0) or 0.0)
    if _avg > _peak:
        state["manual_peak_cost"] = _peak = _avg
    # 铁律闸门（探针口径：dry-run，只算不卖）——任何触发条件都必须先过这一关
    _ok, _d = _r1_net_profit_gate(code, _mvol, _avg, price, state, "手工仓阈值判定")
    if not _ok:
        if _diag_due(code):
            log("[%s] 手工仓观察 | 持仓%d股 成本%.4f 现价%.2f 保守成交价%.2f | %s | "
                "未达卖出条件(需扣费后净赚>=%.0f%%，现%.2f%%)，继续持有（坚决不亏损卖出）"
                % (_cn(code), _mvol, _avg, price, float(_d.get("ref_px", 0.0) or 0.0),
                   _d.get("why", ""), _tp * 100.0, float(_d.get("pct", 0.0) or 0.0)))
        return False
    _pct = float(_d.get("pct", 0.0) or 0.0) / 100.0
    _ref = float(_d.get("ref_px", 0.0) or 0.0)
    _why = ""
    if _pct >= _tp:
        _why = "手工仓固定止盈(扣费后净赚%.2f%%>=%.0f%%)" % (_pct * 100.0, _tp * 100.0)
    elif _tr_on and _pct >= _tr_act and _peak > 0 and _avg > 0:
        _dd = (_peak - _avg) / _peak
        if _dd >= _tr_dd:
            _why = ("手工仓移动止盈(成本最高%.4f->当前%.4f回落%.2f%%>=%.0f%%，扣费后仍净赚%.2f%%)"
                    % (_peak, _avg, _dd * 100.0, _tr_dd * 100.0, _pct * 100.0))
    if not _why:
        if _diag_due(code):
            log("[%s] 手工仓观察 | 持仓%d股 成本%.4f 现价%.2f 保守成交价%.2f | %s | "
                "继续持有(距%.0f%%止盈线还差%.2f%%)"
                % (_cn(code), _mvol, _avg, price, _ref, _d.get("why", ""),
                   _tp * 100.0, max(0.0, (_tp - _pct) * 100.0)))
        return False
    # ---- 走到这里：阈值已过 + 铁律复核已过，可以卖 ----
    log("[%s] 手工仓触发卖出：%s | 持仓%d股 成本%.4f 现价%.2f | 拟卖全部%d股"
        % (_cn(code), _why, _mvol, _avg, price, _mvol))
    if sell_all(C, code, acct, price, _why, state):
        state["manual_shares"] = 0
        state["manual_cost"] = 0.0
        state["manual_peak_cost"] = 0.0
        state["manual_sell_pending_until"] = time.time() + _SELL_PENDING_TTL
        _notify_risk("manual_sell", "%s 手工仓已按铁律卖出 %d股 @%.2f（%s）"
                     % (code, _mvol, price, _why))
        save_state(code, state)
        return True
    return False


def manual_hold_watch(code, state, price):
    """手工仓 30 分钟观察日志（AUD27-P4）。纯日志，不参与任何买卖判断。"""
    try:
        _mvol = int(state.get("manual_shares", 0) or 0)
        if _mvol <= 0 or price <= 0:
            return
        _avg = (float(state.get("manual_cost", 0.0) or 0.0) / _mvol) if _mvol else 0.0
        _tp = float(_manual_cfg(code, "manual_takeover_tp_pct", 0.04) or 0.04)
        _ref = round(price * (1.0 - LIMIT_SLIP_PCT_SELL), 2) if PRICE_TYPE == 11 else price
        _mv = _ref * _mvol
        _fee = (max(_mv * STOCK_COMMISSION_RATE, STOCK_COMMISSION_MIN)
                + _mv * STOCK_STAMP_TAX_RATE + _mv * STOCK_TRANSFER_FEE_RATE)
        _net = _mv - _fee
        _cost = _avg * _mvol
        _pnl = _net - _cost
        _pct = (_pnl / _cost * 100.0) if _cost > 0 else 0.0
        # 达到阈值所需的价格（反解：net(px) = cost*(1+tp)）
        _need_px = 0.0
        if _mvol > 0:
            _k = (1.0 - 0.0)
            _target_net = _cost * (1.0 + _tp)
            _px = _target_net / _mvol / (1.0 - STOCK_STAMP_TAX_RATE - STOCK_TRANSFER_FEE_RATE
                                         - STOCK_COMMISSION_RATE)
            _need_px = _px / (1.0 - LIMIT_SLIP_PCT_SELL) if PRICE_TYPE == 11 else _px
        log("[%s] 【手工仓观察】持仓%d股 成本%.4f 现价%.2f 保守成交价%.2f | 扣费后净浮盈"
            "%.2f元(%.2f%%) | 距%.0f%%止盈线需现价>=%.2f | %s | 手工仓不占策略名额与额度，"
            "只受「亏损不卖+扣费后赚钱才卖」铁律约束"
            % (_cn(code), _mvol, _avg, price, _ref, _pnl, _pct, _tp * 100.0, _need_px,
               "策略会代卖" if _manual_takeover_on(code) else "仅观察、不代卖"))
    except Exception as _e:
        try:
            log("[%s] 手工仓观察日志异常(已忽略): %s" % (code, _e))
        except Exception:
            pass


def handlebar(C):'''
sub_once("def handlebar(C):", MANUAL_SELL, "P14-manual_sell函数")

# ==================================================== P15 handlebar 接入
OLD_HB = '''            # AUD76(2026-10-19)：人工接管标的不做自动买卖决策，仅保留诊断/盈亏汇总日志（纯日志零行为变更）
            if code in manual_takeover_codes():
                if _hdiag_due(code):
                    try:
                        _hdiag_log(C, code, params, state)
                    except Exception:
                        pass
                if _pnl_display_due(code):
                    try:
                        _pnl_display_log(C, code, state)
                    except Exception:
                        pass
                STATES[code] = state
                continue
'''
NEW_HB = '''            # AUD76(2026-10-19)：人工接管标的不做自动买入决策。
            # AUD27(2026-10-20 用户拍板)：**但卖出仍要执行铁律检查** —— 用户明确
            # 「任何针对宁波银行的卖出，都要检查亏损不卖和扣除税费之后赚钱的铁律」。
            # 原实现直接 continue，等于手工仓无人管卖出（止盈也不会触发）。
            # 现改为：先跑 manual_sell（内含三重铁律闸门），再出日志，然后 continue。
            # 买入侧仍然一行都不碰：首仓/M2/M3/续批全部跳过。
            if code in manual_takeover_codes():
                try:
                    if _session_now()[0]:
                        _ms_t = get_tick_safe(C, code)
                        _ms_px = float((_ms_t or {}).get("lastPrice")
                                       or (_ms_t or {}).get("last") or 0.0)
                        if _ms_px > 0:
                            _ms_acct = resolve_account(C, code)
                            _ms_lc = float((_ms_t or {}).get("lastClose") or 0.0)
                            _ms_up, _ms_dn = get_limit_prices_safe(C, code, _ms_lc)
                            if _ms_acct and not _is_replay_bar(C):
                                if manual_sell(C, code, _ms_acct, _ms_px, state,
                                               up=_ms_up, dn=_ms_dn):
                                    STATES[code] = state
                                    continue
                            manual_hold_watch(code, state, _ms_px)
                except Exception as _mse:
                    log("[%s] 手工仓卖出路径异常(已跳过，不影响策略其他标的): %s"
                        % (code, _mse))
                if _hdiag_due(code):
                    try:
                        _hdiag_log(C, code, params, state)
                    except Exception:
                        pass
                if _pnl_display_due(code):
                    try:
                        _pnl_display_log(C, code, state)
                    except Exception:
                        pass
                STATES[code] = state
                continue
'''
sub_once(OLD_HB, NEW_HB, "P15-handlebar接入")

blob = txt.encode("gbk")
io.open(P + ".tmp_w", "wb").write(blob)
shutil.move(P + ".tmp_w", P)
print("阶段D完成，已写入 %d 字节" % len(blob))
