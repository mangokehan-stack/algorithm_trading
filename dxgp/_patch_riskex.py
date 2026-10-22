# -*- coding: utf-8 -*-
"""排雷功能策略侧补丁：常量 + 全局 + 三函数 + 三处拦截挂点。"""
import sys

p = 'zt_shrink_strategy_gbk.py'
raw = open(p, 'rb').read()
text = raw.decode('gbk', errors='strict')
lines = text.split('\r\n')
base = len(lines)


def lineno(sub, start=1, end=None):
    end = end or len(lines)
    hits = [i + 1 for i, ln in enumerate(lines) if sub in ln and start <= i + 1 <= end]
    if len(hits) != 1:
        print('ANCHOR FAIL %r -> %s' % (sub, hits))
        sys.exit(2)
    return hits[0]


edits = []


def E(a, b, new, note):
    edits.append((a, b, new, note))


# ---------- 1) 常量 ----------
a = lineno("ST_HIST_FILE = 'zt_shrink_st_hist.json'")
E(a + 1, a,
  ["",
   "RISK_EXCLUDE_ON = True                                # V2.6.83新增: 提前排雷清单开关(True=命中即拒绝买入)",
   "                                                      #   只拦\"新增买入/加仓\", 绝不拦卖出与持仓管理",
   "RISK_EXCLUDE_FILE = 'zt_shrink_risk_exclude.json'      # 排雷清单(仅纯文件名, 与脚本同目录; 由 download_risk_exclude.py 生成)",
   "RISK_EXCLUDE_MAX_AGE_DAYS = 10                         # 清单最大可用天数(超过则每次启动强提醒; 过期清单仍然拦截=偏紧)"],
  'risk exclude const')

# ---------- 2) 全局状态 ----------
a = lineno("G.st_hist_date = ''            # 历史ST清单按日刷新标记")
E(a + 1, a,
  ["G.risk_ex = {}                  # V2.6.83: 提前排雷清单 {代码: {'tags': [...], 'reasons': [...]}}",
   "G.risk_ex_date = ''             # V2.6.83: 排雷清单装载日(每日一次)"],
  'risk exclude globals')

# ---------- 3) 三函数 ----------
a = lineno('def get_recent_net_profit(s):')
new_fns = [
    "def risk_exclude_path():",
    "    \"\"\"V2.6.83: 排雷清单路径(带账号后缀) —— 与状态文件同目录, 仅允许纯文件名, 禁止穿越\"\"\"",
    "    stem, ext = _split_name(RISK_EXCLUDE_FILE)",
    "    return _join_base(stem + _account_suffix() + ext)",
    "",
    "def _risk_exclude_candidates():",
    "    \"\"\"优先账号后缀文件, 再回退无后缀主文件(工具默认输出名)\"\"\"",
    "    p1 = risk_exclude_path()",
    "    p2 = _join_base(RISK_EXCLUDE_FILE)",
    "    return [p1] if p1 == p2 else [p1, p2]",
    "",
    "def load_risk_exclude():",
    "    \"\"\"V2.6.83新增: 每日装载一次提前排雷清单(由 download_risk_exclude.py 生成)。",
    "    返回 {代码: {'tags': [...], 'reasons': [...]}}。",
    "    容错口径(用户定稿\"误报偏紧\"): 文件缺失=不阻断(此时仍有 ST/亏损/解禁等实时闸门),",
    "    但必须留痕; 结构损坏或清单过期=仍然使用已解析部分并每日强提醒一次(宁可多排, 不可漏排)。\"\"\"",
    "    if not RISK_EXCLUDE_ON:",
    "        return {}",
    "    if G.risk_ex_date == G.today:",
    "        return G.risk_ex if isinstance(G.risk_ex, dict) else {}",
    "    data, used, err = {}, '', ''",
    "    for cand in _risk_exclude_candidates():",
    "        try:",
    "            if not os.path.exists(cand):",
    "                continue",
    "            with open(cand, 'r', encoding='utf-8') as f:",
    "                j = json.load(f)",
    "            if not isinstance(j, dict) or not isinstance(j.get('stocks'), dict):",
    "                err = '结构不符(缺 stocks 字典): %s' % os.path.basename(cand)",
    "                continue",
    "            for _k, _v in j['stocks'].items():",
    "                if not isinstance(_v, dict):",
    "                    continue",
    "                _rs = _v.get('reasons')",
    "                _tg = _v.get('tags')",
    "                data[str(_k)] = {",
    "                    'reasons': [str(x) for x in _rs][:6] if isinstance(_rs, list) else [],",
    "                    'tags': [str(x) for x in _tg][:6] if isinstance(_tg, list) else [],",
    "                }",
    "            used = cand",
    "            _asof = str(j.get('asof') or '')",
    "            if RISK_EXCLUDE_MAX_AGE_DAYS > 0 and len(_asof) == 8:",
    "                try:",
    "                    _d = datetime.datetime.strptime(_asof, '%Y%m%d').date()",
    "                    _age = (datetime.date.today() - _d).days",
    "                    if _age > RISK_EXCLUDE_MAX_AGE_DAYS:",
    "                        err = '清单已过期%d天(asof=%s)' % (_age, _asof)",
    "                except Exception:",
    "                    pass",
    "            break",
    "        except Exception as e:",
    "            err = '%s(%r)' % (os.path.basename(cand), e)",
    "            continue",
    "    G.risk_ex = data",
    "    G.risk_ex_date = G.today",
    "    if data:",
    "        _cnt = {}",
    "        for _v in data.values():",
    "            for _t in _v.get('tags', []):",
    "                _cnt[_t] = _cnt.get(_t, 0) + 1",
    "        log('[排雷] 已装载提前排雷清单%d只(%s) 文件=%s'",
    "            % (len(data), ', '.join('%s=%d' % (k, v) for k, v in sorted(_cnt.items())) or '-',",
    "               os.path.basename(used)))",
    "        if err:",
    "            log('[排雷][告警] %s —— 仍按现有清单拦截(偏紧), 请重新运行 download_risk_exclude.py' % err)",
    "            try:",
    "                pnl_alert('[排雷][告警] %s, 请重新运行 download_risk_exclude.py 更新清单' % err)",
    "            except Exception:",
    "                pass",
    "    elif err:",
    "        log('[排雷][告警] 排雷清单不可用: %s —— 仍依赖实时闸门(ST/财务亏损/仙股/退潮等)' % err)",
    "        try:",
    "            pnl_alert('[排雷][告警] 排雷清单不可用: %s' % err)",
    "        except Exception:",
    "            pass",
    "    else:",
    "        log('[排雷] 未发现排雷清单文件(可选功能), 如需启用请运行 download_risk_exclude.py;'",
    "            ' 当前仅依赖实时闸门(ST/财务亏损/仙股/退潮等)')",
    "    return data",
    "",
    "def risk_excluded(s):",
    "    \"\"\"V2.6.83: 查询排雷清单。命中返回原因文本, 未命中返回 ''。",
    "    异常一律按\"未命中\"处理(排雷是增强项, 不能因清单损坏而误伤全部交易);",
    "    真正的实时风险闸门(risk_blocked/excluded)不受本函数影响。\"\"\"",
    "    if not RISK_EXCLUDE_ON:",
    "        return ''",
    "    try:",
    "        d = load_risk_exclude()",
    "        it = d.get(str(s)) if isinstance(d, dict) else None",
    "        if not isinstance(it, dict):",
    "            return ''",
    "        _rs = it.get('reasons') or []",
    "        if _rs:",
    "            return '排雷命中: ' + '/'.join(str(x) for x in _rs[:3])",
    "        _tg = it.get('tags') or []",
    "        if _tg:",
    "            return '排雷命中: ' + ','.join(str(x) for x in _tg[:3])",
    "        return '排雷命中(清单内)'",
    "    except Exception as e:",
    "        log('[排雷][告警] 清单查询异常(按未命中处理): %r' % (e,))",
    "        return ''",
    "",
    "",
]
E(a, a - 1, new_fns, 'risk exclude functions')

