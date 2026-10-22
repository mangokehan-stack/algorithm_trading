# -*- coding: utf-8 -*-
"""P3 批次修补 A（大行号区）。GBK 安全编辑：行号+锚点双校验 -> 编译通过才写回。"""
import sys

p = 'zt_shrink_strategy_gbk.py'
raw = open(p, 'rb').read()
text = raw.decode('gbk', errors='strict')
lines = text.split('\r\n')
base = len(lines)
print('base lines=%d bytes=%d' % (base, len(raw)))

# (start, end, must_contain, [new lines], note)  —— 1-based, 含端点
edits = []

# ---------- 情绪：download_history_data 缺失空转 ----------
edits.append((11038, 11039,
              "except NameError:",
              ["                    except NameError:",
               "                        # P3(V2.6.83): 旧版只 break 内层循环且不置标志/不告警 —— 外层批次循环",
               "                        #   每批再撞一次 NameError, 300 只票×N 批全部空转, 日志里毫无痕迹。",
               "                        #   现在置 G.no_download(与宿主补数路径同一开关)并记录一次原因。",
               "                        G.no_download = True",
               "                        _sent_wlog('本QMT无download_history_data内置函数, 跳过历史日线预下载(本地数据应已就绪)')",
               "                        break"],
              'sent pre-download NameError'))

# ---------- 情绪：SENT_LAG_DAYS 真正生效 ----------
edits.append((10921, 10922,
              "# 滞后1日: 只用今天之前已完成的交易日(防未来函数)",
              ["        # 滞后N日(V2.6.83 P3): 旧实现硬编码\"今日之前\", 等于永远滞后1日 —— SENT_LAG_DAYS",
               "        #   写了但从不生效(改了常量也没用)。现按常量截断: lag=1 与原口径完全一致,",
               "        #   lag>1 时把最新已完成的那 (lag-1) 个交易日也排除(只用更早的已完成日)。",
               "        # 滞后1日: 只用今天之前已完成的交易日(防未来函数)",
               "        comp = [r for r in rows if r['date'] < _t]",
               "        _lag = max(1, int(SENT_LAG_DAYS or 1))",
               "        if _lag > 1 and comp:",
               "            comp = comp[:-(_lag - 1)] if len(comp) >= _lag else []"],
              'SENT_LAG_DAYS consume'))

# ---------- 情绪：后台线程启动失败文案不符(实际不同步取数) ----------
edits.append((10903, 10903,
              "_sent_wlog('后台线程启动失败",
              ["        # P3(V2.6.83): 旧文案\"退回同步取数\"与实现不符 —— 实际是 return None 由下轮重试,",
               "        #   没有任何同步取数发生; 误导排查(以为正在主线程阻塞取数)。",
               "        _sent_wlog('后台线程启动失败(本轮情绪取数跳过, 买入侧保持中性; 下轮自动重试): %s' % _e)"],
              'sent thread fail wording'))

# ---------- _sent_roll 注释口径(ddof) ----------
edits.append((10774, 10774,
              "# 滚动窗口(含idx)均值/标准差",
              ["    # 滚动窗口(含idx)均值/标准差; 样本不足返回 (None, None)。",
               "    # P3(V2.6.83)口径注明: 标准差按【总体】(除以 n, 即 pandas .std(ddof=0)) 计算 ——",
               "    #   与 pandas 默认 .std()(ddof=1, 除以 n-1) 有细微差异, 但 z-score 仅用于阈值比较、",
               "    #   且 minp/SENT_CLIP_LIMIT 已做截断, 系统性偏差可忽略; 此处不改算法, 仅把口径写清。"],
              '_sent_roll comment'))

# ---------- 死字段 param_verify_note ----------
edits.append((10550, 10550,
              "G.param_verify_note = ",
              ["                    # P3(V2.6.83): 删除死字段 G.param_verify_note —— 全文件只写不读,",
               "                    #   冻结原因已由下方 log/notify 完整输出, 保留字段只会误导(以为有人消费)。"],
              'dead field param_verify_note'))

# ---------- RUN_ROUND_GUARD_SEC 常量消费 ----------
edits.append((9086, 9086,
              "if _sec_since < 5.0:",
              ["        if _sec_since < RUN_ROUND_GUARD_SEC:   # V2.6.83(P3): 5.0 提取为具名常量(原注释引用了不存在的常量)"],
              'run_round guard const'))

# ---------- pyramid_add 死变量 fee ----------
edits.append((7534, 7534,
              "fee = fee_buy(amt, s)",
              ["    # P3(V2.6.83): 删除死变量 fee —— 本函数后续发单/扣款一律用 fee_buy(vol*px, s) 重算,",
               "    #   该变量赋值后全函数零引用(白算一次费用)。"],
              'pyramid dead fee var'))

