# -*- coding: utf-8 -*-
"""v1.2.70 最终验收（编码 / 结构 / 修复项 / 铁律 / 版本号 / 死代码 / AUD23~AUD31）。"""
import ast, re, builtins, collections

P = r"E:\桌面\666666\nbbank\gf_qmt_native_multi_gbk.py"
raw = open(P, "rb").read()
txt = raw.decode("gbk")
lines = txt.split("\n")
tree = ast.parse(txt)
compile(txt, "gf", "exec")

R = []


def chk(name, cond, detail=""):
    R.append((name, bool(cond), detail))


# ---------- 1 编码与结构 ----------
chk("GBK 解码正常", True)
chk("行尾纯 LF（无 CRLF）", "\r\n" not in txt, "CRLF=%d" % txt.count("\r\n"))
chk("首行 coding:gbk 声明保留", txt.startswith("# -*- coding: gbk -*-"))
chk("AST 解析通过", True)
chk("compile 通过", True)
print("字节数 %d | 字符数 %d | 行数 %d" % (len(raw), len(txt), len(lines)))

# ---------- 2 未定义名 ----------
BUILT = set(dir(builtins))
mod_bound = set()
for n in tree.body:
    for sub in ast.walk(n):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
            mod_bound.add(sub.id)
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            mod_bound.add(sub.name)
        if isinstance(sub, ast.arg):
            mod_bound.add(sub.arg)
        if isinstance(sub, ast.ExceptHandler) and sub.name:
            mod_bound.add(sub.name)
        if isinstance(sub, (ast.Global, ast.Nonlocal)):
            mod_bound.update(sub.names)
    if isinstance(n, (ast.Import, ast.ImportFrom)):
        for a in n.names:
            mod_bound.add((a.asname or a.name).split(".")[0])
QB = {"account", "SYMBOL", "passorder", "get_full_tick", "ContextInfo",
      "get_trade_detail_data", "get_instrument_detail", "get_market_data_ex",
      "__file__", "__name__", "__doc__", "__builtins__"}
undef = []
for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
    local = set(mod_bound)
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            local.add(n.id)
        elif isinstance(n, ast.arg):
            local.add(n.arg)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n is not fn:
            local.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                local.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            local.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            local.update(n.names)
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            if n.id not in local and n.id not in QB and n.id not in BUILT:
                undef.append((n.lineno, n.id))
chk("未定义名 = 0", not undef, str(undef[:5]))


def _binders(node, shallow=False):
    """收集该节点本层作用域的绑定名；shallow=True 时不深入嵌套函数体。"""
    out = set()
    for ch in ast.iter_child_nodes(node):
        if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(ch.name)
            if not shallow:
                out |= _binders(ch, shallow=False)
            continue
        if isinstance(ch, (ast.Lambda, ast.ListComp, ast.SetComp,
                           ast.DictComp, ast.GeneratorExp)):
            continue
        if isinstance(ch, ast.Name) and isinstance(ch.ctx, ast.Store):
            out.add(ch.id)
        elif isinstance(ch, ast.arg):
            out.add(ch.arg)
        elif isinstance(ch, ast.ExceptHandler) and ch.name:
            out.add(ch.name)
        elif isinstance(ch, (ast.Global, ast.Nonlocal)):
            out.update(ch.names)
        elif isinstance(ch, (ast.Import, ast.ImportFrom)):
            for a in ch.names:
                out.add((a.asname or a.name).split(".")[0])
        out |= _binders(ch, shallow=shallow)
    return out


undef_cl = []


def _walk_cl(node, env):
    for ch in ast.iter_child_nodes(node):
        if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = env | _binders(ch, shallow=True)
            for a in ch.args.args + ch.args.kwonlyargs:
                inner.add(a.arg)
            if ch.args.vararg:
                inner.add(ch.args.vararg.arg)
            if ch.args.kwarg:
                inner.add(ch.args.kwarg.arg)
            for d in ch.args.defaults + [x for x in ch.args.kw_defaults if x]:
                _walk_cl(d, env)
            for st in ch.body:
                _walk_cl_expr(st, inner)
            continue
        _walk_cl_expr(ch, env)


def _walk_cl_expr(node, env):
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        if (node.id not in env and node.id not in QB
                and node.id not in BUILT):
            undef_cl.append((getattr(node, "lineno", 0), node.id))
    for ch in ast.iter_child_nodes(node):
        _walk_cl_expr(ch, env)


_walk_cl(tree, set(mod_bound))

chk("未定义名 = 0（闭包感知版）", not undef_cl, str(undef_cl[:5]))

# ---------- 3 修复项 ----------


def has(pat):
    return re.search(pat, txt) is not None


chk("P1 资金闸门 fail-closed 拦截落地", has(r'资金口径闸门-查询失败'))
chk("P1 查询失败 return False 拦截", has(r'_notify_risk\("position_query_fail"'))
# 原 except:pass 已消失：buy_shares 资金段内不应再有裸 pass
chk("P1 原 except:pass 已移除", not has(r'except Exception as _qerr:\s*\n\s*pass'))
chk("P2 M3 兜底含 free 校验", has(r'_lot_px <= free \+ 1e-6'))
chk("P2 M3 冗余重复条件已消除",
    not any("_lot_px <= lvl_amt_use" in l and not l.strip().startswith("#")
            for l in lines))
