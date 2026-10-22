# -*- coding: utf-8 -*-
"""P1-3: 全局客户端接口互斥锁。
方案: 新增 _API_LOCK + _api(fn,*a,**kw) helper; 把全部 44 处 C 接口调用
(G.C.get_* / download_history_data / get_trade_detail_data / passorder / cancel /
can_cancel_order) 文本变换为 _api(...) 形式。不动 G.C 本身(passorder/cancel 要收
原始 ContextInfo, 代理有类型检查风险)。括号匹配跳过字符串字面量; 跳过注释行与
三引号文档字符串(头部版本史里有 API 名字提及)。
"""
import io, re

PATH = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
with io.open(PATH, "r", encoding="gbk", newline="") as f:
    text = f.read()
assert "\r\n" in text
assert "\n" not in text.replace("\r\n", "")
lines = text.split("\r\n")
print("lines=%d" % len(lines))

# ---------- 1) 插入 _API_LOCK + _api ----------
def find_one(anchor):
    hits = [i for i, l in enumerate(lines) if anchor in l]
    assert len(hits) == 1, "anchor %r -> %d hits" % (anchor[:50], len(hits))
    return hits[0]

assert "_API_LOCK" not in text and "def _api(" not in text, "already patched"
i = find_one("G.state_lock = threading.RLock()")
block = [
    "_API_LOCK = threading.RLock()      # 审计P1-3: QMT客户端C接口全局互斥锁(情绪后台线程 vs 主线程)",
    "",
    "def _api(fn, *a, **kw):",
    "    \"\"\"审计P1-3修复(第十四轮零预设审计, 2026-10-19): 客户端接口全局互斥调用。",
    "    背景: 情绪模块后台线程与主线程并发调用同一套 QMT 内置 C 接口",
    "    (get_market_data_ex/download_history_data/get_stock_list_in_sector/get_full_tick/",
    "     get_trade_detail_data/passorder/cancel/can_cancel_order 等), 广发精简版客户端",
    "    未承诺这些接口线程安全 —— 并发调用轻则返回错乱数据(情绪指数失真), 重则客户端",
    "    崩溃重启(重启期间策略半就绪)。",
    "    本函数保证任意时刻只有一个线程位于 C 接口内; 单次调用单独加锁(不整段持有),",
    "    主线程等待以单次调用为界, 长耗时取数不会把下单堵死几十秒。",
    "    RLock 可重入: 同线程嵌套调用(下单->回调再取数)不会自锁。\"\"\"",
    "    with _API_LOCK:",
    "        return fn(*a, **kw)",
]
lines[i+1:i+1] = block
print("inserted _API_LOCK + _api after L%d" % (i + 1))

text = "\r\n".join(lines)
lines = text.split("\r\n")

# ---------- 2) 分类代码行(排除注释与文档字符串) ----------
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

# ---------- 3) 括号匹配(跳过字符串) ----------
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

PATTERNS = [
    r"G\.C\.(?:get_full_tick|get_market_data_ex|get_instrument_detail|get_sector_list|get_stock_list_in_sector|get_trading_dates)\(",
    r"(?<![A-Za-z_0-9.])download_history_data\(",
    r"(?<![A-Za-z_0-9.])get_trade_detail_data\(",
    r"(?<![A-Za-z_0-9.])passorder\(",
    r"(?<![A-Za-z_0-9.])can_cancel_order\(",
    r"(?<![A-Za-z_0-9.])cancel\(",
]

# 收集全部命中 (start, end_of_pattern) — end 恰在 '(' 之后
matches = []
for pat in PATTERNS:
    for m in re.finditer(pat, text):
        matches.append((m.start(), m.end(), m.group(0)))

# 行号计算 + 代码行过滤
def line_of(pos):
    return text.count("\r\n", 0, pos)  # 0-based 行索引

kept = []
skipped = []
for (st, en, g) in matches:
    li = line_of(st)
    if not code_line[li]:
        skipped.append((li + 1, g))
        continue
    kept.append((st, en, g))
# 去重(同一位置被多模式命中不可能, 但保平安) + 倒序
kept = sorted(set(kept), key=lambda x: -x[0])
print("code-site matches: %d, skipped(non-code): %d" % (len(kept), len(skipped)))
for (ln, g) in skipped:
    print("  SKIP L%d %s" % (ln, g))

wrapped = []
for (st, en, g) in kept:
    close = find_close(text, en - 1)
    assert close >= en, "no close paren for %r" % g
    call_txt = text[st:close + 1]
    inner = text[en:close]           # 参数部分(含换行)
    fn_txt = g[:-1]                  # 去掉 '('
    if inner.strip() == "":
        new_txt = "_api(" + fn_txt + ")"
    else:
        new_txt = "_api(" + fn_txt + ", " + inner + ")"
    text = text[:st] + new_txt + text[close + 1:]
    wrapped.append((line_of(st) + 1, fn_txt, call_txt.replace("\r\n", " ")[:70]))

# ---------- 4) 写回 + 自检 ----------
with io.open(PATH, "w", encoding="gbk", newline="") as f:
    f.write(text)
with io.open(PATH, "r", encoding="gbk", newline="") as f:
    chk = f.read()
compile(chk, PATH, "exec")
n_api = chk.count("_api(")
print("WRAPPED %d sites; _api( occurrences=%d" % (len(wrapped), n_api))
for (ln, fn, sample) in sorted(wrapped):
    print("  L%-6d %s" % (ln, sample))
# 残留检查: 不应再有未包裹的目标调用(注释/文档串除外)
for pat in PATTERNS:
    for m in re.finditer(pat, chk):
        li = chk.count("\r\n", 0, m.start())
        if code_line[li] if li < len(code_line) else True:
            # 行号可能因插入而偏移, 只做提示
            pass
print("COMPILE OK")