# ---------- 4) excluded() 挂点 ----------
a = lineno('def can_trade():')
# 在 excluded 的 return '' 之前插入（找 can_trade 之前最近的 return ''）
i = a - 1
while i > 0 and lines[i].strip() != "return ''":
    i -= 1
if lines[i].strip() != "return ''":
    print('excluded return anchor not found')
    sys.exit(2)
E(i + 1, i,
  ["    # V2.6.83: 提前排雷清单(解禁/减持/业绩预亏/立案处罚/ST) —— 命中直接不入选",
   "    _rx = risk_excluded(stock)",
   "    if _rx:",
   "        return _rx"],
  'excluded hook')

# ---------- 5) pyramid_add 挂点 ----------
a = lineno("scope_refuse(s, '买入(分批加仓)')")
E(a + 2, a + 1,
  ["    # V2.6.83: 发单前复核排雷清单(选股后清单可能已更新; 只拦新增买入, 不影响卖出)",
   "    _rx = risk_excluded(s)",
   "    if _rx:",
   "        log(disp(s), '分批加仓拒绝: %s(发单前复核)' % _rx)",
   "        return 0.0"],
  'pyramid hook')

# ---------- 6) buy_stock 挂点 ----------
a = lineno("scope_refuse(s, '买入')")
E(a + 2, a + 1,
  ["    # V2.6.83: 发单前复核排雷清单(与选股层形成双重拦截; 只拦新增买入, 卖出/持仓管理不受影响)",
   "    _rx = risk_excluded(s)",
   "    if _rx:",
   "        log(disp(s), '买入拒绝: %s(发单前复核)' % _rx)",
   "        return None"],
  'buy_stock hook')

# ================= 应用 =================
for a, b, new, note in sorted(edits, key=lambda x: -x[0]):
    lines[a - 1:b] = new

out = '\r\n'.join(lines)
if out.count('\r\n') != len(lines) - 1:
    print('ABORT: CRLF mismatch')
    sys.exit(3)
compile(out, p, 'exec')
open(p, 'wb').write(out.encode('gbk', errors='strict'))
print('OK: %d edits, lines %d -> %d (delta %+d)' % (len(edits), base, len(lines), len(lines) - base))