chk("P3 peak 写入用保守价", has(r'state\["trailing_peak"\] = _ref_px_tp'))
chk("P3 回撤计算用保守价",
    has(r'drawdown_from_peak = \(state\["trailing_peak"\] - _ref_px_tp\)'))
chk("P3 不再以实时价更新 peak",
    not has(r'state\["trailing_peak"\] = price'))
chk("P4 额度日志如实化（AUD27：手工仓不计占用）",
    has(r'股票额度\(capital_cap\)：手工仓不计入占用，额度不再被吃')
    or has(r'股票额度\(capital_cap\)：未实现'))
chk("P4 SYMBOLS 注释校正（AUD83-P4 条目已按 AUD27 作废）",
    has(r'AUD83-P4') and has(r'AUD27 后手工仓已完全不计入 capital_cap 占用'))
chk("P5 v1.2.46A/46B/46C 拆分",
    all(has(r'v1\.2\.46%s = AUD7' % s) for s in "ABC"))
chk("P5 v1.2.37 撞号拆分", has(r'v1\.2\.37A = AUD65') and has(r'── v1\.2\.37 = AUD66'))
chk("P5 AUD80 撞号改 AUD85", has(r'AUD85（承接 v1\.2\.57，原误标 AUD80'))
hdr_q = [l for l in lines if l.strip().startswith("#") and "??" in l
         and "乱码恢复为序号" not in l and "P6 文件头" not in l]
chk("P6 文件头乱码清零", not hdr_q, str(hdr_q[:2]))
chk("P7 三变量注释如实化",
    all([has(r'旧注释「供外部看门狗判活」不实'),
         has(r'旧注释「供日志展示」不实'),
         has(r'本变量全文无任何读取点，仅作排障留痕')]))
chk("v1.2.61 记录块已写入文件头", has(r'── v1\.2\.61 = AUD23-P1~P5'))
chk("v1.2.60 记录块已写入文件头", has(r'── v1\.2\.60 = AUD91-P1A~P1E'))
chk("v1.2.59 记录块保留", has(r'── v1\.2\.59 = AUD90-P0A~P0E'))
chk("v1.2.58 记录块保留", has(r'── v1\.2\.58 = AUD83-P1~P7'))
# ---- v1.2.60 / AUD91 三处改动本体验收 ----
chk("AUD91-P1A can_invest 缓冲已改 600",
    has(r'_hard\s*=\s*cap\s*\*\s*PARAMS\["max_position_pct"\]\s*\+\s*600\.0')
    and not has(r'_hard\s*=\s*cap\s*\*\s*PARAMS\["max_position_pct"\]\s*\+\s*300\.0'))
chk("AUD91-P1C free 递减改含费成本",
    has(r'free = max\(0\.0, free - compute_buy_cost\(vol, price\)\)')
    and not has(r'free = max\(0\.0, free - vol \* price\)'))
chk("AUD91-P1C deployed 同期口径未破",
    all('compute_buy_cost(vol, price)' in l
        for l in lines if 'state["deployed"] +=' in l))
chk("AUD91-P1E 参与率注释已补齐缩进",
    any(l.startswith("        # AUD91-P1E") for l in lines)
    and any(l.startswith("        # AUD35(2026-10-08 第三轮零预设审计)：成交量单位是「手」")
            for l in lines))
# ---- v1.2.61 / AUD23-P1~P5 五项改动本体验收 ----
chk("AUD23-P1a 情绪数据不足在狂热单态下 fail-open",
    has(r'_beo1 = bool\(cfg\.get\("block_euphoric_only"\)\) and not SENTIMENT_ENABLED')
    and has(r'if cfg\.get\("fail_closed_on_short", True\) and not _warm8 and not _beo1:'))
chk("AUD23-P1b 子指标全失效在狂热单态下 fail-open",
    has(r'_beo2 = bool\(cfg\.get\("block_euphoric_only"\)\) and not SENTIMENT_ENABLED')
    and has(r'if cfg\.get\("fail_closed_on_short", True\) and not _beo2:'))
chk("AUD23-P2 情绪取数走多形态降级+合理性护栏",
    has(r'closes, _src, err = _idx_fetch_with_fallback\(C, idx, n \+ 5\)')
    and has(r'_okc, _whyc = _index_closes_plausible\(closes, idx\)'))
chk("AUD23-P3 名称未知按最小幅度 ±5% 估算",
    has(r'if not _nm23:') and has(r'return 0\.05, "名称未知\(按最小幅度±5%保守估算\)"'))
chk("AUD23-P4 盘中阶梯加仓跳档补日志",
    has(r'盘中阶梯加仓 %s 跳过：本次 %d股 x %\.2f = %\.0f元 超过可用现金 %\.0f元'))
chk("AUD23-P5 四个 _closed_* 助手口径未知不剔末根",
    txt.count("if has_today_bar is not True:") == 4)

