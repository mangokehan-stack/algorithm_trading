# -*- coding: utf-8 -*-
"""P3 批次修补 B（小行号区）：内容锚点定位 + 唯一性断言 + 编译熔断。"""
import sys

p = 'zt_shrink_strategy_gbk.py'
raw = open(p, 'rb').read()
text = raw.decode('gbk', errors='strict')
lines = text.split('\r\n')
base = len(lines)
print('base lines=%d bytes=%d' % (base, len(raw)))


def lineno(sub, start=1, end=None):
    end = end or len(lines)
    hits = [i + 1 for i, ln in enumerate(lines) if sub in ln and start <= i + 1 <= end]
    if len(hits) != 1:
        print('ANCHOR FAIL %r -> %s' % (sub, hits))
        sys.exit(2)
    return hits[0]


edits = []   # (a, b, [new lines], note)


def E(a, b, new, note):
    edits.append((a, b, new, note))


# ================= 1) FEE_RATE_EST 死常量清理 + RUN_ROUND_GUARD_SEC 定义 =================
a = lineno('FEE_RATE_EST = 0.0015')
for k in range(1, 4):
    if not lines[a - 1 + k].lstrip().startswith('#'):
        print('FEE tail line not comment:', repr(lines[a - 1 + k]))
        sys.exit(2)
E(a, a + 3,
  ["# V2.6.83(P3清理): 原 FEE_RATE_EST(费用+滑点粗估预留比例 0.15%)已全文件零引用, 删除常量定义。",
   "#   费用口径统一走 fee_buy/fee_sell 的真实费率(见 FEE_PROFILE), 滑点走 _slippage_for(lp), 不留粗估口径。",
   "RUN_ROUND_GUARD_SEC = 5.0      # V2.6.83(P3): handlebar/timer_poll 双入口竞态跳过窗口(秒)。",
   "                               #   原为函数内硬编码 5.0, 而注释引用了从未定义的 RUN_ROUND_GUARD_SEC;",
   "                               #   现提取为具名常量, 调窗口只改这一处。"],
  'FEE_RATE_EST cleanup + guard const')

# ================= 2) _prod_of: LOF(16x/18x) 品种识别 =================
a = lineno("if _n6[:2] in ('51', '15') or _n6[:1] == '5':")
E(a, a,
  ["    # P3(V2.6.83): 补 16x/18x 场内基金(LOF/封基) —— 旧版只认 5x/51/15, 16/18 开头的 LOF",
   "    #   会被当成股票(多算印花税、佣金最低5元), 解套价/净利口径双双偏高。",
   "    if (len(_n6) == 6 and _n6[:2] in ('51', '15', '16', '18')) or _n6[:1] == '5':"],
  '_prod_of LOF')

# ================= 3) 死状态字段清理 =================
E(lineno("G.banner_note_date = ''"), lineno("G.banner_note_date = ''"),
  ["# V2.6.83(P3): 删除死字段 G.banner_note_date —— 去重实际由 G.last_day_phase_key 完成, 本字段只写不读"],
  'dead banner_note_date')
E(lineno("G.hourly_buy_note = 0"), lineno("G.hourly_buy_note = 0"),
  ["# V2.6.83(P3): 删除死字段 G.hourly_buy_note —— 本小时发单数由 hourly_buy_last_cnt(buy_cnt 快照)差值算, 该字段零引用"],
  'dead hourly_buy_note')
E(lineno("G.hourly_sell_note = 0"), lineno("G.hourly_sell_note = 0"),
  ["# V2.6.83(P3): 删除死字段 G.hourly_sell_note(同上, 零引用)"],
  'dead hourly_sell_note')
E(lineno("G.notify_ip_ok = set()"), lineno("G.notify_ip_ok = set()"),
  ["G.notify_lock = threading.Lock()  # V2.6.83(P3): 推送队列读写锁(替代只写不读的 notify_ip_ok 占位);",
   "                                  #   情绪后台线程与成交回报线程都会入队, 无锁会越过50条上限/丢消息"],
  'notify lock init')

