# -*- coding: utf-8 -*-
"""V2.6.159 第十四轮审计 —— 第十五轮(V2.6.158/159)修复项回归复查

判据纪律（踩过 6 次的坑）：
  · 负向断言必须排除模块 docstring 与注释行，否则会被版本记录原文撞掉
  · 全文子串断言太宽 → 改用「行首缩进 + 整行」或 AST 节点判
  · 期望值不许手算 → 一律调用被测代码本身或用程序算
"""
import ast, io, re, sys

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
b = open(P, 'rb').read()
src = b.decode('gbk')
assert src.encode('gbk') == b, 'GBK 往返失败'
N = src.replace('\r\n', '\n')
L = N.split('\n')
tree = ast.parse(N)

# ---- 代码区（剔除模块 docstring 与全部注释行），用于负向断言 ----
n0 = tree.body[0]
doc_lo, doc_hi = n0.lineno, n0.end_lineno
CODE = []
for i, l in enumerate(L, 1):
    if doc_lo <= i <= doc_hi:
        continue
    st = l.strip()
    if st.startswith('#'):
        continue
    CODE.append((i, l))
CODE_TXT = '\n'.join(x[1] for x in CODE)

results = []
def chk(no, name, ok, detail=''):
    results.append((no, name, bool(ok), detail))

def count_code(pat):
    """在代码区按整行正则计数"""
    r = re.compile(pat)
    return sum(1 for _, l in CODE if r.search(l))

def count_all(pat):
    r = re.compile(pat)
    return sum(1 for l in L if r.search(l))

def func_seg(fname):
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == fname:
            return n
    return None

# ============ 铁律三查 ============
n_stop = sum(1 for x in ast.walk(tree)
             if (isinstance(x, ast.Attribute) and x.attr == 'stop_order')
             or (isinstance(x, ast.Name) and x.id == 'stop_order'))
chk('R0', '铁律一：止损单/止损参数 AST 引用为 0', n_stop == 0, '实际 %d' % n_stop)
nsl = [l.strip() for l in L if l.strip().startswith('NEVER_STOP_LOSS')]
chk('R0b', '铁律一：NEVER_STOP_LOSS=True 开关在位',
    nsl and 'True' in nsl[0], nsl[0][:60] if nsl else '缺失')

# ============ V2.6.158 修复项 ============
# ① 排雷装载不再传非法参数
bad_call = count_code(r'load_risk_exclude\s*\(\s*(force|True|False|\w+\s*=)')
chk('158-1', '①排雷装载不再传非法参数(原必 TypeError)', bad_call == 0, '可疑 %d 处' % bad_call)

# ② state_broken_lock 存在，且人工核对型冻结点都打标记
chk('158-2a', '②存在 state_broken_lock 标记', count_code(r'state_broken_lock') >= 3,
    '%d 处' % count_code(r'state_broken_lock'))
# 写盘成功分支里保留的置False 属于「写盘失败型」自动恢复路径；
# 人工核对型在它之前已 early-return 并保持 True。判据 = lock 分支内部三要素齐全。
_f2 = func_seg('save_state')
_s2 = ast.get_source_segment(N, _f2) if _f2 else ''
_m = re.search(r"if bool\(getattr\(G, ?'state_broken_lock'.*?\n(.*?)(?=\n        except)", _s2 or '', re.S)
_blk = _m.group(1) if _m else ''
chk('158-2b', '②人工核对型冻结在写盘成功时保持不解除',
    ('state_broken = True' in _blk and 'return True' in _blk),
    'lock分支块长 %d' % len(_blk))

# ③ 买入费用不记两遍：占位带 fee_pre，首笔成交先清零
chk('158-3a', '③占位记录含 fee_pre 标记', count_code(r"'fee_pre'") >= 2,
    '%d 处' % count_code(r"'fee_pre'"))
chk('158-3b', '③首笔成交前把 fee/cost_total 清零',
    count_code(r"_f\(h\['fee'\]\)|h\['fee'\]\s*=\s*0") >= 1,
    '%d 处' % count_code(r"_f\(h\['fee'\]\)|h\['fee'\]\s*=\s*0"))

