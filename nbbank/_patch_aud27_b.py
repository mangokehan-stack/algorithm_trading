# -*- coding: utf-8 -*-
"""AUD27 补丁阶段B：_sync_state_to_actual 手工仓分离 + 新增 _r1_net_profit_gate"""
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


# ============================================================ P6 新增铁律闸门
GATE = '''def _r1_net_profit_gate(code, actual_vol, broker_avg, price, state, reason,
                        sub_vol=None):
    """AUD27-P2(2026-10-20 用户拍板)：卖出侧统一铁律闸门——与账本解耦，按券商实际持仓判。

    用户原话：「任何针对宁波银行的卖出，都要检查亏损不卖和扣除税费之后赚钱的铁律」。
    所以本闸门不依赖 state["position_shares"]（手工仓已移出策略账本，该值恒为 0），
    一律以 **券商实际持仓 + 实际成本** 为准：
        净到手 = 保守成交价 x 拟卖股数 - 佣金(万0.841,5元起) - 印花(万5) - 过户(万1)
        净到手 <= 对应成本  ->  拒绝卖出
    对应成本 = 拟卖股数 x 成本价，成本价取 max(券商均价, 策略账本均价, 手工账本均价)：
    两本账并存时按更保守的一本判，宁可少卖不可亏卖。
    保守成交价 = 现价 x (1 - 卖出滑点)，与 sell_all 实际挂单价一致
    （避免「按现价算赚、按挂单价成交倒亏」）。跌停夹价由调用方在算完后再校一次。

    参数 sub_vol：仅当策略自己也有仓、只卖手工仓那一份时传入手工仓股数；None=全部可卖。
    返回 (ok, detail)：ok=True 才允许继续卖出。detail 含 ref_px/cost/net/pnl/pct/why。
    铁律：本函数只判「能不能卖」，绝不主动卖出，也不含任何止损语义。
    """
    try:
        _avail = int(actual_vol or 0)
        if _avail <= 0:
            return False, {"why": "券商实际持仓为0，无股可卖", "ref_px": 0.0, "cost": 0.0,
                           "net": 0.0, "pnl": 0.0, "pct": 0.0, "vol": 0, "avg": 0.0, "fee": 0.0}
        _vol = _avail if sub_vol is None else min(int(sub_vol), _avail)
        if _vol <= 0:
            return False, {"why": "拟卖股数为0", "ref_px": 0.0, "cost": 0.0,
                           "net": 0.0, "pnl": 0.0, "pct": 0.0, "vol": 0, "avg": 0.0, "fee": 0.0}
        _st = state or {}
        _avg_b = float(broker_avg or 0.0)
        _avg_k = (float(_st.get("total_cost", 0.0) or 0.0) / int(_st.get("position_shares", 0) or 0)
                  if int(_st.get("position_shares", 0) or 0) > 0 else 0.0)
        _avg_m = (float(_st.get("manual_cost", 0.0) or 0.0) / int(_st.get("manual_shares", 0) or 0)
                  if int(_st.get("manual_shares", 0) or 0) > 0 else 0.0)
        _avg = max(_avg_b, _avg_k, _avg_m)
        if _avg <= 0 and price > 0:
            _avg = price          # 极端兜底：连成本都查不到时按现价当成本（必判不赚，等于拒卖）
        _cost = _avg * _vol
        _ref_px = round(price * (1.0 - LIMIT_SLIP_PCT_SELL), 2) if PRICE_TYPE == 11 else price
        if _ref_px <= 0:
            _ref_px = price
        _mv = _ref_px * _vol
        _comm = max(_mv * STOCK_COMMISSION_RATE, STOCK_COMMISSION_MIN)
        _stamp = _mv * STOCK_STAMP_TAX_RATE
        _trf = _mv * STOCK_TRANSFER_FEE_RATE
        _net = _mv - _comm - _stamp - _trf
        _pnl = _net - _cost
        _pct = (_pnl / _cost * 100.0) if _cost > 0 else -100.0
        _detail = {"ref_px": _ref_px, "cost": _cost, "net": _net, "pnl": _pnl,
                   "pct": _pct, "vol": _vol, "avg": _avg, "fee": _comm + _stamp + _trf,
                   "reason": reason}
        if _net <= _cost:
            _detail["why"] = ("不赚钱不卖(净到手%.2f <= 成本%.2f，扣费后%.2f%%)"
                              % (_net, _cost, _pct))
            return False, _detail
        _detail["why"] = "扣费后净赚%.2f元(%.2f%%)" % (_pnl, _pct)
        return True, _detail
    except Exception as _e:
        return False, {"why": "铁律闸门异常，保守拒卖: %s" % _e, "ref_px": 0.0, "cost": 0.0,
                       "net": 0.0, "pnl": 0.0, "pct": 0.0, "vol": 0, "avg": 0.0, "fee": 0.0}


def _sync_state_to_actual('''
sub_once("def _sync_state_to_actual(", GATE, "P6-铁律闸门")