# ================= 4) trigger_log 静默吞掉 -> 留痕 =================
a = lineno("msg += ' | 参数: ' + _p")
E(a + 1, a + 3,
  ["        log(msg)",
   "    except Exception as _e:",
   "        # P3(V2.6.83): 原为静默 pass —— 触发日志是排查\"买卖为何被拒\"的唯一结构化线索,",
   "        #   格式化失败必须留痕; 这里用 print 而非 log(), 避免 log 内部再抛造成递归。",
   "        print('[触发日志] 格式化失败(不影响交易): %r' % (_e,))"],
  'trigger_log silent pass')

# ================= 5) save_state: 备份失败当日重试 =================
a = lineno('if STATE_BAK_KEEP > 0 and G.today and G.state_bak_date != G.today:')
b = None
for i in range(a, min(a + 20, len(lines))):
    if 'traceback.print_exc()' in lines[i]:
        b = i + 1
        break
if not b:
    print('save_state backup block not found')
    sys.exit(2)
E(a, b,
  ["            if STATE_BAK_KEEP > 0 and G.today and G.state_bak_date != G.today:",
   "                # P3(V2.6.83): 备份成功后才置当日标记 —— 旧版一进入就置位, 一旦 copyfile 失败",
   "                #   (磁盘满/杀软占用/权限), 当日之后所有 save_state 都跳过备份, 等于当天没有备份。",
   "                try:",
   "                    base = os.path.dirname(p)",
   "                    if os.path.exists(p):",
   "                        bak = os.path.join(base, os.path.basename(p) + '.bak.%s.json' % G.today)",
   "                        if not os.path.exists(bak):",
   "                            shutil.copyfile(p, bak)",
   "                    olds = sorted(f for f in os.listdir(base)",
   "                                  if f.startswith(os.path.basename(p) + '.bak.')",
   "                                  and f.endswith('.json'))",
   "                    while len(olds) > STATE_BAK_KEEP:",
   "                        os.remove(os.path.join(base, olds.pop(0)))",
   "                    G.state_bak_date = G.today      # 成功才标记; 失败留空 -> 当日下次写盘重试",
   "                except Exception:",
   "                    G.state_bak_date = ''           # 重置标记, 允许当日重试",
   "                    log('[状态][告警] 当日状态文件备份失败(不影响主文件写入, 下次写盘自动重试)')",
   "                    traceback.print_exc()"],
  'save_state backup retry')

# ================= 6) load_state: 旧 GBK 状态文件兼容 =================
a = lineno("with open(cand, 'r', encoding='utf-8') as f:")
E(a, a + 1,
  ["            # P3(V2.6.83): 旧版状态文件可能是 GBK 编码(V2.6.6x 之前的旧脚本/手工编辑写入),",
   "            #   纯 UTF-8 读取会 UnicodeDecodeError -> 被当成\"主文件损坏\"回滚备份甚至冻结交易;",
   "            #   现 UTF-8 失败自动按 GBK 重读一次(只在真正解码失败时触发, 不影响正常路径)。",
   "            try:",
   "                with open(cand, 'r', encoding='utf-8') as f:",
   "                    disk = json.load(f)",
   "            except UnicodeDecodeError:",
   "                with open(cand, 'r', encoding='gbk') as f:",
   "                    disk = json.load(f)",
   "                log('[安全] 状态文件为GBK编码(旧版写入), 已按GBK兼容读取: %s' % cand)"],
  'load_state gbk fallback')

