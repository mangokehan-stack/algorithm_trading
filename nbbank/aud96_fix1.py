# -*- coding: utf-8 -*-
# AUD96 修复脚本1: 版本号/文件头/状态写保护/挂单强清/委托方向/费用保守值
PATH = r"E:\桌面\666666\nbbank\gf_qmt_native_multi_gbk.py"
raw = open(PATH, "rb").read()
t = raw.decode("gb18030")

edits = []
def E(old, new):
    edits.append((old, new))

# 版本号
E('STRATEGY_VERSION = "v1.2.78"',
  'STRATEGY_VERSION = "v1.2.79"   # AUD96(2026-10-22) 独立审计修复: 状态读失败中止写入/挂单强清先查券商/委托方向分字段翻译/费用异常保守值/风险日志防清空 等(见文件头)')
E('STRATEGY_BUILD = "2026-10-21"', 'STRATEGY_BUILD = "2026-10-22"')

# 文件头注记
E('# -*- coding: gbk -*-\n',
  '# -*- coding: gbk -*-\n'
  '# [v1.2.79 修改时间 2026-10-22] AUD96 全新独立审计修复(GBK 直改, 编码不变):\n'
  '#   1) save_state/save_m3 读状态文件失败时中止本次写入(不再用空字典覆盖, 防清空其他股票状态导致重复建仓)\n'
  '#   2) settle_pending_timeout 强制清理(_PENDING_TTL_FORCE)前先查券商活跃委托, 有活跃/未知单则保留在途台账, 防重复下单\n'
  '#   3) _read_order_direction 按字段分别翻译方向(OffsetFlag 48买/49卖; Direction 0/23买 1/24卖), 统一语义 0=买/1=卖/None=未知\n'
  '#   4) order_commission 异常时返回保守最低佣金而非 0, 防盈亏高估提前止盈\n'
  '#   5) in_cooldown 字段类型异常时保守视为冷却中; _manual_takeover_on 配置异常时打日志\n'
  '#   6) _notify_risk 风险日志读失败时中止写入, 防清空全部历史风险记录\n'
  '#   7) _r1_net_profit_gate 成本完全未知时发风险告警(仍拒绝卖出, 保守)\n'
  '#   8) load_state/load_m3 读失败发一次性风险告警提醒人工核对防重复建仓/超额加仓\n'
  '#   9) _rebuild_pending_from_broker 断路恢复分支改 max() 合并在途台账, 防覆盖已登记在途单\n'
  '#  10) query_position_safe 持仓代码匹配改大小写不敏感; init 对 ETF/转债/港股通品种打费率未分档提醒\n'
  '#  11) init 异常兜底重载在途台账; 双实例锁 fail-open 时发风险告警; _sync_state_to_actual 裸 return 改 return True\n'
  '#  铁律未动: 无止损/强平; 扣全费真赚才卖; 人工接管同时释放股票额度与资金额度, 原样保留。\n')

# 1. save_state 读失败中止写入
E('''            _blob, _err = _read_file_bytes(STATE_FILE)
            all_s = {}
            if _blob:''',
  '''            _blob, _err = _read_file_bytes(STATE_FILE)
            if _blob is None:
                # AUD96: 读失败(返回 None)时绝不能用空字典覆盖其他股票状态桶,
                # 否则一次 IO 抖动就会清空全部他股状态 -> 下一根 bar 被当空仓重复建底仓。
                raise IOError("state merge read failed: %s" % _err)
            all_s = {}
            if _blob:''')

# 2. save_m3 读失败中止写入
E('''            _blob, _err = _read_file_bytes(M3_STATE_FILE)
            all_m = {}
            if _blob:''',
  '''            _blob, _err = _read_file_bytes(M3_STATE_FILE)
            if _blob is None:
                # AUD96: 同 save_state, 读失败中止写入, 防止清空他股 M3/M2 当日加仓台账。
                raise IOError("m3 merge read failed: %s" % _err)
            all_m = {}
            if _blob:''')

# 3. _notify_risk 读失败防清空
E('            _prev = (b"" if not _blob else _blob)',
  '''            if _blob is None:
                # AUD96: 风险日志读失败时中止写入, 防止一次读失败清空全部历史风险记录。
                raise IOError("risk log read failed")
            _prev = _blob''')

# 4. 挂单强制清理先查券商
E('''    if _PENDING_TTL_FORCE > 0:
        _pending_clear(code,''',
  '''    if _PENDING_TTL_FORCE > 0:
        # AUD96: 强制清理前先查券商活跃委托; 有活跃/未知单则保留在途台账, 防原单仍挂时重复下单。
        _fok, _flive, _funk, _fdet = has_live_buy_order(acct, code)
        if (not _fok) or _flive > 0 or _funk > 0:
            _log_dup_guard(code, "在途单超时强清前查到活跃/未知委托(%s), 保留在途台账不重复下单" % _fdet)
            return False
        _pending_clear(code,''')

# 5. 委托方向分字段翻译(统一 0=买/1=卖/None=未知)
E('''        if not _ORDER_DIR_FIELD["field"]:
            _ORDER_DIR_FIELD.update({"field": _f, "sample": str(_v), "ts": time.time()})
        return _x
    return None''',
  '''        if not _ORDER_DIR_FIELD["field"]:
            _ORDER_DIR_FIELD.update({"field": _f, "sample": str(_v), "ts": time.time()})
        # AUD96: 不同字段约定不同, 不能都和 49 直接比较。统一翻译: 0=买 / 1=卖 / None=未知。
        if _f in ("m_nOffsetFlag", "m_strOffsetFlag"):
            return 1 if _x == 49 else (0 if _x == 48 else None)
        if _f in ("m_nDirection", "m_dDirection"):
            return 1 if _x in (1, 24, 49) else (0 if _x in (0, 23, 48) else None)
        return None
    return None''')
E('''            off = _read_order_direction(od)
            if off == 49:        # ''' ,
  '''            off = _read_order_direction(od)
            if off == 1:          # AUD96: 1=卖(统一语义), 排除卖单不堵买''')
E('''            if off == 0:
                continue          # AUD96: 明确是买单, 不计入卖侧活跃
            if off == 1:
                any_active = True
                bits.append(''',
  '''XXX''') if False else E('''            off = _read_order_direction(od)
            if off == 49:
                any_active = True
                bits.append(''',
  '''            off = _read_order_direction(od)
            if off == 0:
                continue          # AUD96: 明确是买单, 不计入卖侧活跃
            if off == 1:
                any_active = True
                bits.append(''')

# 6. order_commission 异常保守值
E('''        return max(per * _r, _m) * n
    except Exception:
        return 0.0''',
  '''        return max(per * _r, _m) * n
    except Exception as _e:
        # AUD96: 异常时返回保守最低佣金(而非 0), 防止手续费算 0 导致盈亏高估提前止盈。
        try:
            log_err("order_commission 异常(%s), 按最低佣金保守估算" % _e)
        except Exception:
            pass
        return STOCK_COMMISSION_MIN * max(1, int(n_orders or 1))''')

fails = []
res = t
for old, new in edits:
    n = res.count(old)
    if n != 1 and not (old.startswith("            off = _read_order_direction(od)") and n == 2):
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
    ver = [l for l in chk.splitlines() if l.startswith("STRATEGY_VERSION")][0]
    print("FIX1 APPLIED %d edits, bytes=%d (was %d)" % (len(edits), len(out), len(raw)))
    print("version:", ver)