# ---------- detect_confirm_entry / detect_ma5_break: continue -> break ----------
edits.append((6320, 6321,
              "if L - i >= CONFIRM_BREAK_MAX_DAYS:",
              ["        if L - i >= CONFIRM_BREAK_MAX_DAYS:",
               "            break                       # P3(V2.6.83): i 递减 => L-i 单调增, 超窗后再往前必然更超, 直接结束"],
              'confirm_entry break'))
edits.append((6342, 6343,
              "if L - i >= MA5_RECLAIM_MAX_DAYS:",
              ["        if L - i >= MA5_RECLAIM_MAX_DAYS:",
               "            break                       # P3(V2.6.83): 同上, 破位过久后续必然更久, 省掉无意义遍历"],
              'ma5 break'))

# ---------- _pick_latest_fin_row 单侧日期缺失容错 ----------
edits.append((6030, 6031,
              "if rd and ad and rd <= today and ad <= today:",
              ["        # P3(V2.6.83): 单侧日期缺失容错 —— 旧版要求报告期与公告日同时存在, 任一为空时整条",
               "        #   记录被丢弃(数据源只给其中一个字段), 明明有净利润却判\"取不到\"-> 亏损过滤失效。",
               "        #   现用另一侧兜底, 两侧都缺才跳过; 未来日期仍严格禁止(防未来函数)。",
               "        _rd_c = rd or ad",
               "        _ad_c = ad or rd",
               "        if _rd_c and _ad_c and _rd_c <= today and _ad_c <= today:",
               "            visible.append((_rd_c, _ad_c, r))"],
              'fin row single-side date'))

# ---------- 历史ST清单缺失补强提醒 ----------
edits.append((5676, 5676,
              "历史ST清单未配置(文件不存在)",
              ["            log('历史ST清单未配置(文件不存在), 如需启用历史ST剔除请创建: %s (实际读取路径带账号后缀, 以本行路径为准)' % st_hist_path())",
               "            # P3(V2.6.83): 清单缺失 = 历史ST过滤整体不生效, 仅写本地日志极易被忽略;",
               "            #   每次加载失败只推一次(该分支每交易日最多进一次), 补一条手机强提醒。",
               "            try:",
               "                pnl_alert('[风控][提示] 历史ST清单未配置(文件不存在), 历史ST剔除未生效。如需启用请创建: %s'",
               "                          % st_hist_path())",
               "            except Exception:",
               "                pass"],
              'st hist missing alert'))

# ---------- 死字段 vol_unit_confirmed (4 处只写不读) ----------
for _ln, _must in ((5484, "G.vol_unit_confirmed = False"),
                   (5490, "G.vol_unit_confirmed = True"),
                   (5493, "G.vol_unit_confirmed = False"),
                   (5509, "G.vol_unit_confirmed = False")):
    edits.append((_ln, _ln, _must,
                  ["                # P3(V2.6.83): 删死字段 vol_unit_confirmed(全文件只写不读, 核对结论已由日志表达)"],
                  'dead vol_unit_confirmed L%d' % _ln))

# ---------- 死字段 banner_note_date ----------
edits.append((4975, 4975, "G.banner_note_date = today",
              ["    # P3(V2.6.83): 删死字段 banner_note_date(去重已由 last_day_phase_key 完成)"],
              'dead banner_note_date assign'))

# ---------- 市值缓存缩短 ----------
edits.append((388, 388, "MARKET_CAP_CACHE_SEC = 3600",
              ["MARKET_CAP_CACHE_SEC = 300       # 市值缓存时长(秒), 降低接口调用压力; V2.6.83: 3600->300",
               "                                 #   1小时缓存会让盘中市值筛选用开盘时的旧市值(价格变动20%以内不刷新),",
               "                                 #   5分钟在\"接口压力\"与\"市值时效\"之间取平衡"],
              'mcap cache sec'))

# ================= 校验锚点 =================
fail = 0
for a, b, must, new, note in edits:
    seg = '\r\n'.join(lines[a - 1:b])
    if must not in seg:
        print('ANCHOR FAIL [%s] L%d-%d must=%r' % (note, a, b, must))
        print('   actual: %r' % seg[:200])
        fail += 1
if fail:
    print('ABORT: %d anchor failures, file untouched' % fail)
    sys.exit(2)

# ================= 自底向上应用 =================
for a, b, must, new, note in sorted(edits, key=lambda x: -x[0]):
    lines[a - 1:b] = new

out = '\r\n'.join(lines)
if out.count('\r\n') != len(lines) - 1:
    print('ABORT: CRLF mismatch')
    sys.exit(3)
compile(out, p, 'exec')

open(p, 'wb').write(out.encode('gbk', errors='strict'))
print('OK: %d edits, lines %d -> %d (delta %+d)' % (len(edits), base, len(lines), len(lines) - base))
