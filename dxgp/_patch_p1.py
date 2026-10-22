"""P1-1/P1-2 补丁: 名称取数失败保守剔除 + 换手率/市值缺失计数与强提醒
安全约定: 读写均 newline='' 保留 CRLF; 每个锚点必须唯一命中; 改完 compile 自检
"""
import io, sys

PATH = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"

with io.open(PATH, "r", encoding="gbk", newline="") as f:
    text = f.read()

assert "\r\n" in text, "no CRLF found"
body = text.replace("\r\n", "")
assert "\n" not in body and "\r" not in body, "mixed line endings detected"
lines = text.split("\r\n")
print("lines=%d" % len(lines))

edits = []

def find_one(anchor):
    hits = [i for i, l in enumerate(lines) if anchor in l]
    assert len(hits) == 1, "anchor %r matched %d lines" % (anchor[:60], len(hits))
    return hits[0]

def replace_line(anchor, new_lines, tag):
    i = find_one(anchor)
    if isinstance(new_lines, str):
        new_lines = [new_lines]
    lines[i:i+1] = new_lines
    edits.append(tag)

def insert_after(anchor, new_lines, tag):
    i = find_one(anchor)
    if isinstance(new_lines, str):
        new_lines = [new_lines]
    lines[i+1:i+1] = new_lines
    edits.append(tag)

# ---------- Edit 1: name_known() 助手(插在 is_st_name 的 return 行之后) ----------
anchor1 = "    return 'ST' in _n"
i1 = find_one(anchor1)
helper = [
    "",
    "",
    "def name_known(stock):",
    "    \"\"\"审计P1-1修复(第十四轮零预设审计, 2026-10-19): 股票名称是否可信。",
    "    旧逻辑缺口: inst_name 取数失败时返回空串(或过期缓存), is_st_name('')=False,",
    "    导致 excluded()(选股层)与 risk_blocked()(避雷层)对同一只票同时静默失效 ——",
    "    接口抖动当天, *ST 股可混入候选池; 叠加上\"绝不止损\"铁律, 套住即死等。",
    "    本函数口径: 名称为空/纯空白=身份不明, 调用方必须保守剔除。\"\"\"",
    "    try:",
    "        _nm = inst_name(stock)",
    "        return bool(_nm and str(_nm).strip())",
    "    except Exception:",
    "        return False",
]
lines[i1+1:i1+1] = helper
edits.append("E1 name_known helper")

# ---------- Edit 2: excluded() 名称不可信保守剔除 ----------
anchor2 = "if EXCLUDE_ST and is_st_name(inst_name(stock)):"
i2 = find_one(anchor2)
assert lines[i2+1].strip() == "return 'ST'", "unexpected next line: %r" % lines[i2+1]
new2 = [
    "    if EXCLUDE_ST:",
    "        # 审计P1-1: 名称不可信(取数失败)=身份不明, 保守剔除, 不再静默放行",
    "        if not name_known(stock):",
    "            return '名称取数失败(身份不明,保守剔除)'",
    "        if is_st_name(inst_name(stock)):",
    "            return 'ST'",
]
lines[i2:i2+2] = new2
edits.append("E2 excluded conservative")

# ---------- Edit 3: risk_blocked() 名称不可信保守剔除 ----------
anchor3 = "    if '退' in name:"
i3 = find_one(anchor3)
new3 = [
    "    # 审计P1-1: 名称取数失败=身份不明, 与选股层 excluded() 同口径保守剔除",
    "    if not (name and str(name).strip()):",
    "        return '名称取数失败(身份不明,按保守规则剔除)'",
    "    if '退' in name:",
]
lines[i3:i3+1] = new3
edits.append("E3 risk_blocked conservative")

# ---------- Edit 4: 漏斗计数器新增 st_namefail / st_turnover_missing ----------
anchor4 = "st_held = st_nozt = st_multi = st_done = st_win = st_vol_t0 = st_vol_base = st_turnover"
i4 = find_one(anchor4)
insert_after(anchor4,
    "    st_namefail = st_turnover_missing = 0   # 审计P1-1/P1-2: 名称取数失败保守剔除数 / 换手率字段缺失数(不再静默跳过)",
    "E4 counters init")

# ---------- Edit 5: excluded() 调用点按原因分流计数 ----------
anchor5 = "        if excluded(s):"
i5 = find_one(anchor5)
assert lines[i5+1].strip() == "st_excl += 1" and lines[i5+2].strip() == "continue"
new5 = [
    "        _exr = excluded(s)",
    "        if _exr:",
    "            if _exr.startswith('名称取数失败'):",
    "                st_namefail += 1",
    "            st_excl += 1",
    "            continue",
]
lines[i5:i5+3] = new5
edits.append("E5 excluded call site")

# ---------- Edit 6: 换手率字段缺失计数(插 else 分支) ----------
anchor6 = "                if ZT_TURNOVER_MAX > 0 and _to > ZT_TURNOVER_MAX:"
i6 = find_one(anchor6)
assert lines[i6+1].strip() == "st_turnover += 1" and lines[i6+2].strip() == "continue"
new6 = [
    "                if ZT_TURNOVER_MAX > 0 and _to > ZT_TURNOVER_MAX:",
    "                    st_turnover += 1",
    "                    continue",
    "            else:",
    "                # 审计P1-2: 换手率字段缺失不再静默跳过整条过滤(旧逻辑全市场悄悄",
    "                # 失效且漏斗无计数, 运维看到\"过滤正常\"假象); 计入缺失数并在汇总明示",
    "                st_turnover_missing += 1",
]
lines[i6:i6+3] = new6
edits.append("E6 turnover missing counter")

