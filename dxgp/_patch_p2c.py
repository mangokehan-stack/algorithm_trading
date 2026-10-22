# -*- coding: utf-8 -*-
"""P2 第三批(末批)补丁: P2-2 / P2-3 / P2-10 / P2-11 / P2-14
P2-7 经复核已由 P1-2 修复(_mark_mcap_degraded/_mark_loss_degraded 均有当日守卫), 无需代码改动。
GBK 安全编辑法: encoding='gbk', newline='' + split/join('\r\n'), 锚点全部带命中计数断言
"""
P = 'zt_shrink_strategy_gbk.py'
raw = open(P, encoding='gbk', newline='').read()
lines = raw.split('\r\n')
BASE = len(lines)
assert BASE == 11203, 'base line count %d' % BASE
delta = 0

def find_seq(seq, start=0):
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

# ================= P2-14: data_gate 用户定稿口径知情注释 =================
i_try = None
for i, ln in enumerate(lines):
    if ln == '    try:' and lines[i + 1] == "        if not bool(getattr(G, 'loss_data_ok', True)):":
        i_try = i
        break
assert i_try is not None, 'P2-14 anchor not found'
lines[i_try:i_try] = [
    '    # P2-14修复(2026-10-19): 知情注释——以下各"数据降级"分支的放行/拦截口径是用户',
    '    # 2026-10-02 明确拍板的定稿, 不是疏漏: 硬降级(业绩数据全挂/历史覆盖率不足/持仓',
    '    # 行情连续陈旧)是否停新买由 NEW_BUY_DATA_BLOCK 决定(默认False=只强提示不停买),',
    '    # 软降级(未达MIN_UNIVERSE_RATIO/数据未就绪)一律只提示不拦截; 想改成"降级即停',
    '    # 新买"只需把 NEW_BUY_DATA_BLOCK 置 True, 无需改代码。内部异常路径另按',
    '    # MARKET_TIDE_ERR_BLOCK_N 连续次数升级拦截(见下方 except 分支注释)。',
]
delta += 6
print('P2-14 done')

# ================= P2-10: buy_stock 仙股下限当天现价复核 =================
replace_seq(
    ["        scope_refuse(s, '买入')",
     '        return None',
     '    if plan:'],
    ["        scope_refuse(s, '买入')",
     '        return None',
     '    # P2-10修复(2026-10-19): 仙股下限当天现价复核——risk_blocked 里的 RISK_MIN_PRICE',
     '    # 检查用的是已完成交易日收盘(comp[-1]), 盘中现价可能已跌破下限(昨收2.05元、',
     '    # 今日跌到1.98元), 原逻辑当天不会再拦, 会在仙股上触发买入; 这里在发单前用',
     '    # 实时最新价(lp)按同一阈值复核一次, 跌破即拒单。选股语义不变, 只补盘中时段',
     '    # 缺口; lp 不可用(<=0)时跳过复核(仍由选股阶段的收盘口径把关)',
     '    if RISK_MIN_PRICE > 0 and _f(lp) > 0 and _f(lp) < RISK_MIN_PRICE:',
     "        log(disp(s), '买入拒绝: 现价%.3f已低于仙股下限%.1f元(盘中复核, 选股阶段收盘口径未覆盖盘中下跌)'",
     '            % (_f(lp), RISK_MIN_PRICE))',
     '        return None',
     '    if plan:'])
print('P2-10 done')

# ================= P2-11a: _fin_unknown_rd 助手(插在 risk_blocked 之前) =================
i_rb = None
for i, ln in enumerate(lines):
    if ln == 'def risk_blocked(s, comp):':
        i_rb = i
        break