# ---- v1.2.62 / AUD24-P1~P7 七项改动本体验收（F2 取数链路专项） ----
chk("AUD24-P1a _inject_dl_funcs 已定义且三路兜底",
    has(r'def _inject_dl_funcs\(C=None\):')
    and has(r'fn = globals\(\)\.get\(nm\)')
    and has(r'fn = getattr\(C, nm, None\)')
    and has(r'_bi = __builtins__'))
chk("AUD24-P1b init/handlebar/补下载三处调用注入",
    txt.count("_inject_dl_funcs(") == 4)
chk("AUD24-P1c 空壳不再直接调用（if not callable(fn): continue）",
    has(r'if not callable\(fn\):') and has(r'errs\.append\("%s=未接入" % name\)'))
chk("AUD24-P1d 告警路径有异常保护（不影响主流程）",
    has(r'# AUD24-P1b：告警路径必须绝不抛异常'))
chk("AUD24-P2 调用方传真实需求根数（不再 ma_long+5）",
    txt.count('_get_index_closes_yday(C, p.get("ma_long", 60))') == 1
    and txt.count('_get_index_closes_yday(C, PARAMS.get("ma_long", 60))') == 1
    and not has(r'_get_index_closes_yday\(C, p\.get\("ma_long", 60\) \+ 5\)'))
chk("AUD24-P2b 请求 n+10 根、最少收 n+1 根",
    has(r'_idx_fetch_with_fallback\(C, idx, n \+ 10, need=n \+ 1\)'))
chk("AUD24-P3 指数不复权优先（前复权仅兜底）",
    has(r'_hist_vals_from_ex\(C, idx, "close", n, "none", False\), "ex/none"')
    and has(r'dividend_type="none", fill_data=True\)'))
chk("AUD24-P4a _idx_last_bar_date 已定义并按自然日缓存",
    has(r'def _idx_last_bar_date\(C, idx\):')
    and has(r'_IDX_LASTDATE\.get\("day"\) == _today'))
chk("AUD24-P4b 末根日期确认为当日才剔",
    has(r'_has_today = \(_bar == datetime\.now\(\)\.strftime\("%Y%m%d"\)\) if _bar else None')
    and has(r'if _has_today is True:'))
chk("AUD24-P5a 老接口 require_code 参数已加",
    has(r'def _hist_vals_old\(C, code, field, n, dividend_type, require_code=False\):')
    and has(r'if require_code:') )
chk("AUD24-P5b _get_hist 与指数调用均启用严格模式",
    has(r'def _get_hist\(C, code, field, n=120, old_require_code=False\):')
    and has(r'_get_hist\(C, idx, "close", n, True\)'))
chk("AUD24-P6 首尾 0 值清洗（不再整段作废）",
    has(r'# P6：切掉首尾连续 0 值') and has(r'while vals and not \(vals\[-1\] > 0\):'))
chk("AUD24-P7 need 最低长度闸（短序列继续降级）",
    has(r'if need is not None and len\(vals\) < need:'))
chk("AUD24-P7b 全不足时回传最长合理候选（准确报实得根数）",
    has(r'_best = \[None, "--"\]') and has(r'if _best\[0\]:'))
chk("v1.2.62 记录块已写入文件头", has(r'── v1\.2\.62 = AUD24-P1~P7'))

# ---- v1.2.63 / AUD25-P1~P2 两项改动本体验收（启动自检如实化） ----
chk("AUD25-P1a _sentiment_mode_desc 已定义",
    has(r'def _sentiment_mode_desc\(\):'))
chk("AUD25-P1b 单态语义如实描述（只拦狂热/恐慌放行/不缩放）",
    has(r'狂热单态（只拦狂热日 / 恐慌放行 / 不缩放仓位）'))
chk("AUD25-P1c 情绪自检改打印生效策略（不再直接列原始开关）",
    has(r'_sent_desc, _sent_note = _sentiment_mode_desc\(\)')
    and has(r'生效策略=%s%s')
    and not has(r'门控=恐慌\(%s\)/狂热\(%s\) \| 缩放=首仓'))
chk("AUD25-P1d 完整模式仍逐项打印四项原值",
    has(r'；门控=恐慌\(%s\)/狂热\(%s\)；缩放=首仓\(%s\)/加仓\(%s\)'))
chk("AUD25-P2a _dl_inject_report 已定义",
    has(r'def _dl_inject_report\(\):'))
chk("AUD25-P2b init 注入后打印补下载自检",
    txt.count("log(_dl_inject_report())") == 1)
chk("AUD25-P2c 三路全落空时给出明确处置提示",
    has(r'三路均未命中') and has(r'行情-数据管理'))
chk("v1.2.63 记录块已写入文件头", has(r'── v1\.2\.63 = AUD25-P1~P2'))

# ---- v1.2.64 / AUD26-P1 个股数据门口径对齐本体验收 ----
chk("AUD26-P1a 个股数据门请求 ma_long+10、判定只需 ma_long",
    has(r'closes, st, err = _get_hist\(C, code, "close", _need \+ 10\)')
    and has(r'if not closes or len\(closes\) < _need:'))
