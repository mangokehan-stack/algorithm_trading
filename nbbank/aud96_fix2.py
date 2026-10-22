# -*- coding: utf-8 -*-
# AUD96 修复脚本2: 冷却保守/人工接管告警/R1成本未知告警/load_state,m3告警/rebuild合并/持仓大小写/init兜底/锁告警/sync return
PATH = r"E:\桌面\666666\nbbank\gf_qmt_native_multi_gbk.py"
raw = open(PATH, "rb").read()
t = raw.decode("gb18030")

edits = []
def E(old, new):
    edits.append((old, new))

# 7. in_cooldown 保守
E('''    if not isinstance(until, str):
        return False''',
  '''    if not isinstance(until, str):
        # AUD96: 字段被外部改坏成非字符串时保守视为"仍在冷却期", 宁可少开仓不放行。
        try:
            log_err("冷却字段类型异常(stop_cooldown_until=%r), 保守视为冷却中" % (until,))
        except Exception:
            pass
        return True''')

# 8. 人工接管配置异常留日志
E('''                return bool(_s.get("manual_takeover"))
    except Exception:
        pass''',
  '''                return bool(_s.get("manual_takeover"))
    except Exception as _e:
        # AUD96: SYMBOLS 配置异常不能静默, 否则人工接管形同虚设。
        try:
            log_err("人工接管配置读取异常(%s), 保守按未接管处理, 请检查 SYMBOLS 配置" % _e)
        except Exception:
            pass''')

# 10. R1 成本未知告警
E('''        if _avg <= 0 and price > 0:
            _avg = price''',
  '''        if _avg <= 0 and price > 0:
            # AUD96: 成本完全未知时按现价判亏(仍拒绝卖出, 保守), 但必须发风险告警提醒人工核对,
            # 否则该股卖出通道会被静默永久堵死。
            try:
                _notify_risk("r1_cost_unknown",
                             "%s 卖出被拒: 成本未知(券商均价/内部/手动均取不到), 请人工核对持仓成本" % code)
            except Exception:
                pass
            _avg = price''')

# 11. load_state 读失败/解析失败一次性告警
E('''    if _blob is None:
        _LS_STATUS["state"] = "read-failed(%s)" % _err
        return new_state()''',
  '''    if _blob is None:
        _LS_STATUS["state"] = "read-failed(%s)" % _err
        # AUD96: 读失败被当空仓处理, 若实盘有持仓会重复建仓, 必须发一次性风险告警。
        if not _LS_STATUS.get("state_rf_notified"):
            _LS_STATUS["state_rf_notified"] = True
            try:
                _notify_risk("state_read_fail",
                             "状态文件读取失败(%s): 该股被按空仓处理, 若实盘有持仓请人工核对, 防重复建仓" % _err)
            except Exception:
                pass
        return new_state()''')
E('''        _LS_STATUS["state"] = "parse-failed(%s)" % _e
        all_s = {}''',
  '''        _LS_STATUS["state"] = "parse-failed(%s)" % _e
        all_s = {}
        if not _LS_STATUS.get("state_pf_notified"):   # AUD96: 解析失败同读失败, 一次性告警
            _LS_STATUS["state_pf_notified"] = True
            try:
                _notify_risk("state_parse_fail",
                             "状态文件解析失败(%s): 该股被按空仓处理, 若实盘有持仓请人工核对, 防重复建仓" % _e)
            except Exception:
                pass''')

# 12. load_m3 读失败一次性告警
E('''        _LS_STATUS["m3"] = "read-failed(%s)" % _err
        return {"date": "", "triggered": [], "used": 0.0, "m2_used": 0.0}''',
  '''        _LS_STATUS["m3"] = "read-failed(%s)" % _err
        # AUD96: M3 台账读失败会使当日加仓额度归零, 发一次性告警提醒人工核对。
        if not _LS_STATUS.get("m3_rf_notified"):
            _LS_STATUS["m3_rf_notified"] = True
            try:
                _notify_risk("m3_read_fail",
                             "M3台账读取失败(%s): 当日加仓额度被重置, 请人工核对防止超额加仓" % _err)
            except Exception:
                pass
        return {"date": "", "triggered": [], "used": 0.0, "m2_used": 0.0}''')

# 13. rebuild 恢复分支 max 合并
E('''            _beff_b = int(_blive_b) + int(_bunk_b)
            if _beff_b > 0:
                _PENDING_BUYS[code] = _beff_b''',
  '''            _beff_b = int(_blive_b) + int(_bunk_b)
            if _beff_b > 0:
                # AUD96: 断路恢复时不覆盖内存中已登记的在途数, 取两者较大值防漏记导致重复下单。
                _PENDING_BUYS[code] = max(_PENDING_BUYS.get(code, 0), _beff_b)''')

# 14. query_position_safe 大小写不敏感
E('''            if pid != code:
                continue
            vol = int(getattr(pos, "m_nVolume", 0) or 0)''',
  '''            if pid.upper() != code.upper():   # AUD96: 后缀大小写差异不再误判空仓
                continue
            vol = int(getattr(pos, "m_nVolume", 0) or 0)''')

# 15. init 费率未分档品种提醒
E('% (STRATEGY_VERSION, STRATEGY_BUILD))',
  '''% (STRATEGY_VERSION, STRATEGY_BUILD))
        try:
            for _sym79 in enabled_symbols():
                _c79 = str(_sym79.get("code", ""))
                if _c79[:2] in ("51", "52", "56", "58", "15", "16", "12", "11", "10") or "HK" in _c79.upper():
                    log("费率提醒 | %s 属 ETF/可转债/港股通类品种, 当前费用参数仅按 A 股股票实现"
                        "(佣金万0.841、5元/单起, 印花税/过户费), 交易该类品种前请先人工校准费率" % _c79)
        except Exception:
            pass''')

# 16. init 异常兜底重载在途台账
E('''        log_err("init''',
  '''        try:
            _pending_load()   # AUD96: init 中途异常时兜底重载在途台账, 防在途丢失后重复下单
            log("init 异常兜底: 在途台账已重载, 请人工核对委托/持仓")
        except Exception:
            pass
        log_err("init''')

# 17. 双实例锁 fail-open 告警
E('''            _INSTANCE_LOCK_ACQUIRED = True
            return True
    return False''',
  '''            _INSTANCE_LOCK_ACQUIRED = True
            try:
                _notify_risk("lock_fail_open",
                             "实例锁异常 fail-open: 可能存在双实例, 请确认只运行一个模型窗口")
            except Exception:
                pass
            return True
    return False''')

# 18. _sync_state_to_actual 裸 return 改 return True
E('''            _SETTLE_BREAKER_DATE.pop(code, None)
        return''',
  '''            _SETTLE_BREAKER_DATE.pop(code, None)
        return True   # AUD96: 显式返回, 与 docstring 契约一致(空仓分支已处理)''')

fails = []
res = t
for old, new in edits:
    n = res.count(old)
    if n != 1:
        fails.append((old[:70].replace("\n", "\\n"), n))
    else:
        res = res.replace(old, new)

if fails:
    print("ABORT, unmatched edits:")
    for f in fails:
        print(" ", f)
else:
    out = res.encode("gb18030")
    open(PATH, "wb").write(out)
    chk = open(PATH, "rb").read().decode("gb18030")
    print("FIX2 APPLIED %d edits, bytes=%d (was %d)" % (len(edits), len(out), len(raw)))
    ver = [l for l in chk.splitlines() if l.startswith("STRATEGY_VERSION")][0]
    print("version:", ver[:60])