assert i_rb is not None, 'P2-11a anchor not found'
helper11 = [
    'def _fin_unknown_rd():',
    '    """P2-11修复(2026-10-19): 业绩报告期未知→保守剔除的每日守卫+计数(与',
    '    _mark_mcap_degraded 同一模式: 每日首次 trigger_log 强提示, 后续仅计数不刷屏)"""',
    '    try:',
    "        if getattr(G, 'fin_unknown_rd_date', '') != G.today:",
    '            G.fin_unknown_rd_date = G.today',
    '            G.fin_unknown_rd_n = 0',
    "        G.fin_unknown_rd_n = int(getattr(G, 'fin_unknown_rd_n', 0) or 0) + 1",
    '        if G.fin_unknown_rd_n == 1:',
    "            trigger_log('业绩报告期未知-保守剔除', '选股',",
    "                        '数据源只返回净利润数值、未返回报告期(无法验证15个月时效), '",
    "                        '按保守规则剔除(与业绩数据缺失=剔除同家风); 若批量出现, '",
    "                        '请检查 QMT 财务接口字段是否变更',",
    '                        mode=TRADE_MODE)',
    "            log('保守剔除: 业绩报告报告期未知(无法做15个月时效校验), 当日首次已强提示, 后续仅计数')",
    '    except Exception:',
    '        pass',
    '',
    '',
]
lines[i_rb:i_rb] = helper11
delta += len(helper11)
print('P2-11a done')

# ================= P2-11b: 报告期未知=保守剔除(改 staleness 校验入口) =================
replace_seq(
    ["            if _ny > 0 and _nm > 0 and _rd10[:4].isdigit() and _rd10[4:6].isdigit():"],
    ["            _rd_ok = bool(_rd10[:4].isdigit() and _rd10[4:6].isdigit())",
     '            if _ny > 0 and _nm > 0 and not _rd_ok:',
     '                # P2-11修复(2026-10-19): 报告期未知=保守剔除。原逻辑只在 report_date',
     '                # 为8位数字时才做15个月时效校验, 而 get_financial_data 用法2(barpos 取值)',
     '                # 与 jqdata 兜底分支会返回 report_date=未知, 陈旧校验被静默跳过——一份',
     '                # 可能是年前的旧报告会被当成有效数据放行; 遵循本文件"取数未知=保守剔除"',
     '                # 的一贯家风(与 RISK_LOSS_MISSING_DEGRADE=False 同思路), 未知报告期',
     '                # 一律剔除并计数告警(每日首次强提示, 后续仅计数不刷屏)',
     '                _fin_unknown_rd()',
     "                return ('最新一期业绩报告报告期未知(数据源仅返回值未返回报告期, 无法验证15个月时效) | '",
     "                        '字段=%s | 取值=%.2f万元 | 数据源=%s | 按保守规则剔除'",
     "                        % (profit.get('field', ''), profit.get('value', 0.0) / 10000.0,",
     "                           profit.get('source', '')))",
     '            if _ny > 0 and _nm > 0 and _rd_ok:'])
print('P2-11b done')

# ================= P2-3a: _STATE_SCHEMA(插在 load_state 之前) =================
i_ls = None
for i, ln in enumerate(lines):
    if ln == 'def load_state():':
        i_ls = i
        break
assert i_ls is not None, 'P2-3a anchor not found'
schema = [
    '# P2-3修复(2026-10-19): 状态文件关键字段类型基线(与下方 load_state 的 st 默认值同源)。',
    '# 磁盘状态文件可能被外部工具/旧版本/手工编辑损坏(如 hold 变成 list、trades 变成 dict、',
    '# buys.n 变成字符串), 原 st.update(disk) 直接合入坏字段, 会让后续 hold.items()/',
    '# trades.append() 抛异常或静默错算; 现在合入前先按本基线校验, 坏字段重置为默认值。',
    '# 数值字段 int/float 互相兼容(JSON 不区分 0 与 0.0), bool 不算数值。',
    '_STATE_SCHEMA = {\'hold\': {}, \'done\': {}, \'names\': {}, \'names_ts\': {},',
    '                 \'sold\': {}, \'realized\': {}, \'pnlmeta\': {}, \'sell_ctx\': {},',
    '                 \'ledger_sold\': {}, \'lock\': {}, \'handoff\': {}, \'buy_ctx\': {},',
    '                 \'ordids\': {}, \'processed_deals\': {}, \'order_fills\': {},',
    '                 \'submit_intents\': {}, \'manual_fill\': {}, \'manual_avg_cost\': {},',
    '                 \'trades\': [], \'buys\': {\'date\': \'\', \'n\': 0, \'codes\': []},',
    '                 \'last_dl_date\': \'\', \'last_init_date\': \'\', \'trap_used\': 0.0,',
    '                 \'pos_empty_n\': 0}',
    '',
]
lines[i_ls:i_ls] = schema
delta += len(schema)
print('P2-3a done')