# ------------------------------------------------ P7 actual_vol>0：不再写策略账本
OLD_SYNC = '''    if broker_avg > 0:
        state["total_cost"] = actual_vol * broker_avg
    elif price > 0:
        state["total_cost"] = actual_vol * price
'''
NEW_SYNC = '''    # ============ AUD27-P1(2026-10-20 用户拍板)：手工仓不占策略持仓名额与投资额度 ============
    # 原实现（AUD27 前）在这里把券商实际持仓整个写进策略账本：
    #     state["total_cost"] = actual_vol * broker_avg
    #     state["deployed"]   = state["total_cost"]      <- 也算进 20 万预算
    #     state["tier"]       = 0
    #     state["last_add_price"] = broker_avg           <- 还成了金字塔加仓基准
    # 结果：用户手工买的 1000 股（2026-10-20 13:00:05 实盘，总成本 34830）被策略
    # 「接管」——既占掉 3.48 万额度、又让机器准备按 M2 给它加仓，与用户意图相反。
    # 现改为「两本账」：
    #   · 策略账本 position_shares / total_cost / deployed —— 只记策略自己下的单，此处不动；
    #   · 手工账本 manual_shares / manual_cost —— 记券商可见但归人工管的那部分。
    # 手工仓因此不计入 capital_cap 占用、不进 M2 金字塔基准、不参与策略止盈判定；
    # 卖出侧改由 _r1_net_profit_gate 以「券商实际持仓 + 实际成本」为准（铁律一条不少）。
    _mkt_cost = actual_vol * (broker_avg if broker_avg > 0 else (price if price > 0 else 0.0))
    state["manual_shares"] = actual_vol
    state["manual_cost"] = _mkt_cost
    _mpx = (broker_avg if broker_avg > 0 else price)
    if _mpx > 0:
        _prev_peak = float(state.get("manual_peak_cost", 0.0) or 0.0)
        if _mpx > _prev_peak:
            state["manual_peak_cost"] = _mpx
    _mavg = (_mkt_cost / actual_vol) if actual_vol > 0 else 0.0
    log("[%s] 【手工仓已分离】券商持仓%d股 均价%.4f 成本%.2f 元 —— 已记入手工账本"
        "(manual_shares/manual_cost)，**不占用策略持仓名额与 20 万投资额度**，"
        "机器不会对此加仓；卖出仍受「亏损不卖 + 扣完税费后赚钱才卖」铁律约束%s"
        % (_cn(code), actual_vol, _mavg, _mkt_cost,
           "（manual_takeover=True：满足阈值时由策略代卖）"
           if _manual_takeover_on(code) else "（manual_takeover=False：仅观察，不代卖）"))
'''
sub_once(OLD_SYNC, NEW_SYNC, "P7-actual>0改为两本账")

# ------------------------------------------------ P8 tier 不再被外部持仓推进
OLD_TIER = '''    if _prev_pos > actual_vol > 0:
        state["tier"] = 0
    else:
        state["tier"] = 0 if state["position_shares"] == 0 else state["tier"]
'''
NEW_TIER = '''    # AUD27-P1：tier（金字塔档位）只跟策略自己的仓走——手工仓不占名额，也就不能推进档位。
    # 原实现「减仓则重置为 0」在手工仓场景下含义已变：策略账本空仓时 tier 恒为 -1（未开仓），
    # 不能因为「券商有仓」就置 0，否则下一次策略真正开首仓时会直接从第 2 档起步、少买 5 万。
    if state["position_shares"] > 0:
        state["tier"] = state.get("tier", -1)
    else:
        state["tier"] = -1
'''
sub_once(OLD_TIER, NEW_TIER, "P8-tier不随手工仓推进")