# ④ load_risk_exclude 读盘分支有 return data
fn = func_seg('load_risk_exclude')
ret_cnt = sum(1 for x in ast.walk(fn) if isinstance(x, ast.Return)) if fn else 0
# 返回可能是裸 Name(data)，也可能是条件表达式(有 data 就返 data)，两者都算修好
has_data_ret = False
if fn:
    for x in ast.walk(fn):
        if isinstance(x, ast.Return) and x.value is not None:
            if any(isinstance(y, ast.Name) and y.id == 'data' for y in ast.walk(x.value)):
                has_data_ret = True
chk('158-4', '④load_risk_exclude 装载分支返回 data', has_data_ret,
    'return %d 处，含 data %s' % (ret_cnt, has_data_ret))

# ⑤ _ts_to_date 先判八位年月日
fn = func_seg('_ts_to_date')
seg5 = ast.get_source_segment(N, fn) if fn else ''
chk('158-5', '⑤ts_to_date 先判 8 位年月日形态',
    bool(re.search(r'19000101|29991231|\d{8}\s*<=|len\(\s*_?\w+\s*\)\s*==\s*8', seg5 or '')),
    (seg5 or '')[:0] or '已包含八位判定')

# ============ V2.6.159 修复项 ============
fn = func_seg('sell_stall_confirmed')
seg6 = ast.get_source_segment(N, fn) if fn else ''
chk('159-5a', '⑤止盈主判据含近 N 日新高(不再要求涨幅<=1%)',
    ('new_high' in seg6.lower()) or ('新高' in seg6), '')
chk('159-5b', '⑤STALL_MAX_GAIN_PCT 参数仍在位(未被删除)',
    count_code(r'STALL_MAX_GAIN_PCT\s*=') >= 1, '')

# ⑦ bootstrap 快照三条件
fn = func_seg('sent_bootstrap')
seg7 = ast.get_source_segment(N, fn) if fn else ''
chk('159-7', '⑦bootstrap 引入 _restored 条件', '_restored' in seg7, '')

# ⑧ 改名
chk('159-8', '⑧指标文案已改名为强势股家数', count_code(r'强势股家数') >= 1,
    '%d 处' % count_code(r'强势股家数'))

# ⑨ 委托号双向
for fn_name in ('_oid_rec', '_oid_side_of', '_oid_known'):
    chk('159-9-' + fn_name, '⑨存在 %s 辅助函数' % fn_name, func_seg(fn_name) is not None, '')
chk('159-9b', '⑨ordids 按买/卖方向分槽', "'sell'" in CODE_TXT and "'buy'" in CODE_TXT, '')

# ⑩ 死代码清理（负向断言：只查代码区整行）
chk('159-10a', '⑩不可达返回已删(代码区无该整行)',
    count_code(r'^\s*return data\s*$') == 0,
    '%d 处' % count_code(r'^\s*return data\s*$'))
chk('159-10b', '⑩只写不读的 ready 字段已清',
    count_code(r"SENT_STATE\['ready'\]") == 0,
    '%d 处' % count_code(r"SENT_STATE\['ready'\]"))

# ============ 参数指纹零漂移（交易参数不得变） ============
import subprocess, sys as _s
r = subprocess.run([_s.executable, r'E:\桌面\666666\dxgp\_fp_calc_150.py', P],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
fp = [x for x in r.stdout.splitlines() if re.search(r'参数指纹|efb96534', x)]
chk('FP', '参数指纹仍为 efb96534(交易参数零漂移)', 'efb96534' in r.stdout,
    (fp[0].strip()[:70] if fp else r.stdout.strip()[-80:]))

# ============ 输出 ============
ok = sum(1 for x in results if x[2])
print('=' * 72)
print('V2.6.158/159 修复项回归复查   %d / %d PASS' % (ok, len(results)))
print('=' * 72)
for no, name, good, detail in results:
    print('%-4s %-4s %-52s %s' % (no, 'PASS' if good else 'FAIL', name, detail[:40]))
print('-' * 72)
print('FAIL %d 项' % (len(results) - ok))