# ================= 7) notify_enqueue / notify_drain 加锁 =================
a = lineno('def notify_enqueue(text):')
b = lineno('# ==================== 通用工具 ====================')
E(a, b - 1,
  ["def notify_enqueue(text):",
   "    \"\"\"P1-11: 把推送排入队列, 由 timer_poll 在【锁外】统一发送 ——",
   "    推送(含无超时DNS解析)绝不在持锁的交易线程里执行, 防止DNS无响应时",
   "    冻结成交回报/废单回调。队列有上限, 防异常刷屏时无限膨胀。",
   "    P3(V2.6.83): 入队整体持 G.notify_lock —— 旧版\"检查长度+append\"是裸操作, 情绪后台线程",
   "    与成交回报线程并发入队时会越过 50 条上限(两边同时看到49), 或 pop(0)/append 交错丢消息。",
   "    注意: log() 放在锁外调用, 避免与日志锁形成嵌套\"\"\"",
   "    _dropped = 0",
   "    try:",
   "        with G.notify_lock:",
   "            if len(G.notify_queue) < 50:",
   "                G.notify_queue.append(str(text))",
   "            else:",
   "                G.notify_queue.pop(0)",
   "                G.notify_queue.append(str(text))",
   "                _dropped = int(getattr(G, 'notify_dropped', 0) or 0) + 1",
   "                G.notify_dropped = _dropped",
   "        if _dropped:",
   "            log('[通知][告警] 推送队列已满，累计丢弃%d条旧消息' % _dropped)",
   "    except Exception:",
   "        pass",
   "",
   "def notify_drain(max_items=3, max_seconds=5.0):",
   "    \"\"\"锁外限量、限时发送，避免Webhook拖慢交易轮询。",
   "    P3(V2.6.83): 只对 pop(0) 持 G.notify_lock, 真正的发送(可能慢/DNS卡住)仍在锁外;",
   "    旧版无锁 pop 与另一线程 append 并发时会漏发或 IndexError。\"\"\"",
   "    started, sent = time.time(), 0",
   "    while sent < max_items and time.time() - started < max_seconds:",
   "        with G.notify_lock:",
   "            if not G.notify_queue:",
   "                break",
   "            t = G.notify_queue.pop(0)",
   "        sent += 1",
   "        try:",
   "            notify(t)",
   "        except Exception:",
   "            log('通知队列发送失败(不影响交易)')",
   "",
   ""],
  'notify lock')

# ================= 8) 早盘量能闸门过 sent_param =================
a = lineno('if _exp_min < BUY_MIN_ELAPSED_MIN:')
E(a, a,
  ["                # P3(V2.6.83): 过 sent_param —— 情绪恐慌档把 BUY_MIN_ELAPSED_MIN 覆写为 45 分钟时,",
   "                #   本处仍按全局常量 30 分钟判定\"早盘bar少不算缺量\", 同一份数据两套口径。",
   "                if _exp_min < sent_param('BUY_MIN_ELAPSED_MIN', BUY_MIN_ELAPSED_MIN):"],
  'exp_min sent_param')

# ================= 9) abs_cap_left: 无效价格不得当成\"不限制\" =================
a = lineno('def abs_cap_left(price):')
b = lineno('def data_gate():')
E(a, b - 1,
  ["def abs_cap_left(price):",
   "    \"\"\"本策略绝对资金封顶(STRATEGY_CASH_CAP)下, 按 price 还能再买的股数上限(2026-10-09第五轮审计新增)。",
   "    口径与 calc_size 的 n5 一致: 已投入成本占用额度 —— V2.6.58b起已移交人工的套牢仓不占用(释放资金额度),",
   "    同时也不加回任何名义额度(不放大/不重复计算)。",
   "    P3(V2.6.83): 价格无效(<=0)时不再返回 None —— None 的语义是\"本策略不设上限\"(调用方直接放行),",
   "    旧版把\"价格算不出来\"也归到这一类, 等于行情异常时静默取消资金封顶; 现与异常路径一致返回 0.0(不允许买),",
   "    只有 STRATEGY_CASH_CAP<=0(真的没有上限)才返回 None。\"\"\"",
   "    try:",
   "        if STRATEGY_CASH_CAP <= 0:",
   "            return None",
   "        if _f(price) <= 0:",
   "            log('[安全][资金封顶] 价格无效(%.4f), 无法折算可买股数, 保守返回0股上限(不允许买)' % _f(price))",
   "            return 0.0",
   "        # V2.6.75: 统一调用 used_capital()(含在途委托), 与 calc_size 的 n5 同一口径 ——",
   "        # 旧版两处各算一遍且算法不同(n5漏在途), 是\"突破 STRATEGY_CASH_CAP\"的根因。",
   "        inv = used_capital()",
   "        return max(0.0, STRATEGY_CASH_CAP - inv) / _f(price)",
   "    except Exception as _e:   # V2.6.79 P2-2: fail-safe, 异常时保守返回0(不允许买)",
   "        log('[安全][资金封顶] abs_cap_left计算异常, 保守返回0股上限(不允许买): %s' % repr(_e)[:150])",
   "        return 0.0",
   ""],
  'abs_cap_left invalid price')