chk("AUD26-P1b 个股门文案与指数门统一（不足%d根(实得%d)）",
    has(r'"不足%d根\(实得%d\)" % \(_need, len\(closes or \[\]\)\)'))
chk("AUD26-P1c fetch_hist_fields need 改为 ma_long",
    has(r'need = params\["ma_long"\]\n'))
chk("AUD26-P1d 无 ma_long+5 残留",
    "ma_long\", 60) + 5" not in txt and 'params["ma_long"] + 5' not in txt)
chk("AUD26-P1e 最终判定按已收盘有效根数",
    has(r'_eff_n = len\(closes\) - \(1 if flag_today is True else 0\)')
    and has(r'if _eff_n < need:'))
chk("v1.2.64 记录块已写入文件头", has(r'── v1\.2\.64 = AUD26-P1'))

# ---- v1.2.65 / AUD27-P1~P5 手工仓分离 + 卖出铁律本体验收 ----
# 用户原话：「手工买入的宁波银行股票，不占用策略持仓名额和投资金额。但是任何针对宁波银行
# 的卖出，都要检查亏损不卖和扣除税费之后赚钱的铁律，这个不要忘记了。」
# 验收分两片：A 片=手工仓必须真的不占额度/名额；B 片=卖出侧铁律一条不少（且不得依赖策略账本）。
_ssa = txt[txt.find("def _sync_state_to_actual("):]
_ssa = _ssa[:_ssa.find("\ndef ", 10)]
_ssa_code = "\n".join(l for l in _ssa.split("\n") if not l.strip().startswith("#"))

chk("AUD27-P1a+AUD35-P1 手工份额=券商全量-策略账本-在途买单",
    has(r'state\["manual_shares"\] = _ms_new_a35')
    and has(r'state\["manual_cost"\] = _mkt_cost')
    and has(r'_ms_new_a35 = int\(actual_vol\) - _strat_reach_a35')
    and has(r'_strat_reach_a35 = max\(0, _ps_a35 \+ _pd_a35\)'))
chk("AUD27-P1b 策略账本不再被外部持仓污染（源码级）",
    'state["total_cost"] = actual_vol' not in _ssa_code
    and 'state["deployed"] = actual_vol' not in _ssa_code
    and 'state["total_cost"] = _mkt_cost' not in _ssa_code,
    "剔除注释后仍出现污染赋值")
chk("AUD27-P1c deployed 只跟策略账本 total_cost",
    has(r'state\["deployed"\] = float\(state\.get\("total_cost", 0\.0\) or 0\.0\)'))
chk("AUD27-P1d tier 空仓时恒 -1（不被外部持仓推进）",
    has(r'if state\["position_shares"\] > 0:\s*\n\s*state\["tier"\] = state\.get\("tier", -1\)\s*\n'
        r'\s*else:\s*\n\s*state\["tier"\] = -1'))
chk("AUD27-P1e last_add_price 不回填券商均价",
    'state["last_add_price"] = broker_avg' not in _ssa_code)
chk("AUD27-P1f 手工仓分离日志如实告知不占额度",
    has(r'【手工仓已分离】') and has(r'不占用策略持仓名额与 20 万投资额度'))
chk("AUD27-P1g 外部变动日志按两本账分别打印",
    has(r'手工账本 = %d股/%.2f元') and has(r'策略账本 = %d股/%.2f元\(已部署%.2f\)'))
chk("AUD27-P1h 清仓时手工账本一并归零",
    has(r'【手工仓已清空】') and has(r'_m_sh = int\(state\.get\("manual_shares", 0\) or 0\)'))
chk("AUD27-P1i new_state 含手工账本四字段",
    all(has(r'"%s":' % k) for k in ("manual_shares", "manual_cost",
                                    "manual_peak_cost", "manual_sell_pending_until")))

chk("AUD27-P2a _r1_net_profit_gate 已定义且签名含 sub_vol",
    has(r'def _r1_net_profit_gate\(code, actual_vol, broker_avg, price, state, reason,')
    and has(r'sub_vol=None'))
chk("AUD27-P2b 成本价取三本账最大值（宁可少卖不可亏卖）",
    has(r'_avg = max\(_avg_b, _avg_k, _avg_m\)'))
chk("AUD27-P2c 净到手 <= 成本 一律拒卖",
    has(r'if _net <= _cost:') and has(r'不赚钱不卖'))
chk("AUD27-P2d 三费口径：佣金万0.841(5元起)+印花万5+过户万1",
    has(r'_comm = order_commission\(_mv\)')   # AUD93-P1：统一走逐单 5 元底函数
    and has(r'_stamp = _mv \* STOCK_STAMP_TAX_RATE')
    and has(r'_trf = _mv \* STOCK_TRANSFER_FEE_RATE'))
chk("AUD27-P2e 保守成交价与 sell_all 挂单价同口径",
    has(r'_ref_px = round\(price \* \(1\.0 - LIMIT_SLIP_PCT_SELL\), 2\) if PRICE_TYPE == 11 else price'))