# ================= P2-3b: st.update(disk) 前加字段类型校验 =================
replace_seq(
    ['            st.update(disk)'],
    ['            # P2-3修复(2026-10-19): 合入前字段类型校验(详见上方 _STATE_SCHEMA 说明)',
     '            _bad = []',
     '            for _fk, _fd in _STATE_SCHEMA.items():',
     '                if _fk not in disk:',
     '                    continue',
     '                _v = disk[_fk]',
     '                _ok = isinstance(_v, type(_fd))',
     '                if not _ok and type(_fd) in (int, float) \\',
     '                        and isinstance(_v, (int, float)) and not isinstance(_v, bool):',
     '                    _ok = True          # JSON 不区分 int/float, 数值字段互相兼容',
     '                if not _ok:',
     "                    _bad.append('%s(%s)' % (_fk, type(_v).__name__))",
     '                    disk[_fk] = _fd',
     '            # buys 内层结构校验(外层 dict 通过但 n/codes 坏同样会错算当日名额)',
     "            if isinstance(disk.get('buys'), dict):",
     "                _bn = disk['buys'].get('n', 0)",
     '                if not isinstance(_bn, int) or isinstance(_bn, bool) \\',
     "                        or not isinstance(disk['buys'].get('codes', []), list):",
     "                    _bad.append('buys.n/codes(内层)')",
     "                    disk['buys'] = {'date': '', 'n': 0, 'codes': []}",
     '            # hold 是本策略持仓命脉: 容器本身损坏=灾难场景(持仓记录全丢+可能重复买入),',
     '            # 重置后必须停新买等人工核对; 容器完好但个别记录损坏, 仅摘除坏记录',
     "            if not isinstance(disk.get('hold'), dict):",
     "                _bad.append('hold(容器损坏, 已停新买等人工核对)')",
     "                disk['hold'] = {}",
     '                G.state_broken = True',
     '            elif disk.get(\'hold\'):',
     "                _hv = {_k: _v for _k, _v in disk['hold'].items() if isinstance(_v, dict)}",
     '                if len(_hv) != len(disk[\'hold\']):',
     "                    _bad.append('hold(%d条坏记录已摘除)' % (len(disk['hold']) - len(_hv)))",
     "                    disk['hold'] = _hv",
     '            if _bad:',
     "                log('[安全][告警] 状态文件字段类型异常, 已按基线重置: %s | 文件=%s'",
     "                    % (', '.join(_bad), cand))",
     '                try:',
     "                    pnl_alert('[安全][告警] 状态文件字段异常已重置: %s | 请检查是否有外部工具'",
     "                              '改动状态文件; hold损坏时已停新买, 需人工核对券商持仓' % ', '.join(_bad))",
     '                except Exception:',
     '                    pass',
     '            st.update(disk)'])
print('P2-3b done')

# ================= P2-2a: _FP_DENY + _fp_keys(插在 param_fingerprint 之前) =================
i_pf = None
for i, ln in enumerate(lines):
    if ln == 'def param_fingerprint():':
        i_pf = i
        break