# ================= 10) strategy_status_signature 加锁 =================
a = lineno('def strategy_status_signature(phase=None):')
b = lineno('def strategy_pnl_value():')
E(a, b - 1,
  ["def strategy_status_signature(phase=None):",
   "    \"\"\"生成策略状态签名；仅业务状态变化才触发状态日志刷新。",
   "    触发字段: 交易日、市场时段、日初始化阶段、账号/状态文件可用性、候选代码及排序、",
   "    自有持仓代码/股数/退出与分批状态、买卖累计笔数、熔断状态、累计已实现盈亏(按分取整)、财务数据源可用性。",
   "    时间戳不进入签名，因此时间流逝、轮询执行不会单独触发刷新。",
   "    【2026-10-02 用户要求: 存活打点改静默】浮动盈亏/总资产(随行情每轮变动)不再进入签名 ——",
   "    旧版把它们按分取整也算作触发字段, 盘中几乎每轮签名都变, 心跳实际退化成\"定时打点\";",
   "    现在价格类指标仍照常写进日志正文, 只是不再单独触发输出(需按盈亏触发见 HB_PNL_TRIGGER_PCT)。",
   "    P3(V2.6.83): 整个构造过程持 G.state_lock —— state['hold'] 会被成交回报线程同时增删,",
   "    旧版无锁遍历可能抛 \"dictionary changed size during iteration\" 导致本轮巡检中断;",
   "    RLock 可重入, 已在持锁路径(轮询)内调用时不会死锁。\"\"\"",
   "    with G.state_lock:",
   "        state = G.state or {}",
   "        hold_sig = []",
   "        for code, h in sorted((state.get('hold') or {}).items()):",
   "            if not is_own_position(h):",
   "                continue",
   "            hold_sig.append((code, int(h.get('buy_vol') or 0), bool(h.get('exited')),",
   "                             int(h.get('plan_idx') or 0), bool(h.get('plan_done')),",
   "                             int(h.get('pend_vol') or 0)))",
   "        cand_sig = tuple(c.get('stock') for c in (G.candidates or []))",
   "        meta = state.get('pnlmeta') or {}",
   "        fuse_sig = (bool(meta.get('fuse_on')), str(meta.get('fuse_until') or ''),",
   "                    bool(meta.get('manual_resume')))",
   "        _d_nb, _d_ns = _ledger_today_counts()   # V2.6.50b: 账本当日笔数(与全天汇总一致)",
   "        return (G.today or '', phase if phase is not None else market_phase(), int(G.dl_phase or 0),",
   "                G.acct_ok, bool(G.state_broken), cand_sig, tuple(hold_sig),",
   "                _d_nb, _d_ns, fuse_sig,",
   "                int(round(_f((state.get('realized') or {}).get('pnl')) * 100)),",
   "                bool(getattr(G, 'loss_data_ok', True)))",
   ""],
  'status_signature lock')

# ================= 11) atr_of 日期口径 =================
a = lineno('if G.today and str(d)[:8] == G.today:')
E(a, a,
  ["        # P3(V2.6.83): 日期口径统一用 _bardate_loose —— 索引若是 date/datetime, str(d)[:8] 得到",
   "        #   '2026-10-' 永远不等于 '20261019', 当日未走完的K线剔不掉, ATR 混入半截当日数据。",
   "        if G.today and _bardate_loose(d) == G.today:"],
  'atr_of date caliber')