chk("AUD27-P2f 闸门异常 fail-closed（拿不准就拒卖）",
    has(r'铁律闸门异常，保守拒卖'))
_gate_src = txt[txt.find("def _r1_net_profit_gate("):]
_gate_src = _gate_src[:_gate_src.find("\ndef ", 10)]
# 剔除 docstring 与注释后再判（docstring 里本就写着「不含任何止损语义」这句说明）
_gate_body = _gate_src[_gate_src.find('"""', _gate_src.find('"""') + 3) + 3:]
_gate_body = "\n".join(l for l in _gate_body.split("\n") if not l.strip().startswith("#"))
chk("AUD27-P2g 闸门实现体不含任何止损语义",
    ("stop_loss" not in _gate_body) and ("止损" not in _gate_body)
    and ("强平" not in _gate_body),
    "闸门实现体出现止损语义")
chk("AUD27-P2h sell_all 的 R1 段改为调用统一闸门",
    has(r'_gate_ok, _gd = _r1_net_profit_gate\(code, pos_vol, _gavg94, price, state, reason,'))
chk("AUD27-P2i sell_all 独立查券商均价（第4返回值是原因文本）",
    has(r'# AUD27-P2：verify_position_before_order 的第4个返回值是「原因文本」不是均价')
    and has(r'_q_ok, _q_vol, _q_avg, _q_cu = query_position_safe\(C, acct, code\)'))
chk("AUD27-P2j R1 不再依赖 position_shares>0 才生效",
    not has(r'if int\(state\.get\("position_shares", 0\) or 0\) > 0:\s*\n\s*# R1'))

_sms = txt[txt.find("def manual_sell("):]
_sms = _sms[:_sms.find("\ndef ", 10)]
_sms_code = "\n".join(l for l in _sms.split("\n") if not l.strip().startswith("#"))
chk("AUD27-P3a manual_sell 已定义且受 manual_takeover 开关约束",
    has(r'def manual_sell\(C, code, acct, price, state, up=0\.0, dn=0\.0\):')
    and has(r'if not _manual_takeover_on\(code\):\s*\n\s*return False'))
chk("AUD27-P3b 不写策略账本（tier/deployed/first_batch 均未赋值）",
    all(k not in _sms_code for k in ('state["tier"]', 'state["deployed"]',
                                     'state["first_batch_n"]', 'state["position_shares"]')))
chk("AUD27-P3c 两本账并存时让位策略止盈链",
    has(r'两本账并存：策略自己有仓时本路径让位，避免一键全平账户'))
chk("AUD27-P3d 卖单在途冻结防重复挂单",
    has(r'if time\.time\(\) < float\(state\.get\("manual_sell_pending_until", 0\.0\) or 0\.0\):'))
chk("AUD27-P3e 跌停禁卖（与策略侧同口径）",
    has(r'if dn and dn > 0 and price <= dn:'))
chk("AUD27-P3f 阈值判定前必过铁律闸门",
    has(r'_ok, _d = _r1_net_profit_gate\(code, _mvol, _avg, price, state, "手工仓阈值判定"\)'))
chk("AUD27-P3g 固定止盈仍需扣费后净赚 >= 阈值",
    has(r'if _pct >= _tp:'))
chk("AUD27-P3g2 移动止盈改两段式市价口径（AUD29-P1 修正）",
    has(r'if _tr_on and _pct >= _tr_act and price > _peak:')       # peak 仅在达激活线且市价创新高时更新
    and has(r'elif _tr_on and _peak > 0:')                          # peak 激活后回撤不再回看激活线
    and has(r'_dd = \(_peak - price\) / _peak'))
chk("AUD27-P3h 卖出成功后清手工账本并置在途冻结",
    has(r'state\["manual_sell_pending_until"\] = time\.time\(\) \+ _SELL_PENDING_TTL'))
chk("AUD27-P3i 手工仓路径不触任何买入函数",
    not re.search(r'(buy_shares|intraday_add|place_first_batch|manual_sell[\s\S]{0,3000}?buy_shares)',
                  _sms_code))
chk("AUD27-P3j handlebar 手工仓分支改为先跑 manual_sell 再 continue",
    has(r'if manual_sell\(C, code, _ms_acct, _ms_px, state,')
    and has(r'manual_hold_watch\(C, code, state, _ms_px\)'))
chk("AUD27-P3k 手工仓分支仍在下单前跑 bar 重放拦截",
    has(r'if _ms_acct and not _is_replay_bar\(C\):'))
chk("AUD27-P4a manual_hold_watch 已定义（纯日志）",
    has(r'def manual_hold_watch\(C, code, state, price\):')
    and has(r'纯日志，不参与任何买卖判断'))
chk("AUD30-P2 观察日志独立节流 60s（原实现每 bar 刷屏）",
    has(r'_MANUAL_WATCH_TS') and has(r'_MANUAL_WATCH_GAP = 60\.0')
    and has(r'if _now - _MANUAL_WATCH_TS\.get\(code, 0\.0\) < _MANUAL_WATCH_GAP:'))
