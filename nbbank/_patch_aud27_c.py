# -*- coding: utf-8 -*-
"""AUD27 补丁阶段C：券商清仓时同步清手工账本 + sell_all 改走统一铁律闸门"""
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


# ============================================================ P12 清仓分支清手工账本
OLD_CLR = '''        _keep_cd = state.get("stop_cooldown_until", "")
        _keep_fpd = state.get("firstpos_date", "")
        state.clear()
        state.update(new_state())
        if _keep_cd:
            state["stop_cooldown_until"] = _keep_cd
        if _keep_fpd:
            state["firstpos_date"] = _keep_fpd
'''
NEW_CLR = '''        _keep_cd = state.get("stop_cooldown_until", "")
        _keep_fpd = state.get("firstpos_date", "")
        # AUD27-P1：手工仓被清掉时，手工账本一并归零（否则 manual_shares 会残留，
        # 让后续 _r1_net_profit_gate 按早已不存在的成本判盈亏）。
        _m_sh = int(state.get("manual_shares", 0) or 0)
        _m_cost = float(state.get("manual_cost", 0.0) or 0.0)
        state.clear()
        state.update(new_state())
        if _keep_cd:
            state["stop_cooldown_until"] = _keep_cd
        if _keep_fpd:
            state["firstpos_date"] = _keep_fpd
        if _m_sh > 0:
            log("[%s] 【手工仓已清空】券商%d股已不在持仓(成本%.2f元)，手工账本归零"
                "（策略账本本就为空，不影响任何买卖判定）" % (_cn(code), _m_sh, _m_cost))
'''
sub_once(OLD_CLR, NEW_CLR, "P12-清仓清手工账本")

