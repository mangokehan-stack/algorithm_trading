# -*- coding: utf-8 -*-
"""AUD27 补丁阶段E：init 自检 + 诊断行 + 状态字段兼容"""
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


# ==================================================== P16 init 手工仓自检日志
OLD_INIT = '''            if _mt_codes:
                log("人工接管额度释放说明 | 资金额度：已释放（人工接管标的已投入资金不再占用策略现金池，"
                    "见 _account_free_cash） | 股票额度(capital_cap)：未实现、无回收再分配通路，"
                    "单标的版本亦无第二支标的可接收；如需多标的共享额度须改为显式配置项")
'''
NEW_INIT = '''            if _mt_codes:
                # AUD27(2026-10-20)：原「股票额度未实现、无通络」说明已过时——手工仓现在
                # 完全不进 capital_cap 占用（_sync_state_to_actual 只写 manual_* 两本账），
                # 额度天然不再被吃。此处如实改写，并逐标的打印手工仓现状与卖出阈值。
                log("人工接管额度说明(AUD27) | 资金额度：已释放（_account_free_cash 跳过不载）| "
                    "股票额度(capital_cap)：手工仓不计入占用，额度不再被吃"
                    "(原 AUD83-P4「未实现」条随之作废)")
                for _ms_code in _mt_codes:
                    _ms_st = STATES.get(_ms_code) or {}
                    _ms_sh = int(_ms_st.get("manual_shares", 0) or 0)
                    _ms_cs = float(_ms_st.get("manual_cost", 0.0) or 0.0)
                    _ms_tp = float(_manual_cfg(_ms_code, "manual_takeover_tp_pct", 0.04) or 0.04)
                    log("手工仓自检 | %s | 手工持仓=%d股 成本=%.2f元 均价=%.4f | "
                        "不占策略名额与额度 | 卖出阈值=扣费后净赚>=%.0f%%%s | "
                        "亏损一律不卖（坚决不止损铁律）"
                        % (_ms_code, _ms_sh, _ms_cs, (_ms_cs / _ms_sh) if _ms_sh else 0.0,
                           _ms_tp * 100.0,
                           " + 移动止盈(激活%.0f%%/回落%.0f%%)"
                           % (float(_manual_cfg(_ms_code,
                                                "manual_takeover_trailing_activate_pct", 0.03) or 0.03) * 100.0,
                              float(_manual_cfg(_ms_code,
                                                "manual_takeover_trailing_dd_pct", 0.02) or 0.02) * 100.0)
                           if bool(_manual_cfg(_ms_code, "manual_takeover_trailing", True)) else ""))
'''
sub_once(OLD_INIT, NEW_INIT, "P16-init自检")

blob = txt.encode("gbk")
io.open(P + ".tmp_w", "wb").write(blob)
shutil.move(P + ".tmp_w", P)
print("阶段E完成，已写入 %d 字节" % len(blob))
