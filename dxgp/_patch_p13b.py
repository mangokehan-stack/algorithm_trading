# -*- coding: utf-8 -*-
"""P1-3 补丁二: 包裹 _patch_p13.py 漏掉的 9 处 C 接口调用。
漏掉原因: 原 PATTERNS 只认 G.C. 前缀, 不认局部别名 C. 与绑定方法别名 _ctx_sub。
本脚本字符串/注释/文档串感知(复用 _scan_api_wrap.py 的分类逻辑), 括号匹配跳过字符串。
多行调用自动把续行缩进 +6(保持对齐; Python 不强制, 仅整洁)。
"""
import io, re

PATH = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
with io.open(PATH, "r", encoding="gbk", newline="") as f:
    text = f.read()
assert "\r\n" in text
assert "\n" not in text.replace("\r\n", "")
lines = text.split("\r\n")
print("lines=%d" % len(lines))

# ---------- 行分类(注释/文档串) ----------
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

# ---------- 括号匹配(跳过字符串) ----------
def find_close(s, open_idx):
    depth = 0
    i = open_idx
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"' or c == "'":
            q = c
            i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1

# ---------- 待包裹模式: 局部别名 C.<api>( 与 绑定方法别名 ----------
C_APIS = ["get_full_tick", "get_market_data_ex", "get_instrument_detail",
          "get_sector_list", "get_stock_list_in_sector", "get_trading_dates",
          "get_raw_financial_data", "get_financial_data",
          "download_history_data", "get_trade_detail_data"]
ALIAS_VARS = ["_ctx_sub", "_ctx_tick", "_ctx_1m", "_global_sub"]

def line_of(pos):
    return text.count("\r\n", 0, pos)

matches = []   # (start, end_after_open_paren, fn_text)
skipped = []
for name in C_APIS:
    pat = r"(?<![A-Za-z_0-9._])C\." + re.escape(name) + r"\s*\("
    for m in re.finditer(pat, text):
        li = line_of(m.start())
        if not code_line[li]:
            skipped.append((li + 1, "C." + name, "comment/doc"))
            continue
        # 行内字符串检查
        ln = lines[li]
        col = m.start() - (text.rfind("\r\n", 0, m.start()) + 2)
        if in_string(col, string_spans(ln)):
            skipped.append((li + 1, "C." + name, ln.strip()[:60]))
            continue
        matches.append((m.start(), m.end(), "C." + name))
for v in ALIAS_VARS:
    pat = r"(?<![A-Za-z_0-9._])" + re.escape(v) + r"\s*\("
    for m in re.finditer(pat, text):
        li = line_of(m.start())
        if not code_line[li]:
            skipped.append((li + 1, v, "comment/doc"))
            continue
        ln = lines[li]
        col = m.start() - (text.rfind("\r\n", 0, m.start()) + 2)
        if in_string(col, string_spans(ln)):
            skipped.append((li + 1, v, ln.strip()[:60]))
            continue
        # 已被 _api( 包裹的跳过
        pre = text[max(0, m.start() - 8):m.start()]
        if "_api(" in pre:
            skipped.append((li + 1, v, "already wrapped"))
            continue
        matches.append((m.start(), m.end(), v))

for (lno, fn, why) in sorted(skipped):
    print("  SKIP L%d %s (%s)" % (lno, fn, why))
print("target matches: %d, skipped: %d" % (len(matches), len(skipped)))
assert len(matches) == 9, "expect 9, got %d" % len(matches)

# 倒序处理(从后往前, 不影响前面的位置)
matches.sort(key=lambda x: -x[0])
wrapped = []
for (st, en, fn) in matches:
    close = find_close(text, en - 1)
    assert close >= en, "no close paren for %s" % fn
    call_txt = text[st:close + 1]
    inner = text[en:close]
    if inner.strip() == "":
        new_txt = "_api(" + fn + ")"
    else:
        new_txt = "_api(" + fn + ", " + inner + ")"
    # 多行调用: 续行缩进 +6
    if "\r\n" in new_txt:
        parts = new_txt.split("\r\n")
        parts = [parts[0]] + ["      " + p if p.strip() else p for p in parts[1:]]
        new_txt = "\r\n".join(parts)
    text = text[:st] + new_txt + text[close + 1:]
    wrapped.append((line_of(st) + 1, fn, call_txt.replace("\r\n", " ")[:70]))

# ---------- 写回 + 自检 ----------
with io.open(PATH, "w", encoding="gbk", newline="") as f:
    f.write(text)
with io.open(PATH, "r", encoding="gbk", newline="") as f:
    chk = f.read()
compile(chk, PATH, "exec")
n_api = chk.count("_api(")
print("WRAPPED %d sites; _api( occurrences=%d" % (len(wrapped), n_api))
for (ln, fn, sample) in sorted(wrapped):
    print("  L%-6d %s" % (ln, sample))
print("COMPILE OK")