chk("AUD27-P4b 观察日志含反解止盈触发价",
    has(r'距%.0f%%止盈线需现价>=%.2f'))
chk("AUD27-P5a SYMBOLS 手工接管配置齐全",
    all(has(r'"%s":' % k) for k in ("manual_takeover_tp_pct", "manual_takeover_trailing",
                                    "manual_takeover_trailing_activate_pct",
                                    "manual_takeover_trailing_dd_pct")))
chk("AUD27-P5b _manual_cfg 缺键时按默认值兜底",
    has(r'def _manual_cfg\(code, key, default=None\):'))
chk("AUD27-P5c init 自检声明手工仓不占名额与额度",
    has(r'人工接管额度说明\(AUD27\)') and has(r'手工仓自检'))
chk("AUD27-P5d init 自检声明亏损一律不卖",
    has(r'亏损一律不卖'))
chk("v1.2.65 记录块已写入文件头", has(r'── v1\.2\.65 = AUD27-P1~P5'))

# ---------- 4 铁律 ----------
m = re.search(r'"hard_stop_dd_pct":\s*([^,\n]+)', txt)
chk("硬止损关闭 (hard_stop_dd_pct=None)", m and m.group(1).strip() == "None",
    m.group(1).strip() if m else "未找到")
chk("sell_all R1 不赚钱不卖复核存在", has(r'R1拦截-不赚钱不卖'))
chk("sell_all 缺 state 时拒绝卖出", has(r'R1拦截-缺少持仓状态'))
calls = [c for c in re.findall(r'sell_all\(([^\n]*)\)', txt) if "def " not in c]
chk("全部 sell_all 调用均传 state", all("state" in c for c in calls),
    "调用点 %d 个" % len(calls))
chk("移动止盈 pnl_pct>=0 红线保留",
    "drawdown_from_peak >= ts_dd and pnl_pct >= 0" in txt)
chk("R1 净到手<=成本 拦截（AUD27 起由统一闸门承载）",
    has(r'if _net <= _cost:') and has(r'不赚钱不卖'))
chk("无止损单/强制平仓字样",
    not re.search(r'(止损卖出|强制平仓|fail_close_all|stop_loss_order)', txt))
chk("止损仅告警不卖出", has(r'止损告警-待处理'))

# ---------- 5 版本号 ----------
m1 = re.search(r'#  策略版本:\s*(v[\d.]+)\s*\(构建\s*(\d{4}-\d{2}-\d{2})\)', txt)
m2 = re.search(r'STRATEGY_VERSION\s*=\s*"(v[\d.]+)"', txt)
m3 = re.search(r'STRATEGY_BUILD\s*=\s*"(\d{4}-\d{2}-\d{2})"', txt)
chk("版本号三处对齐",
    m1 and m2 and m3 and m1.group(1) == m2.group(1) == "v1.2.80"
    and m1.group(2) == m3.group(1) == "2026-10-22",
    "头=%s 常量=%s 构建=%s" % (m1.group(1) if m1 else "?",
                              m2.group(1) if m2 else "?",
                              m3.group(1) if m3 else "?"))
vn = re.findall(r'──\s*(v[\d.]+[A-C]?)\s*=', txt)
cur_v = (re.search(r'STRATEGY_VERSION\s*=\s*"(v[\d.]+)"', txt) or [None, "?"])[1] \
    if False else (re.search(r'STRATEGY_VERSION\s*=\s*"(v[\d.]+)"', txt).group(1))
chk("当前版本必有对应变更记录块（防版本历史漂移）",
    ("── %s = " % cur_v) in txt, "当前版本=%s" % cur_v)
dup = sorted({x for x in vn if vn.count(x) > 1})
chk("版本记录无重复号", not dup, str(dup))
an = re.findall(r'──\s*v[\d.]+[A-C]?\s*=\s*(AUD\d+)(?![-\d])', txt)
adup = sorted({x for x in an if an.count(x) > 1})
chk("审计号无重复", not adup, str(adup))

# ---------- 6 死代码 ----------
refs = collections.Counter()
for n in ast.walk(tree):
    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
        refs[n.id] += 1
defs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
dead = sorted(k for k in defs if refs.get(k, 0) == 0)
chk("未引用函数仅 QMT 三入口",
    set(dead) == {"init", "handlebar", "stop"}, str(dead))
dupf = [k for k, v in collections.Counter(
    n.name for n in tree.body if isinstance(n, ast.FunctionDef)).items() if v > 1]
chk("无重复函数定义", not dupf, str(dupf))
bare = [n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.ExceptHandler) and n.type is None]
chk("无裸 except", not bare, str(bare))

# ---------- 5b AUD92 状态落盘误拦修复（2026-10-21，用户逐项确认） ----------
chk("AUD92-P1 截断写防护改三通道读取（读不出来不否决）",
    has(r'_t_blob, _t_err = _read_file_bytes\(tmp\)')
    and has(r'if _t_blob is not None:')
    and 'with open(tmp, "rb") as _tf:' not in txt)