assert i_pf is not None, 'P2-2a anchor not found'
fphelp = [
    '# P2-2修复(2026-10-19): param_fingerprint 排除清单——非行为型常量(纳入只会因部署',
    '# 环境差异产生误报, 不会产生"行为变了却发现不了"的漏报, 故排除)',
    '_FP_DENY = {',
    "    'BLACKLIST_FILE', 'EMERGENCY_FILE', 'MANUAL_ALERT_FILE', 'PNL_LEDGER_CSV',",
    "    'RUN_LOG_FILE', 'STATE_FILE', 'ST_HIST_FILE',            # 部署路径/文件名",
    "    'CSV_ENCODING', 'LOG_ENCODING', 'LOG_FILE_ENCODING',     # 编码(环境相关)",
    "    'NOTIFY_WEBHOOK', 'NOTIFY_ALLOWED_HOSTS', 'NOTIFY_TIMEOUT',  # 通知基础设施",
    "    'ACCOUNT_ID', 'STRAT_TAG', 'BUY_BLOCK_TAG', 'TRAP_TAG',  # 账户/订单标签",
    "    'ORDER_STATUS_MAP', 'PHASE_NAME',                        # 展示用映射(非决策)",
    "    'SENT_STATE',                                            # 运行时状态(非配置)",
    '}',
    '',
    'def _fp_keys():',
    '    """P2-2: 自动捕获行为型全局常量——UPPER_CASE、非下划线前缀、非 _FP_DENY、',
    '    取值为标量/容器(int/float/bool/str/tuple/list/dict/None); 排除 G 等对象与函数。',
    '    本函数只被 param_fingerprint 在启动时调用一次, 此时 globals() 已含全部常量',
    '    (含文件后部的 SENT_*), 自动捕获安全。"""',
    "    _T = (int, float, bool, str, tuple, list, dict, type(None))",
    '    _g = globals()',
    "    return [k for k in _g if k.isupper() and not k.startswith('_')",
    "            and k not in _FP_DENY and isinstance(_g[k], _T)]",
    '',
    '',
]
lines[i_pf:i_pf] = fphelp
delta += len(fphelp)
print('P2-2a done')

# ================= P2-2b: keys 显式列表 -> 自动捕获 =================
i_keys = None
for i in range(i_pf + len(fphelp), len(lines)):
    if lines[i] == "    keys = ['VERSION', 'NEVER_STOP_LOSS', 'CONFIRM_ENTRY_ON', 'MA5_RECLAIM_ON', 'STALL_CONFIRM_ON',":
        i_keys = i
        break
assert i_keys is not None, 'P2-2b keys anchor not found'
i_close = None
for i in range(i_keys + 1, i_keys + 40):
    if lines[i].strip().startswith(']'):
        i_close = i
        break
assert i_close is not None, 'P2-2b close anchor not found'
old_n = i_close - i_keys + 1
new_keys = [
    '    # P2-2修复(2026-10-19): 显式列表 -> 自动捕获(机制根治漏参)。原显式列表已三度漏参',
    '    # (V2.6.81 新加的 MARKET_CAP_MIN_YI/MAX_YI、SENT_REGIME_PANIC_LO、',
    '    # SENT_EVT_FRENZY_*/SENT_EVT_PANIC_* 等约40个行为参数未纳入), 指纹失真导致',
    '    # "参数没变但行为变了"无法被发现; 现自动收集全部 UPPER_CASE 模块级常量(标量/',
    '    # 容器), 仅排除与行为无关的路径/URL/编码/账户/展示映射/运行时状态(见 _FP_DENY);',
    '    # VERSION 仍纳入(版本变更=指纹变更, 沿用 V2.6.70 决定)。注意: 本函数只在启动时',
    '    # 调用一次, 此时 globals() 已含全部常量(含文件后部的 SENT_*), 自动捕获安全。',
    '    keys = sorted(_fp_keys())',
]
lines[i_keys:i_close + 1] = new_keys
delta += len(new_keys) - old_n
print('P2-2b done: %d lines -> %d lines' % (old_n, len(new_keys)))

# ================= 写回 =================
assert len(lines) == BASE + delta, 'delta mismatch: %d vs %d' % (len(lines), BASE + delta)
open(P, 'w', encoding='gbk', newline='').write('\r\n'.join(lines))
print('written. base=%d delta=%+d new=%d' % (BASE, delta, len(lines)))
print('ALL P2-BATCH-C OK')