# ============================================================ P13 sell_all 改走统一闸门
OLD_R1 = '''    if state is not None:
        ok_v, pos_vol, can_use, why = verify_position_before_order(C, acct, code, state, "卖出", price)
        if not ok_v:
            log("【持仓校验】%s 卖出委托中止(%s)" % (_cn(code), why))
            _emit_trade("卖出-" + reason, code, "SELL", 0, price, {}, "BLOCK", "持仓校验中止：%s" % why)
            return False
        # R1 兜底(2026-09-29 审计修复)：任何卖出路径在持仓校验通过后，再次复核盈亏。
        # verify_position_before_order 只校验股数/可卖量，不判盈亏；此处为亏损不卖红线的
        # 最后一道闸门，防止上层调用方漏判 pnl_pct 直接调用 sell_all。
        _pos_s = state.get("position_shares", 0)
        _cost_s = state.get("total_cost", 0)
        if _pos_s > 0 and _cost_s > 0:
            # AUD33(2026-10-08 零预设独立审计)：与止盈净到手口径统一——卖出费用
            # (印花税0.05%+佣金万0.841最低5元)从市值扣除后再判盈亏，杜绝「毛盈亏≈0
            # 卖出后实际净亏手续费」的临界场景（铁律「不赚钱不卖」字面收紧）。
            # AUD34(2026-10-08 第二轮零预设审计)：补扣过户费(mv×0.00001，与止盈
            # should_take_profit 同费率口径)；拦截条件收紧为净到手<=成本一律拒绝——
            # 确保卖出的股票都是赚钱的（扣完所有费用后仍盈利才允许卖出）。
            # AUD36(2026-10-08 第四轮零预设独立审计)：铁律边界收紧——原按「现价」判净到手，
            # 而实际限价卖出挂单价=现价×(1-卖出滑点0.003)，移动止盈在「刚转盈」临界区
            # (浮盈0~0.3%)时可能「按现价算赚、按挂单价成交倒亏」，违反「不赚钱不卖」铁律。
            # 现改为按最保守成交价(卖出挂单价)计算净到手，只有按最差成交价仍盈利才允许卖出。
            _ref_px = round(price * (1 - LIMIT_SLIP_PCT_SELL), 2) if PRICE_TYPE == 11 else price
            if _ref_px <= 0:
                _ref_px = price
            _mv_s = _ref_px * _pos_s
            _sell_comm_s = max(_mv_s * STOCK_COMMISSION_RATE, STOCK_COMMISSION_MIN)
            _sell_stamp_s = _mv_s * STOCK_STAMP_TAX_RATE
            _sell_transfer_s = _mv_s * STOCK_TRANSFER_FEE_RATE
            _net_mv_s = _mv_s - _sell_comm_s - _sell_stamp_s - _sell_transfer_s
            _pnl_pct_s = (_net_mv_s - _cost_s) / _cost_s
            if _pnl_pct_s <= 0:
                log("【R1拦截-不赚钱不卖】%s 持仓%d股@成本%.0f 保守成交价%.2f(现价%.2f) 净到手%.2f%%(扣费后，须>0才卖)，拒绝卖出(%s)"
                    % (_cn(code), _pos_s, _cost_s, _ref_px, price, _pnl_pct_s * 100, reason))
                _emit_trade("卖出-" + reason, code, "SELL", _pos_s, price, {"持仓": _pos_s, "成本": _cost_s, "现价": price, "保守成交价": _ref_px, "浮盈%": round(_pnl_pct_s*100,2)}, "BLOCK", "R1拦截：不赚钱不卖红线（净到手口径，按保守成交价），拒绝卖出")
                return False
    else:
'''
NEW_R1 = '''    if state is not None:
        ok_v, pos_vol, can_use, _r1_why = verify_position_before_order(C, acct, code, state, "卖出", price)
        if not ok_v:
            log("【持仓校验】%s 卖出委托中止(%s)" % (_cn(code), _r1_why))
            _emit_trade("卖出-" + reason, code, "SELL", 0, price, {}, "BLOCK",
                        "持仓校验中止：%s" % _r1_why)
            return False
        # AUD27-P2：verify_position_before_order 的第4个返回值是「原因文本」不是均价，
        #   成本价须单独查一次券商持仓（_td_query 有 3s 缓存，同根 bar 内几乎零开销）。
        _r1_avg = 0.0
        try:
            _q_ok, _q_vol, _q_avg, _q_cu = query_position_safe(C, acct, code)
            if _q_ok:
                pos_vol = _q_vol if _q_vol >= 0 else pos_vol
                _r1_avg = float(_q_avg or 0.0)
        except Exception as _r1qe:
            log("【R1成本查询异常】%s %s —— 按已缓存成本继续判盈亏" % (_cn(code), _r1qe))
        # R1 兜底：任何卖出路径在持仓校验通过后，再次复核盈亏。
        # verify_position_before_order 只校验股数/可卖量，不判盈亏；此处为「亏损不卖」红线
        # 的最后一道闸门，防止上层调用方漏判 pnl_pct 直接调用 sell_all。
        # AUD27-P2(2026-10-20 用户拍板)：原实现只查 state["position_shares"]>0，
        #   而手工仓已移出策略账本（该值恒为 0），R1 会整段跳过 —— 那等于给「亏损卖出」
        #   开后门。现改为调用统一闸门 _r1_net_profit_gate：一律以**券商实际持仓+实际成本**
        #   为准判「扣完佣金/印花/过户后是否真赚钱」，与账本彻底解耦。
        #   口径不放松：仍按最保守成交价（挂单价）算净到手，净到手<=成本一律拒卖。
        _gate_ok, _gd = _r1_net_profit_gate(code, pos_vol, _r1_avg, price, state, reason)
        if not _gate_ok:
            log("【R1拦截-不赚钱不卖】%s 券商持仓%d股@成本%.4f 保守成交价%.2f(现价%.2f) "
                "%s，拒绝卖出(%s)"
                % (_cn(code), int(_gd.get("vol", 0) or 0), float(_gd.get("avg", 0.0) or 0.0),
                   float(_gd.get("ref_px", 0.0) or 0.0), price, _gd.get("why", ""), reason))
            _emit_trade("卖出-" + reason, code, "SELL", int(_gd.get("vol", 0) or 0), price,
                        {"券商持仓": pos_vol, "成本价": round(float(_gd.get("avg", 0.0) or 0.0), 4),
                         "保守成交价": _gd.get("ref_px", 0.0), "净到手": round(float(_gd.get("net", 0.0) or 0.0), 2),
                         "扣费后盈亏%": round(float(_gd.get("pct", 0.0) or 0.0), 2)},
                        "BLOCK", "R1拦截：不赚钱不卖红线（券商实际持仓口径，按保守成交价扣完三费），拒绝卖出")
            return False
    else:
'''
sub_once(OLD_R1, NEW_R1, "P13-sell_all走统一闸门")

blob = txt.encode("gbk")
io.open(P + ".tmp_w", "wb").write(blob)
shutil.move(P + ".tmp_w", P)
print("阶段C完成，已写入 %d 字节" % len(blob))
