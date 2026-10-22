# -*- coding: utf-8 -*-
"""V2.6.159 第十四轮独立审计 —— 机器扫描 B 批（全自动化检查）"""
import ast, io, re, collections

P = r'E:\桌面\666666\dxgp\_a160_u8.py'
src = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
L = src.split('\n')
tree = ast.parse(src)

def seg(n):
    return ast.get_source_segment(src, n) or ''

out = []
def w(s):
    out.append(s)

# ---------- B1 格式化占位符与参数个数是否匹配 ----------
w('===== B1 百分号格式化：占位符个数 vs 实参个数 =====')
bad = []
for n in ast.walk(tree):
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, (ast.Constant, ast.Name, ast.JoinedStr)) :
        fmt = None
        if isinstance(n.left, ast.Constant) and isinstance(n.left.value, str):
            fmt = n.left.value
        if fmt is None:
            continue
        # 去掉 %% 与转义 %%
        f2 = fmt.replace('%%', '\x00')
        ph = re.findall(r'%(?:[-+ #0]*\d*(?:\.\d+)?[hlL]?)([diouxXeEfFgGcrsa%])', f2)
        nph = len(ph)
        # 实参个数
        if isinstance(n.right, ast.Tuple):
            nargs = len(n.right.elts)
        else:
            nargs = 1
        if nph != nargs:
            bad.append((n.lineno, nph, nargs, fmt[:80]))
w('检查了全部百分号格式化表达式，可疑 %d 处' % len(bad))
for b in sorted(bad)[:25]:
    w('  L%-6d 占位符%d 实参%d | %s' % (b[0], b[1], b[2], b[3]))

# ---------- B2 .format / f-string 的花括号 ----------
w('')
w('===== B2 str.format 占位符与实参 =====')
bad2 = []
for n in ast.walk(tree):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'format':
        base = n.func.value
        fmt = None
        if isinstance(base, ast.Constant) and isinstance(base.value, str):
            fmt = base.value
        if fmt is None:
            continue
        spec = re.findall(r'\{([^}]*)\}', fmt.replace('{{', '\x00').replace('}}', '\x01'))
        if len(spec) != len(n.args):
            bad2.append((n.lineno, len(spec), len(n.args), fmt[:70]))
w('可疑 %d 处' % len(bad2))
for b in sorted(bad2)[:15]:
    w('  L%-6d 洞%d 实参%d | %s' % (b[0], b[1], b[2], b[3]))

# ---------- B3 return 之后的死语句 ----------
w('')
w('===== B3 return 之后仍有语句（真死代码） =====')
dead = []
for fn in ast.walk(tree):
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    for blk in ast.walk(fn):
        body = getattr(blk, 'body', None)
        if not isinstance(body, list):
            continue
        for i, st in enumerate(body[:-1]):
            if isinstance(st, ast.Return):
                nxt = body[i+1]
                # 下一句只有注释/文档字符串不成立 —— AST 里 pass/Expr(常量) 才算语句
                if not (isinstance(nxt, ast.Pass)):
                    dead.append((fn.name, nxt.lineno, type(nxt).__name__, L[nxt.lineno-1].strip()[:70]))
w('命中 %d 处' % len(dead))
for d in sorted(set(dead))[:25]:
    w('  %s L%-6d %s | %s' % d)

# ---------- B4 裸除法：分母不是字面量且不在 protected 内 ----------
w('')
w('===== B4 除法：分母非常量且无零保护 =====')
divs = []
for n in ast.walk(tree):
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
        d = n.right
        simple = isinstance(d, ast.Constant) and not isinstance(d.value, (str, bytes))
        # 检查函数体内是否有对该分母的 if 判断（粗筛）
        divs.append((n.lineno, seg(n)[:60], simple))
w('全部除法 %d 处，其中分母是字面量的 %d 处' % (len(divs), sum(1 for d in divs if d[2])))