# ------------------------------------------------ P9 deployed 不再被外部持仓占用
OLD_DEP = '''    state["deployed"] = state["total_cost"]
    state["last_add_price"] = broker_avg if broker_avg > 0 else price
'''
NEW_DEP = '''    # AUD27-P1：deployed（已用额度）与 last_add_price（加仓基准）同样不得被手工仓污染。
    #   deployed      -> 只反映策略账本 total_cost（手工仓 0 元占用）
    #   last_add_price-> 策略有仓时按策略均价，否则保持原值（空仓时无意义）
    # 原实现两者都直接取券商均价，手工仓一进来就等于「策略已投入 34830、加仓基准 34.83」。
    state["deployed"] = float(state.get("total_cost", 0.0) or 0.0)
    if state["position_shares"] > 0:
        state["last_add_price"] = (float(state.get("total_cost", 0.0) or 0.0)
                                   / int(state["position_shares"] or 1))
    elif float(state.get("last_add_price", 0.0) or 0.0) > 0 and state["position_shares"] <= 0:
        state["last_add_price"] = 0.0
'''
sub_once(OLD_DEP, NEW_DEP, "P9-deployed不占额度")

# ------------------------------------------------ P10 日志措辞同步
OLD_LOG = '''    log("[%s] 检测到外部交易，成本基准已重算(总成本=%.0f)；注意：加档基准 last_add_price=%.4f "
        "为券商加权均价/市价的混合成本，金字塔加仓时点会据此重算"
        % (code, state["total_cost"], state["last_add_price"]))
'''
NEW_LOG = '''    # AUD27-P1：原日志「成本基准已重算...金字塔加仓时点会据此重算」讲的是「策略接管外部持仓」，
    # 与现行两本账语义相反，改为如实描述：手工仓已单独记账，策略账本未变。
    log("[%s] 检测到外部持仓变动(券商%d股 均价%.4f) | 手工账本 = %d股/%.2f元 | "
        "策略账本 = %d股/%.2f元(已部署%.2f) | 手工仓不占策略名额与额度，机器不对其加仓"
        % (_cn(code), actual_vol, (broker_avg if broker_avg > 0 else price),
           int(state.get("manual_shares", 0) or 0), float(state.get("manual_cost", 0.0) or 0.0),
           int(state.get("position_shares", 0) or 0), float(state.get("total_cost", 0.0) or 0.0),
           float(state.get("deployed", 0.0) or 0.0)))
'''
sub_once(OLD_LOG, NEW_LOG, "P10-日志措辞同步")

# ------------------------------------------------ P11 manual_takeover_on 助手
HELPER = '''# AUD27(2026-10-20)：手工仓开关查询。返回 True 表示该标的的手工仓可由策略按铁律代卖。
def _manual_takeover_on(code):
    try:
        for _s in SYMBOLS:
            if _s.get("code") == code:
                return bool(_s.get("manual_takeover"))
    except Exception:
        pass
    return False


def _manual_cfg(code, key, default=None):
    """AUD27：读 SYMBOLS 里该标的的手工仓配置项（缺省回落到全局 PARAMS 同名项）。"""
    try:
        for _s in SYMBOLS:
            if _s.get("code") == code:
                if key in _s:
                    return _s.get(key)
                break
    except Exception:
        pass
    return PARAMS.get(key, default)


def _r1_net_profit_gate('''
sub_once("def _r1_net_profit_gate(", HELPER, "P11-手工仓配置助手")

blob = txt.encode("gbk")
io.open(P + ".tmp_w", "wb").write(blob)
shutil.move(P + ".tmp_w", P)
print("阶段B完成，已写入 %d 字节" % len(blob))