# ---------- Edit 7: 漏斗汇总日志补两个计数 ----------
anchor7 = "log('           -> 换手率不符%d / 成交额不足%d / 板块或名称排除%d / 历史ST%d / 避雷风险%d / '"
i7 = find_one(anchor7)
new7 = ("log('           -> 换手率不符%d(字段缺失%d) / 成交额不足%d / 板块或名称排除%d(名称取数失败%d) / "
        "历史ST%d / 避雷风险%d / '")
lines[i7] = new7
anchor7b = "% (st_turnover, st_amt, st_excl, st_sthist, st_risk, st_ma10, st_lowhold, st_hot,"
i7b = find_one(anchor7b)
lines[i7b] = ("% (st_turnover, st_turnover_missing, st_amt, st_excl, st_namefail, st_sthist, "
              "st_risk, st_ma10, st_lowhold, st_hot,")
edits.append("E7 funnel log")

# ---------- Edit 8: _mark_mcap_degraded() 函数(插在 _mark_loss_degraded 的 except pass 之后) ----------
anchor8 = "    if getattr(G, 'loss_degrade_date', '') != G.today:"
i8 = find_one(anchor8)
# 找到 _mark_loss_degraded 函数结尾(其 except Exception: pass 后的空行)
j = i8
while "pass" not in lines[j]:
    j += 1
# j 是 pass 行; 确认其上层是 except Exception:
assert "except Exception:" in lines[j-1]
mcap_fn = [
    "",
    "",
    "def _mark_mcap_degraded(n_degrade=0, n_checked=0):",
    "    \"\"\"审计P1-2修复(第十四轮, 2026-10-19): 流通市值降级放行占比过高时每日一条强提醒。",
    "    与 _mark_loss_degraded 同规格(每日守卫+trigger_log); 只提醒不改筛选行为",
    "    (MARKET_CAP_DEGRADE=True 仍放行不误剔), 提醒运维尽快排查数据源。\"\"\"",
    "    try:",
    "        if getattr(G, 'mcap_degrade_date', '') != G.today:",
    "            G.mcap_degrade_date = G.today",
    "            _pct = (n_degrade * 100.0 / n_checked) if n_checked > 0 else 0.0",
    "            trigger_log('流通市值筛选降级过半', '选股',",
    "                        '本轮%d只候选中%d只取不到流通股本被降级放行(占比%.0f%%), '",
    "                        '市值筛选名义开启实则大半失效, 请检查 get_instrument_detail '",
    "                        '字段拼写(CirculatingVolume/FloatVolume/FloatVolumn)与数据权限'",
    "                        % (int(n_checked), int(n_degrade), _pct),",
    "                        mode=TRADE_MODE)",
    "            log('【降级模式】流通市值筛选: %d/%d只取不到流通股本已降级放行(占比%.0f%%), '",
    "                '30~150亿筛选大半失效, 请尽快检查数据源(本日仅提醒一次)'",
    "                % (int(n_degrade), int(n_checked), _pct))",
    "    except Exception:",
    "        pass",
]
lines[j+1:j+1] = mcap_fn
edits.append("E8 _mark_mcap_degraded")

# ---------- Edit 9: 市值降级过半调用 + 名称失败强提醒 ----------
anchor9 = "st_mcap_miss, st_mcap_degrade))"
i9 = find_one(anchor9)
call9 = [
    "                st_mcap_miss, st_mcap_degrade))",
    "        # 审计P1-2: 降级放行占比过高(>=50%)时按财务降级同规格每日一条强提醒",
    "        _mcap_checked8 = st_mcap_low + st_mcap_high + st_mcap_miss + st_mcap_degrade",
    "        if _mcap_checked8 > 0 and st_mcap_degrade * 2 >= _mcap_checked8:",
    "            _mark_mcap_degraded(st_mcap_degrade, _mcap_checked8)",
]
lines[i9:i9+1] = call9
edits.append("E9 mcap degrade call")

anchor9b = "    if blocked:"
i9b = find_one(anchor9b)
alert9 = [
    "    # 审计P1-1: 名称取数失败强提醒(每日至多一条由 _mark 系列同规格, 此处为日志明示)",
    "    if st_namefail > 0:",
    "        log('[数据告警][强提醒] 本轮%d只股票名称取数失败(身份不明), 已按保守规则剔除; '",
    "            '若多个轮次持续出现, 请检查行情接口 get_instrument_detail 可用性'",
    "            % st_namefail)",
    "    if blocked:",
]
lines[i9b:i9b+1] = alert9
edits.append("E9b namefail alert")

# ---------- 写回 + 自检 ----------
out = "\r\n".join(lines)
with io.open(PATH, "w", encoding="gbk", newline="") as f:
    f.write(out)

# 自检: 重新读取并编译
with io.open(PATH, "r", encoding="gbk", newline="") as f:
    chk = f.read()
compile(chk, PATH, "exec")
for t in ["def name_known(", "st_turnover_missing", "_mark_mcap_degraded", "名称取数失败(身份不明,保守剔除)"]:
    assert t in chk, "post-check missing: %s" % t
print("EDITS APPLIED: %s" % ", ".join(edits))
print("POST-CHECK OK: compile + markers, new line count=%d" % len(chk.split("\r\n")))