# ================= 12) 退潮 bars 当日剔除口径 =================
a = lineno('bars = {_k: _v for _k, _v in bars.items() if str(_k)[:8] != G.today}')
E(a, a,
  ["            # P3(V2.6.83): 同上, 索引为 date/datetime 时 str()[:8] 无法与 '20261019' 比较,",
   "            #   当日K线剔不掉 -> 退潮判断混入未完成K线(与本块 P2-12 的意图相反)。",
   "            bars = {_k: _v for _k, _v in bars.items() if _bardate_loose(_k) != G.today}"],
  'market tide date caliber')

# ================= 13) exit_price_needed 按品种计费 =================
a = lineno('def exit_price_needed(h):')
b = lineno('def trap_metrics(s, h, lp):')
E(a, b - 1,
  ["def exit_price_needed(h, code=''):",
   "    \"\"\"解套价: 以该价全部卖出、扣掉全部摩擦费用后净利刚好转正的最低价格(人工解套的目标价)。",
   "    P3(V2.6.83): 新增 code 参数 —— 旧版固定按股票费率(万0.841/5元起/印花税万5)推算, 持仓若是",
   "    ETF(万0.5/0.1元起/无印花税)或可转债(卖出十万分之5), 解套价会算高或算低: 算高则人工挂单",
   "    永远卖不掉, 算低则按该价卖出扣费后仍亏(违背\"扣费后真正赚钱才卖\"的铁律)。\"\"\"",
   "    vol = pos_vol(h)",
   "    cost = pos_cost(h)",
   "    if vol <= 0 or cost <= 0:",
   "        return 0.0",
   "    _pit = fee_profile(code) if code else FEE_PROFILE['stock']",
   "    _rate = _f(_pit.get('rate'))",
   "    _min = _f(_pit.get('min'))",
   "    _stamp = _f(_pit.get('stamp'))",
   "    _tr = _f(_pit.get('transfer'))",
   "    if code and _prod_of(code) == 'cbond':",
   "        _rate = FEE_CBOND_SELL_RATE      # 可转债买卖不同价: 解套用卖出档费率",
   "    denom = vol * (1.0 - _stamp - _tr)",
   "    p1 = ((cost + _min) / denom) if denom > 0 else 0.0",
   "    p2 = (cost / (vol * (1.0 - _rate - _stamp - _tr))) if vol > 0 else 0.0",
   "    px = max(p1, p2)",
   "    if px <= 0:",
   "        return 0.0",
   "    # Q8修复(2026-10-19 第九轮零预设审计): 解套价迭代上限 30->300 次 —— 旧版30次(每次+0.2%)在极端费用",
   "    #   情形下算出的价可能远高于涨停价, 被当委托价发单后必废单并耗尽重发次数(giveup), 卖出永久停摆",
   "    for _i in range(300):",
   "        px = math.ceil(px * 100) / 100.0        # 只向上取整到分, 保证确实能覆盖费用",
   "        if net_pnl_if_sell(h, px, code) > 0:",
   "            return _round2(px)",
   "        px = px * 1.002",
   "    return _round2(px)",
   ""],
  'exit_price_needed code')

# ================= 14) 四个调用点传 code =================
cnt = 0
for i, ln in enumerate(lines):
    if 'exit_price_needed(h)' in ln and not ln.lstrip().startswith('def '):
        lines[i] = ln.replace('exit_price_needed(h)', 'exit_price_needed(h, s)')
        cnt += 1
if cnt != 6:
    print('ABORT: exit_price_needed call sites = %d (expect 6)' % cnt)
    sys.exit(2)
print('exit_price_needed call sites patched: %d' % cnt)

# ================= 应用（倒序） =================
for a, b, new, note in sorted(edits, key=lambda x: -x[0]):
    lines[a - 1:b] = new

out = '\r\n'.join(lines)
if out.count('\r\n') != len(lines) - 1:
    print('ABORT: CRLF mismatch')
    sys.exit(3)
compile(out, p, 'exec')

open(p, 'wb').write(out.encode('gbk', errors='strict'))
print('OK: %d edits(+4 call sites), lines %d -> %d (delta %+d)'
      % (len(edits), base, len(lines), len(lines) - base))
