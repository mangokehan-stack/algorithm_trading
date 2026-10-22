# -*- coding: utf-8 -*-
"""P1-3 残留扫描: 找出所有未包裹 _api() 的 QMT C 接口调用(含局部别名 C. 与绑定方法别名)。
只读不改。字符串字面量/注释/文档串内的提及不算。
"""
import io, re

PATH = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
with io.open(PATH, "r", encoding="gbk", newline="") as f:
    text = f.read()
lines = text.split("\r\n")

API_NAMES = [
    "get_full_tick", "get_market_data_ex", "get_instrument_detail",
    "get_sector_list", "get_stock_list_in_sector", "get_trading_dates",
    "download_history_data", "get_trade_detail_data", "passorder",
    "can_cancel_order", "cancel", "subscribe_quote", "unsubscribe_quote",
    "get_raw_financial_data", "get_financial_data",
]
ALIAS_VARS = ["_ctx_sub", "_ctx_tick", "_ctx_1m", "_global_sub"]

# ---- 行分类: 注释/文档串 ----
in_doc = False
code_line = []
for ln in lines:
    s = ln.strip()
    if in_doc:
        code_line.append(False)
    elif s.startswith("#"):
        code_line.append(False)
    else:
        code_line.append(True)
    if ln.count('"""') % 2 == 1:
        in_doc = not in_doc

def string_spans(s):
    """返回该行内字符串字面量的 (start,end) 区间列表(不含三引号跨行, 已由 in_doc 处理)"""
    spans = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "#":
            break
        if c == '"' or c == "'":
            q = c
            j = i + 1
            while j < n:
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == q:
                    break
                j += 1
            spans.append((i, min(j, n - 1)))
            i = j + 1
            continue
        i += 1
    return spans

def in_string(pos, spans):
    return any(a <= pos <= b for (a, b) in spans)

unwrapped = []
wrapped_cnt = 0
skipped_other = []
for li, ln in enumerate(lines):
    if not code_line[li]:
        continue
    spans = string_spans(ln)
    # 1) 直接 API 名调用(允许 _api( 前缀与 G.C./C. 限定前缀)
    for name in API_NAMES:
        pat = r"(_api\()?((?:[A-Za-z_][A-Za-z_0-9]*\.)*)" + re.escape(name) + r"\s*\("
        for m in re.finditer(pat, ln):
            if in_string(m.start(), spans):
                continue
            qual = m.group(2) or ""
            if m.group(1):
                wrapped_cnt += 1
            elif qual in ("", "G.C.", "C."):
                unwrapped.append((li + 1, qual + name, ln.strip()[:90]))
            else:
                skipped_other.append((li + 1, qual + name, ln.strip()[:70]))
    # 2) 绑定方法别名调用
    for v in ALIAS_VARS:
        for m in re.finditer(r"(?<![A-Za-z_0-9.])" + re.escape(v) + r"\s*\(", ln):
            if in_string(m.start(), spans):
                continue
            pre = ln[:m.start()]
            if re.search(r"_api\(\s*$", pre):
                wrapped_cnt += 1
            else:
                unwrapped.append((li + 1, v, ln.strip()[:90]))

print("wrapped(recognized)=%d" % wrapped_cnt)
print("UNWRAPPED=%d" % len(unwrapped))
for (lno, name, sample) in unwrapped:
    print("  L%-6d %-28s %s" % (lno, name, sample))
if skipped_other:
    print("SKIPPED(other-qualifier, 非QMT-C调用)=%d" % len(skipped_other))
    for (lno, name, sample) in skipped_other:
        print("  L%-6d %-40s %s" % (lno, name, sample))