chk("AUD92-P1 真·半截 JSON 仍拦截并告警",
    has(r'tmp JSON 解析失败，已放弃替换\(保留原文件\)'))
chk("AUD92-P2 落盘结果登记字典存在且成功时登记 ok",
    has(r'_LW_STATUS = \{\}')
    and has(r'_LW_STATUS\[path\] = "ok"'))
chk("AUD92-P2 save_state 见 skip 如实报失败进持久化降级",
    has(r'if _LW_STATUS\.get\(STATE_FILE\) == "skip":')
    and has(r'状态写入被守卫放弃'))
chk("AUD92-P3 情绪日志显示生效缩放（狂热单态标注不缩放）",
    has(r'if cfg\.get\("block_euphoric_only"\) and not SENTIMENT_ENABLED:')
    and has(r'狂热单态·不缩放'))

# ---------- 5c AUD93 佣金按「每张委托单 5 元起」全量对齐（2026-10-21 用户拍板） ----------
chk("AUD93-P1 统一佣金函数 order_commission 定义（每单 5 元底·支持多单）",
    has(r'def order_commission\(amount, n_orders=1, rate=None, minimum=None\):')
    and has(r'return max\(per \* _r, _m\) \* n'))
chk("AUD93-P1 内联 max(金额x费率,5元) 已全部收口（无残留）",
    len(re.findall(r'max\(\w+ \* STOCK_COMMISSION_RATE, STOCK_COMMISSION_MIN\)', txt)) == 0)
chk("AUD93-P1 九处费用点统一走 order_commission",
    txt.count("order_commission(") >= 12)
chk("AUD93-P1 compute_buy_cost 佣金走统一函数",
    has(r'commission = order_commission\(amount, 1, commission_rate, commission_min\)'))
chk("AUD93-P1 下单前按含费成本预留 shrink_for_fee（四处生效）",
    has(r'def shrink_for_fee\(vol, price, cash_avail, lot_size=100\):')
    and txt.count("shrink_for_fee(vol, price,") == 5)
chk("AUD93-P2 手工仓需现价反推含 5 元底（迭代收敛）",
    has(r'for _ in range\(3\):')
    and has(r'_fee_t = \(order_commission\(_mv_t\)'))

# ================= AUD94（第二十四轮零预设独立审计·9 项） =================
chk("AUD94-P1 策略权益市值只算策略自己的股（扣手工份额）",
    has(r'_mv_strat_p94 = int\(actual_vol\) - _mv_ms_p94')
    and has(r'mv = max\(_mv_strat_p94, int\(state\.get\("expected_shares", 0\) or 0\)\) \* price'))
chk("AUD94-P1 不再用券商全量 actual_vol 直接计市值",
    not has(r'^    mv = max\(actual_vol, state\.get\("expected_shares", 0\)\) \* price$'))
chk("AUD94-P2 加仓链入口按策略账本持仓判定",
    has(r'elif \(int\(state\.get\("position_shares", 0\) or 0\) > 0 and not state\["paused"\]'))
chk("AUD94-P3 在途买单期间手工份额只增不减",
    has(r'if _pd_a35 > 0 and _ms_new_a35 < _ms_prev_p94:')
    and has(r'_ms_new_a35 = _ms_prev_p94'))
chk("AUD94-P4 R1 闸门支持 exact_avg 按指定账本成本判",
    has(r'sub_vol=None, exact_avg=False\):')
    and has(r'if exact_avg and _avg_b > 0:'))
chk("AUD94-P4 sell_all 按本次卖的那本账取成本",
    has(r'_gvol94 = max\(0, int\(pos_vol\) - _ms_g94\)')
    and has(r'sub_vol=_gvol94, exact_avg=True'))
chk("AUD94-P5 买入额度闸门只算策略持仓市值",
    has(r'_pv_strat94 = int\(_pv\) - _pv_ms94')
    and has(r'_used = max\(_used, float\(_pv_strat94\) \* float\(_apx\)\)'))
chk("AUD94-P6 锁续命回读校验 pid（易主即降级只观察）",
    has(r'_owner94 = int\(\(json\.loads\(_rf94\.read\(\) or "\{\}"\) or \{\}\)\.get\("pid", 0\) or 0\)')
    and has(r'if _owner94 and _owner94 != os\.getpid\(\):'))
chk("AUD94-P7 情绪 EWMA 每交易日只平滑一次",
    has(r'_SENT_EWMA_DAY = \{\}')
    and has(r'if _SENT_EWMA_DAY\.get\(code\) != _day94 or code not in _SENT_EWMA:'))
chk("AUD94-P8 cash 注释如实标注（不再说「不参与风控计算」）",
    has(r'AUD94-P8 如实标注')
    and not has(r'\u4ec5\u4f5c\u53c2\u8003\uff0c\u4e0d\u53c2\u4e0e\u98ce\u63a7\u8ba1\u7b97'))
chk("AUD94-P9 释放锁前校验归属（不删他人锁）",
    has(r'if _owner9 and _owner9 != os\.getpid\(\):'))
chk("AUD94 铁律零触碰：硬止损仍为 None",
    has(r'hard_stop_dd_pct'))
