# -*- coding: utf-8 -*-
"""V2.6.152 干跑: 从母版 AST 抽取字符串常量真实渲染, 验证 19 处文案已与行为一致。
   不注入任何桩, 全部从母版切片。"""
import ast
import re
import sys

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
src = t.replace('\r\n', '\n')
tree = ast.parse(src)
L = src.split('\n')

res = []
def ok(name, detail=''):
    res.append(('PASS', name, detail))
def bad(name, detail=''):
    res.append(('FAIL', name, detail))

# 收集所有字符串常量(排除模块/函数 docstring —— 文件头是整块历史记录, 天然含旧词)
DOCS = set()
for nd in ast.walk(tree):
    if isinstance(nd, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
        d = ast.get_docstring(nd, clean=False)
        if d:
            DOCS.add(d)
CONSTS = []
for nd in ast.walk(tree):
    if isinstance(nd, ast.Constant) and isinstance(nd.value, str) and len(nd.value) > 8:
        if nd.value in DOCS:
            continue
        CONSTS.append(nd.value)

def render(tpl):
    """按占位符类型喂参数: %s->str, %d->int, %f->float"""
    pats = re.findall(r'%(?:\.\d+)?([sdf])', tpl.replace('%%', ''))
    args = []
    for p in pats:
        if p == 's':
            args.append('X')
        elif p == 'd':
            args.append(1)
        else:
            args.append(1.0)
    return tpl % tuple(args) if args else tpl

OLD = ['全按中性', '全部中性', '不影响原策略', '不拦截买入', '全按中性来',
       '按中性处理', '中性, 不阻塞交易', '就绪前全部中性']
# 允许保留的自然措辞: "情绪值-0.97处于中性区间" / "按【中性】处理" 已改成 "此时暂停开新仓"... 实际 7 号仍有【中性】
# 所以只查"按中性处理"及其变体是否还被用作"不影响交易"的说明
bad_left = []
for s in CONSTS:
    for k in OLD:
        if k in s:
            bad_left.append((k, s[:90]))
if bad_left:
    bad('代码字符串常量仍含旧口径', repr(bad_left[:4]))
else:
    ok('代码字符串常量已无旧口径', '检查 %d 条常量' % len(CONSTS))

# ---- 1) 初始化行真实渲染 ----
c_init = [s for s in CONSTS if s.startswith('情绪模块初始化:')]
if len(c_init) == 1:
    out = c_init[0] % ('0.1.0', 3, '1981eb897c6e')
    if '暂停开新仓' in out and '中性处理' not in out:
        ok('① 初始化行', out)
    else:
        bad('① 初始化行', out)
else:
    bad('① 初始化行 常量数', str(len(c_init)))

# ---- 2) 情绪指纹行真实渲染 ----
c_fp = [s for s in CONSTS if 'Phase=%d 就绪=%s' in s]
if len(c_fp) == 1:
    out = c_fp[0] % ('1981eb897c6e', 3, 'False(尚未发起取数, 首轮定时器会拉起)')
    if '暂停开新仓' in out and '卖出不受影响' in out and '中性' not in out:
        ok('② 情绪指纹行', out)
    else:
        bad('② 情绪指纹行', out)
else:
    bad('② 情绪指纹行 常量数', str(len(c_fp)))

# ---- 3) 已交后台线程 ----
c_th = [s for s in CONSTS if s.startswith('情绪计算已交给后台线程')]
if len(c_th) == 1:
    out = c_th[0]
    if '买入一律暂停' in out and '中性' not in out:
        ok('③ 已交后台线程', out)
    else:
        bad('③ 已交后台线程', out)
else:
    bad('③ 已交后台线程 常量数', str(len(c_th)))

# ---- 4) ★强提醒(推微信/钉钉)真实渲染 ----
c_alert = [s for s in CONSTS if s.startswith('[情绪模块][强提醒]')]
if len(c_alert) == 1:
    out = c_alert[0] % (5, '累计覆盖率12.3%(<90%下限)')
    if '不拦截买入' in out:
        bad('④ 强提醒仍写"不拦截买入"', out)
    elif '暂停开新仓' in out and '卖出不受影响' in out:
        ok('④ 强提醒(推手机)', out)
    else:
        bad('④ 强提醒', out)
else:
    bad('④ 强提醒 常量数', str(len(c_alert)))

# ---- 5) 状态行读数 ----
c_rd = [s for s in CONSTS if s.startswith('取数中(后台线程')]
if len(c_rd) == 1:
    if '暂停开新仓' in c_rd[0]:
        ok('⑤ 状态行读数', c_rd[0])
    else:
        bad('⑤ 状态行读数', c_rd[0])
else:
    bad('⑤ 状态行读数 常量数', str(len(c_rd)))

# ---- 6) 未渲染占位符检查(对全部 19 处新文案逐条真渲染) ----
NEW_TXT = ['未就绪将暂停开新仓, 卖出不受影响', '此时暂停开新仓', '数据没准备好前暂停开新仓',
           '买入一律暂停(卖出不受影响)', '开新仓暂停']
hit = 0
for s in CONSTS:
    if any(k in s for k in NEW_TXT):
        hit += 1
        try:
            out = render(s)
        except Exception as e:
            bad('新文案渲染失败', '%s <- %r' % (e, s[:70]))
            continue
        if re.search(r'%(?:\.\d+)?[sdf]', out.replace('%%', '')):
            bad('新文案有未渲染占位符', out[:100])
if hit >= 12:
    ok('⑥ 新文案占位符', '扫到 %d 条含新口径的常量, 渲染均无残留占位符' % hit)
else:
    bad('⑥ 新文案数量偏少', '只扫到 %d 条' % hit)

# ---- 7) 逻辑链复核: 降级 -> READY=False -> sent_gate_skip 返回 True ----
#   从母版原样切出 sent_gate_skip 与 sent_block_note 执行(不注桩, 用真实模块级初值)
fn_src = []
for nd in tree.body:
    if isinstance(nd, ast.FunctionDef) and nd.name in ('sent_gate_skip', 'sent_block_note'):
        fn_src.append(ast.get_source_segment(src, nd))
if len(fn_src) == 2:
    ns = {'_SENTIMENT_ON': True, '_SENTIMENT_READY': False, 'SENT_STATE': {}}
    exec('\n'.join(fn_src), ns)
    g = ns['sent_gate_skip']()
    note = ns['sent_block_note']()
    if g is True and '未就绪' in note:
        ok('⑦ 未就绪 → 拦阻', 'gate=%s note=%s' % (g, note))
    else:
        bad('⑦ 未就绪 → 拦阻', 'gate=%s note=%s' % (g, note))
    # 就绪 + 闸门关 -> 放行
    ns['_SENTIMENT_READY'] = True
    ns['SENT_STATE']['gate_skip'] = False
    if ns['sent_gate_skip']() is False and ns['sent_block_note']() == '':
        ok('⑦ 就绪+闸门放行', 'gate=False note=空')
    else:
        bad('⑦ 就绪+闸门放行')
    # 就绪 + 闸门开 -> 拦, 且原因与"未就绪"可区分
    ns['SENT_STATE']['gate_skip'] = True
    if ns['sent_gate_skip']() is True and 'L1闸门' in ns['sent_block_note']():
        ok('⑦ 恐慌拦阻原因可区分', ns['sent_block_note']())
    else:
        bad('⑦ 恐慌拦阻原因可区分', ns['sent_block_note']())
    # 模块关闭 -> 一律放行
    ns['_SENTIMENT_ON'] = False
    if ns['sent_gate_skip']() is False and ns['sent_block_note']() == '':
        ok('⑦ 模块关闭不拦', 'gate=False note=空')
    else:
        bad('⑦ 模块关闭不拦')
else:
    bad('⑦ 函数切片', str(len(fn_src)))

# ---- 8) 版本一致性 ----
vers = re.findall(r"VERSION = '(V2\.6\.\d+)'", src)
heads = re.findall(r'# 版本号: (V2\.6\.\d+)', src)
if vers and heads and vers[0] == heads[0] == 'V2.6.152':
    ok('⑧ 版本号一致', 'VERSION=%s 文件头首行=%s' % (vers[0], heads[0]))
else:
    bad('⑧ 版本号一致', 'VERSION=%s head=%s' % (vers[:1], heads[:1]))

# ---- 输出 ----
OUT = []
for st, name, detail in res:
    OUT.append('%s  %-28s %s' % (st, name, detail))
np = sum(1 for r in res if r[0] == 'PASS')
OUT.append('')
OUT.append('%d/%d PASS' % (np, len(res)))
txt = '\n'.join(OUT)
open(r'E:\桌面\666666\dxgp\_dryrun152.txt', 'w', encoding='utf-8').write(txt)
print(txt)
