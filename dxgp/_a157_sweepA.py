# -*- coding: utf-8 -*-
"""全新审计 A 批：结构性危险模式静态扫描"""
import ast, io, collections, re

P = r'E:\桌面\666666\dxgp\_a157_u8.py'
raw = io.open(P, encoding='utf-8', newline='').read()
src = raw.replace('\r\n', '\n')
L = src.split('\n')
tree = ast.parse(src)
out = []
def w(s=''):
    out.append(s)
def seg(n):
    try:
        return (ast.get_source_segment(src, n) or '').replace('\n', ' ')[:150]
    except Exception:
        return '?'

w('=' * 78)
w('A1. 同名函数重复定义（后定义静默覆盖前定义）')
w('=' * 78)
names = collections.defaultdict(list)
for n in ast.walk(tree):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names[n.name].append(n.lineno)
dups = {k: v for k, v in names.items() if len(v) > 1}
# 区分：不同作用域同名是正常的（如 .close）
for k, v in sorted(dups.items()):
    w('  %-40s 行 %s' % (k, v))
if not dups:
    w('  (无)')

w('')
w('=' * 78)
w('A2. 模块级常量 定义了但全文零引用（死常量）')
w('=' * 78)
const_def = {}
for n in tree.body:
    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
        nm = n.targets[0].id
        if nm.isupper() or (nm.startswith('_') and nm[1:].isupper()):
            const_def[nm] = n.lineno
use_cnt = collections.Counter()
for n in ast.walk(tree):
    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
        use_cnt[n.id] += 1
dead = [(k, v, use_cnt.get(k, 0)) for k, v in const_def.items() if use_cnt.get(k, 0) == 0]
for k, ln, c in sorted(dead, key=lambda x: x[1]):
    w('  L%-6d %-34s 引用次数=%d' % (ln, k, c))
w('  ---- 合计 %d / %d 个模块级常量零引用' % (len(dead), len(const_def)))

w('')
w('=' * 78)
w('A3. 定义了但从未被调用的函数（按名字查调用点，排除回调入口）')
w('=' * 78)
CALLBACK = {'init', 'after_init', 'handlebar', 'timer_poll', 'order_callback',
            'deal_callback', 'orderError_callback', 'log_guard', 'print_summary'}
called = collections.Counter()
for n in ast.walk(tree):
    if isinstance(n, ast.Call):
        f = n.func
        if isinstance(f, ast.Name):
            called[f.id] += 1
        elif isinstance(f, ast.Attribute):
            called[f.attr] += 1
for n in tree.body:
    if isinstance(n, ast.FunctionDef):
        if n.name in CALLBACK:
            continue
        # 字符串里出现也算（可能被 getattr / 注册表调用）
        instr = src.count("'%s'" % n.name) + src.count('"%s"' % n.name)
        if called.get(n.name, 0) == 0:
            w('  L%-6d %-34s 调用=0  字符串出现=%d' % (n.lineno, n.name, instr))

w('')
w('=' * 78)
w('A4. 裸 except / except: pass（吞掉所有异常，含 KeyboardInterrupt）')
w('=' * 78)
bare = []
silent = []
for n in ast.walk(tree):
    if isinstance(n, ast.ExceptHandler):
        if n.type is None:
            bare.append(n.lineno)
            body = n.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                silent.append(n.lineno)
w('  裸 except 总数 = %d' % len(bare))
w('  其中 只有 pass（完全静默） = %d : %s' % (len(silent), silent[:40]))
# 裸 except 且不含任何 log 调用
nolog = []
for n in ast.walk(tree):
    if isinstance(n, ast.ExceptHandler) and n.type is None:
        s = ast.get_source_segment(src, n) or ''
        if ('log(' not in s) and ('_sent_wlog' not in s) and ('print(' not in s) and ('notify' not in s):
            nolog.append(n.lineno)
w('  裸 except 且内部无任何日志输出 = %d : %s' % (len(nolog), nolog[:40]))

w('')
w('=' * 78)
w('A5. ★ 函数内给全局名赋值但缺 global 声明（赋值即变局部变量，静默失效）')
w('=' * 78)
global_consts = set(k for k in const_def)
hits = 0
for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
    declared = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Global):
            declared.update(n.names)
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id in global_consts and t.id not in declared:
                    w('  %s() L%-6d 赋值 %s （无 global 声明 → 实际写的是局部变量）' % (fn.name, n.lineno, t.id))
                    hits += 1
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            if n.target.id in global_consts and n.target.id not in declared:
                w('  %s() L%-6d 自增 %s （无 global）' % (fn.name, n.lineno, n.target.id))
                hits += 1
if hits == 0:
    w('  (无)')

w('')
w('=' * 78)
w('A6. 可变默认参数（[] / {} / set() 作默认值）')
w('=' * 78)
cnt = 0
for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
    for d in list(fn.args.defaults) + [x for x in fn.args.kw_defaults if x]:
        if isinstance(d, (ast.List, ast.Dict, ast.Set)) or (isinstance(d, ast.Call) and getattr(d.func, 'id', '') in ('list', 'dict', 'set')):
            w('  %s() L%-6d 默认值=%s' % (fn.name, fn.lineno, seg(d)))
            cnt += 1
w('  ---- 合计 %d' % cnt)

w('')
w('=' * 78)
w('A7. 版本号一致性')
w('=' * 78)
head_txt = '\n'.join(L[:246])
m1 = re.search(r'#\s*版本号[:：]\s*(\S+)', head_txt)
w('  文件头 版本号 = %s' % (m1.group(1) if m1 else '未找到'))
for n in tree.body:
    if isinstance(n, ast.Assign) and any(getattr(t, 'id', '') == 'VERSION' for t in n.targets):
        w('  L%-6d VERSION = %s' % (n.lineno, seg(n.value)))
# 全文出现的所有 V2.6.xxx
vs = collections.Counter(re.findall(r'V2\.6\.\d{3}', src))
w('  全文版本串计数: %s' % dict(sorted(vs.items(), key=lambda x: x[0])))
mx = max(vs, key=lambda k: int(k.split('.')[-1]))
w('  最高版本串 = %s' % mx)

io.open(r'E:\桌面\666666\dxgp\_a157_sweepA.txt', 'w', encoding='utf-8', newline='\n').write('\n'.join(out))
print('\n'.join(out))