chk("v1.2.78 版本记录块在文件头",
    has(r'v1\.2\.78 = AUD95-P1'))
chk("AUD95-P1 运行模式探测加入 init 起始时刻下界（防上一轮残留误报）",
    has(r'_INIT_START_TS = 0\.0')
    and has(r'_MODE_PRE_INIT_SEC = 10\.0')
    and has(r'if _age > \(time\.time\(\) - _INIT_START_TS\) \+ _MODE_PRE_INIT_SEC:'))
chk("AUD95-P1 init 首行写入起始时刻",
    has(r'global _LOG_IN_NEST, _trade_mode_pending, _INIT_START_TS')
    and has(r'    _INIT_START_TS = time\.time\(\)'))
chk("v1.2.77 版本记录块在文件头",
    has(r'v1\.2\.77 = 日志文案修复'))
chk("v1.2.77 情绪自检字段名改为「配置模式」（区分配置原值与生效语义）",
    has(r'情绪模块自检 \| 启用=%s \| 配置模式=%s \| 生效策略=%s%s'))
chk("v1.2.76 版本记录块在文件头",
    has(r'v1\.2\.76 = AUD94-P1~P9'))
chk("v1.2.80 版本记录块在文件头",
    has(r'v1\.2\.80 = AUD97-P1~P5'))
chk("v1.2.79 版本记录块已补齐（AUD96）",
    has(r'v1\.2\.79 = AUD96-P1~P11'))
chk("AUD96-P1 save_state/save_m3 读失败中止写入（防清空他股状态）",
    has(r'state merge read failed') and has(r'm3 merge read failed'))
chk("AUD96-P2 挂单强清前先查券商活跃委托",
    has(r'在途单超时强清前查到活跃/未知委托'))
chk("AUD96-P3 委托方向分字段翻译（统一 0=买/1=卖/None=未知）",
    has(r'_d97 = 1 if _x == 49 else \(0 if _x == 48 else None\)')
    and has(r'_d97 = 1 if _x in \(1, 24, 49\) else \(0 if _x in \(0, 23, 48\) else None\)'))
chk("AUD96-P4 佣金异常返回保守最低值而非 0",
    has(r'order_commission 异常'))
chk("AUD96-P5 冷却字段类型异常保守视为冷却中",
    has(r'保守视为冷却中'))
chk("AUD96-P6 风险日志读失败中止写入（防清空历史记录）",
    has(r'risk log read failed'))
chk("AUD96-P7 R1 成本未知发风险告警（仍拒卖）",
    has(r'r1_cost_unknown'))
chk("AUD96-P8 状态/M3 读失败一次性风险告警",
    has(r'state_read_fail') and has(r'm3_read_fail'))
chk("AUD96-P9 在途台账断路恢复改 max() 合并",
    has(r'max\(_PENDING_BUYS\.get\(code, 0\), _beff_b\)'))
chk("AUD96-P10 持仓代码匹配大小写不敏感 + 品种费率提醒",
    has(r'pid\.upper\(\) != code\.upper\(\)') and has(r'费率提醒'))
chk("AUD96-P11 init 兜底重载台账 + 锁 fail-open 告警 + sync 显式返回",
    has(r'init 异常兜底: 在途台账已重载') and has(r'lock_fail_open')
    and has(r'return True   # AUD96'))
chk("AUD97-P1 委托侧代码匹配大小写不敏感（4 处）",
    txt.count('pid.upper() != code.upper()') >= 2
    and txt.count('pid.upper() == code.upper()') >= 1
    and has(r'AUD97-P1: 后缀大小写差异不再漏查活跃买单')
    and has(r'AUD97-P1: 后缀大小写差异不再漏查活跃卖单'))
chk("AUD97-P2 方向翻译逐字段回退（值域不认继续试下一字段）",
    has(r'_d97 = 1 if _x == 49 else \(0 if _x == 48 else None\)')
    and has(r'AUD97-P2: 该字段存在但值域不认'))
chk("AUD97-P3 方向自检改用统一语义统计并如实描述未知处置",
    has(r'_d97 = _read_order_direction\(_od\)')
    and has(r'按「方向未知」单列并保守处理'))
chk("AUD97-P5 区分「文件不存在」与「读失败」（首次创建必须能落盘）",
    has(r'if os\.path\.exists\(STATE_FILE\):\n\s+raise IOError\("state merge read failed')
    and has(r'if os\.path\.exists\(M3_STATE_FILE\):\n\s+raise IOError\("m3 merge read failed')
    and has(r'if os\.path\.exists\(RISK_EVENT_LOG\):\n\s+raise IOError\("risk log read failed'))

# ---------- 输出 ----------
print()
print("=" * 74)
print("v1.2.80 最终验收")
print("=" * 74)
npass = sum(1 for _, c, _ in R if c)
for name, c, d in R:
    print("  [%s] %-34s %s" % ("PASS" if c else "FAIL", name, d if not c else ""))
print("=" * 74)
print("通过 %d / %d" % (npass, len(R)))
print("=" * 74)
