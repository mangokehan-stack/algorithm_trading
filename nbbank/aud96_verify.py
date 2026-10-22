import py_compile, sys
try:
    py_compile.compile(r"E:\桌面\666666\nbbank\gf_qmt_native_multi_gbk.py",
                       doraise=True)
    print("COMPILE OK")
    # 额外自检: GBK 解码全文 + 关键修复点在位
    t = open(r"E:\桌面\666666\nbbank\gf_qmt_native_multi_gbk.py", "rb").read().decode("gb18030")
    checks = {
        "版本v1.2.79": 'STRATEGY_VERSION = "v1.2.79"' in t,
        "文件头注记": "[v1.2.79 修改时间 2026-10-22]" in t,
        "save_state读失败保护": "state merge read failed" in t,
        "save_m3读失败保护": "m3 merge read failed" in t,
        "风险日志防清空": "risk log read failed" in t,
        "挂单强清先查券商": "在途单超时强清前查到活跃/未知委托" in t,
        "方向分字段翻译": 'return 1 if _x == 49 else (0 if _x == 48 else None)' in t,
        "has_live_buy_order语义": "AUD96: 1=卖(统一语义)" in t,
        "卖单状态语义": "AUD96: 明确是买单" in t,
        "佣金异常保守值": "order_commission 异常" in t,
        "冷却保守": "保守视为冷却中" in t,
        "人工接管告警": "人工接管配置读取异常" in t,
        "R1成本未知告警": "r1_cost_unknown" in t,
        "load_state告警": "state_read_fail" in t,
        "load_m3告警": "m3_read_fail" in t,
        "rebuild合并": "max(_PENDING_BUYS.get(code, 0), _beff_b)" in t,
        "持仓大小写不敏感": "pid.upper() != code.upper()" in t,
        "init费率提醒": "费率提醒" in t,
        "init兜底台账": "init 异常兜底: 在途台账已重载" in t,
        "锁fail-open告警": "lock_fail_open" in t,
        "sync显式return": "return True   # AUD96" in t,
    }
    bad = [k for k, v in checks.items() if not v]
    print("CHECKS:", "ALL PASS (%d)" % len(checks) if not bad else "MISSING: %s" % bad)
    # 铁律确认: 无止损卖出调用
    import re
    sl = re.findall(r"check_hard_stop\(", t)
    print("check_hard_stop调用次数(应只在告警路径):", len(sl))
except Exception as e:
    print("COMPILE FAIL:", e)
