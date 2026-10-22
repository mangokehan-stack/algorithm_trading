# -*- coding: utf-8 -*-
"""V2.6.149 零预设静态审计扫描(程序化证据)"""
import ast, re, sys, io, os

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
t = raw.decode('gbk')
src = t.replace('\r\n', '\n')
lines = src.split('\n')
tree = ast.parse(src)
out = []
def w(s=''):
    out.append(s)

# ---------- 1 版本号一致性 ----------
w('=== 1 版本号一致性 ===')
ver_const = re.search(r"^VERSION = '(V[\d.]+)'", src, re.M).group(1)
sent_ver = re.search(r"^SENT_VERSION = '(.*?)'", src, re.M).group(1)
heads = re.findall(r'^# 版本号: (V[\d.a-z]+)', src, re.M)
w('VERSION 常量 = %s' % ver_const)
w('SENT_VERSION = %s' % sent_ver)
w('文件头版本行数 = %d, 首行 = %s' % (len(heads), heads[0] if heads else 'NA'))
w('首行 == VERSION ? %s' % (heads[0] == ver_const if heads else False))
bad = [h for h in heads if h != ver_const and not re.match(r'^V2\.6\.\d+[a-z]?$', h)]
w('文件头异常版本号: %s' % (bad or '无'))
w()

# ---------- 2 死代码: return/raise/continue/break 之后仍有语句 ----------
w('=== 2 死代码扫描 (同一块内 return 之后的兄弟语句) ===')
dead = []
def scan_block(body, owner):
    hit_term = False
    for st in body:
        if hit_term:
            dead.append((owner, st.lineno, lines[st.lineno - 1].strip()[:90]))
        if isinstance(st, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
            hit_term = True
    for st in body:
        for field in ('body', 'orelse', 'finalbody'):
            sub = getattr(st, field, None)
            if isinstance(sub, list):
                scan_block(sub, owner)
        # if/while/for 的 body 已在上面覆盖; Try 的 handlers
        for h in getattr(st, 'handlers', []) or []:
            scan_block(h.body, owner)
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        scan_block(node.body, node.name)
w('死代码条数 = %d' % len(dead))
for o, ln, s in dead[:40]:
    w('  %s() L%d  %s' % (o, ln, s))
w()

# ---------- 3 裸 except / except: pass ----------
w('=== 3 异常处理 ===')
bare = 0
pass_only = 0
broad = 0
for n in ast.walk(tree):
    if isinstance(n, ast.ExceptHandler):
        if n.type is None:
            bare += 1
            if len(n.body) == 1 and isinstance(n.body[0], ast.Pass):
                pass_only += 1
        elif isinstance(n.type, ast.Name) and n.type.id == 'Exception':
            broad += 1
w('裸 except: %d (其中只有 pass: %d)' % (bare, pass_only))
w('except Exception: %d' % broad)
w()

# ---------- 4 铁律: 止损相关 ----------
w('=== 4 铁律检查 ===')
for kw in ('stop_order', 'stop_loss_order', 'algo_order', 'order_target'):
    w('  %-18s 出现 %d 次' % (kw, len(re.findall(kw, src))))
w('  NEVER_STOP_LOSS 赋值: %s' % re.findall(r'^NEVER_STOP_LOSS\s*=\s*(\S+)', src, re.M))
w()

# ---------- 5 下单调用 ----------
w('=== 5 下单调用 (passorder 实际调用点) ===')
for i, l in enumerate(lines, 1):
    if '_api(passorder' in l:
        m = re.search(r'_api\(passorder,\s*(\d+)', l)
        w('  L%-6d opType=%s  %s' % (i, m.group(1) if m else '?', l.strip()[:110]))
w()

# ---------- 6 金额上限守卫覆盖 ----------
w('=== 6 资金/持仓上限守卫 ===')
for kw in ('used_capital()', 'abs_cap_left(', 'can_open_new(', 'pos_limit()'):
    cnt = len(re.findall(re.escape(kw), src))
    w('  %-20s 出现 %d 次' % (kw, cnt))
w()

# ---------- 7 情绪模块状态键 ----------
w('=== 7 情绪模块关键函数存在性 ===')
for fn in ('_sent_fetch_from_cache', '_sent_acc_load', '_sent_acc_dump', '_sent_apply_rows',
           '_sent_use_last_good', '_sent_compute', '_sent_fetch_sync', 'sent_daily_refresh',
           '_sent_reset_ready', 'sent_gate_skip', 'sent_size_mult', 'sent_param'):
    w('  %-26s %s' % (fn, '有' if ('def %s' % fn) in src else '★缺失★'))
w()

# ---------- 8 排雷清单 / ST 清单 ----------
w('=== 8 排雷/ST/黑名单 ===')
for fn in ('risk_excluded', '_load_risk_exclude', 'load_st_hist', 'is_st_name',
           'excluded', 'load_blacklist', '_load_blacklist'):
    w('  %-22s %s' % (fn, '有' if ('def %s' % fn) in src else '缺失'))
w()

# ---------- 9 参数指纹机制 ----------
w('=== 9 参数指纹 ===')
deny = re.search(r'_FP_DENY = \{(.*?)\n\}', src, re.S)
w('  _FP_DENY 键数 = %d' % (len(re.findall(r"'([A-Z_]+)'", deny.group(1))) if deny else -1))
w('  VERSION 在 DENY 内: %s' % ("'VERSION'" in (deny.group(1) if deny else '')))
w('  HISTORY_BARS 在 DENY 内: %s' % ("'HISTORY_BARS'" in (deny.group(1) if deny else '')))
w()

# ---------- 10 可能的数据泄露: 使用当日数据 ----------
w('=== 10 未来函数排查 (r[date] < today 之类守卫计数) ===')
pat = {
    "date'] < _t": len(re.findall(r"date'\] < _t", src)),
    "_today and isinstance": len(re.findall(r'_today and isinstance', src)),
    ">= _today": len(re.findall(r'>= _today', src)),
    ">= today": len(re.findall(r'>= today', src)),
}
for k, v in pat.items():
    w('  %-24s %d 处' % (k, v))
w()

# ---------- 11 大函数清单(复杂度过高嫌疑) ----------
w('=== 11 超长函数 (>250 行) ===')
for n in tree.body:
    if isinstance(n, ast.FunctionDef):
        span = (n.end_lineno or n.lineno) - n.lineno + 1
        if span > 250:
            w('  L%-6d %-28s %d 行' % (n.lineno, n.name, span))
w()

# ---------- 12 禁止项: xtquant / 外部依赖 ----------
w('=== 12 环境合规 (QMT 内置 Python) ===')
for kw in ('xtquant', 'xtdata', 'import requests', 'import numpy', 'import pandas',
           'import urllib', 'pip ', 'subprocess'):
    w('  %-18s %d 次' % (kw, len(re.findall(re.escape(kw), src))))
w()

open(r'E:\桌面\666666\dxgp\_audit_static.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('written %d lines' % len(out))