# ---------- B5 价格/数量的 falsy 误判：if not X: continue 之类 ----------
w('')
w('===== B5 关键变量被当作布尔量判断 =====')
susp = []
for n in ast.walk(tree):
    if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp) and isinstance(n.test.op, ast.Not):
        e = n.test.operand
        if isinstance(e, ast.Name) and re.search(r'price|vol|amt|amount|qty|shares|fee|cost|val', e.id, re.I):
            susp.append((n.lineno, e.id, L[n.lineno-1].strip()[:90]))
w('命中 %d 处' % len(susp))
for s in sorted(susp)[:30]:
    w('  L%-6d not %s | %s' % s)

# ---------- B6 浮点相等比较（金额/价格/费用） ----------
w('')
w('===== B6 浮点相等比较 =====')
eq = []
for n in ast.walk(tree):
    if isinstance(n, ast.Compare):
        for op, cmp in zip(n.ops, n.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)):
                a, b = n.left, cmp
                fa = isinstance(a, ast.Name) and re.search(r'fee|price|cost|val|amt|amount|pnl|ratio|eq|avg', a.id, re.I)
                fb = isinstance(b, ast.Name) and re.search(r'fee|price|cost|val|amt|amount|pnl|ratio|eq|avg', b.id, re.I)
                if fa or fb:
                    eq.append((n.lineno, seg(n)[:80]))
w('命中 %d 处' % len(eq))
for e in sorted(eq)[:25]:
    w('  L%-6d %s' % e)

# ---------- B7 切片边界 ----------
w('')
w('===== B7 切片 [1:] / [:-1] / [-N:] 使用点 =====')
sl = [(i+1, l.strip()[:95]) for i, l in enumerate(L) if re.search(r'\[\s*1\s*:\s*\]|\[\s*:-1\s*\]|\[\s*-\d+\s*:\s*\]', l) and 'def ' not in l]
w('共 %d 处' % len(sl))
for s in sl[:30]:
    w('  L%-6d %s' % s)

# ---------- B8 索引 [0] / [-1] 无长度检查 ----------
w('')
w('===== B8 rows[0] / rows[-1] 出现密度 =====')
i0 = [(i+1, l.strip()[:95]) for i, l in enumerate(L) if re.search(r'\b(rows|_r|_d|_x|_lst|_arr|_list)\s*\[\s*(0|-1)\s*\]', l)]
w('共 %d 处（不逐一判断，交由人工核）' % len(i0))
for s in i0[:25]:
    w('  L%-6d %s' % s)

# ---------- B9 except 只记日志后返回"看起来正常"的值 ----------
w('')
w('===== B9 except 吞异常后返回的"正常值" =====')
sus = []
for fn in ast.walk(tree):
    if not isinstance(fn, ast.FunctionDef):
        continue
    for h in ast.walk(fn):
        if isinstance(h, ast.ExceptHandler):
            body = h.body
            if not body or isinstance(body[0], (ast.Raise,)):
                continue
            txt = '\n'.join(L[i-1].strip() for i in range(h.lineno, min(len(L), h.lineno+12)))
            rets = [x for x in ast.walk(h) if isinstance(x, ast.Return)]
            for r in rets:
                v = seg(r.value) if r.value else 'None(裸返回)'
                if re.search(r'^(\'|\")?\s*0(\.0*)?\s*$|^\{\}$|^\[\]$|^None$|^True$|^False$|^\'\'$|^\{\s*\}$', v.strip()):
                    sus.append((fn.name, r.lineno, v[:50]))
w('可疑 %d 处' % len(sus))
seen = set()
for s in sorted(sus):
    k = (s[0], s[1])
    if k in seen: continue
    seen.add(k)
    w('  %s L%-6d 返回 %s' % s)

io.open(r'E:\桌面\666666\dxgp\_a160_sweepB.txt', 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
print('\n'.join(out[:6]))
print('...')
print('总行数 =', len(out))
print('已写入 _a160_sweepB.txt')