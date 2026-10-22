# -*- coding: utf-8 -*-
"""V2.6.84: 排雷模块日志口径纠偏(用户确认"改")
1. 区分 文件不存在 / 文件存在但清单为空 / 解析失败 三种情形
2. 提示补上"生成后自动装载, 无需重启"
3. 三种提示改为每日一次, 防止 60 秒重试时刷屏
仅改日志文案与输出频次, 不动解析/拦截/买卖逻辑。
"""
import sys

P = 'zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
text = raw.decode('gbk')
lines = text.split('\r\n')
n0 = len(lines)

def find(pred, desc, lo=0, hi=None):
    hi = hi if hi is not None else len(lines)
    hits = [i for i in range(lo, hi) if pred(lines[i])]
    if len(hits) != 1:
        print('FAIL 定位[%s]: 命中 %d 处 -> %r' % (desc, len(hits), [h + 1 for h in hits]))
        sys.exit(1)
    return hits[0]

# --- 锚点 1: data, used, err = {}, '', '' (在 load_risk_exclude 内) ---
a1 = find(lambda l: l.strip() == "data, used, err = {}, '', ''", 'data/used/err 初始化')
print('OK 锚点1 L%d: %s' % (a1 + 1, lines[a1].strip()))
assert "G.risk_ex_date == G.today" in lines[a1 - 2], '锚点1 上下文不符'

# --- 锚点 2: for _k, _v in j['stocks'].items(): ---
a2 = find(lambda l: l.strip() == "for _k, _v in j['stocks'].items():", 'stocks 遍历')
print('OK 锚点2 L%d: %s' % (a2 + 1, lines[a2].strip()))
assert "_found" not in lines[a2], '锚点2 已打过补丁?'

# --- 锚点 3: else 分支前的 elif err: ---
a3 = find(lambda l: l.strip() == 'elif err:' and 'risk' not in l, 'elif err 分支', a1, a1 + 120)
print('OK 锚点3 L%d: %s' % (a3 + 1, lines[a3].strip()))

# --- 锚点 4: 旧文案 ---
a4 = find(lambda l: '未发现排雷清单文件(可选功能)' in l, '旧文案')
print('OK 锚点4 L%d' % (a4 + 1))
assert lines[a4 + 1].strip().startswith("' 当前仅依赖实时闸门"), '锚点4 后续行不符'
assert lines[a4 - 1].strip() == 'else:', '锚点4 前一行不是 else: -> %r' % lines[a4 - 1].strip()

ok_old = lines[a4].strip()
ok_old2 = lines[a4 + 1].strip()

# 倒序应用: 先改后面的文案块, 再改前面的初始化与 _found

# === 编辑 A: 重写 else 分支 (a4 起, 替换 2 行) ===
new_tail = [
    "    elif _found:",
    "        # V2.6.84: 文件存在但清单为空 —— 旧版误并入\"未发现文件\"分支, 提示方向跑偏",
    "        if getattr(G, 'risk_ex_note_date', '') != G.today:",
    "            G.risk_ex_note_date = G.today",
    "            log('[排雷][提示] 清单文件存在但内容为空(0只): %s —— 今日无提前排雷拦截对象;'",
    "                ' 若刚更新过清单请确认工具输出是否正常' % os.path.basename(used))",
    "    else:",
    "        # V2.6.84: 旧版说\"可选功能\"但 RISK_EXCLUDE_ON 实为 True, 会让人以为未启用而不去补清单;",
    "        #   且未说明生成后自动装载(无需重启), 用户会误以为要等次日。改为醒目待办 + 明确生效方式。",
    "        #   每日一次, 避免 60 秒重试装载时反复刷屏(重试本身不变, 清单随时生成仍当轮生效)。",
    "        if getattr(G, 'risk_ex_note_date', '') != G.today:",
    "            G.risk_ex_note_date = G.today",
    "            log('[排雷][待办] 排雷功能已开启(RISK_EXCLUDE_ON=True)但清单文件不存在: %s'",
    "                % ', '.join(os.path.basename(x) for x in _risk_exclude_candidates()))",
    "            log('[排雷][待办] 今日仅依赖实时闸门(ST/财务亏损/仙股/退潮等), 无提前排雷(解禁/减持/立案/预亏)拦截;'",
    "                ' 请运行 download_risk_exclude.py 生成清单 —— 生成后自动装载, 无需重启策略')",
]
lines[a4 - 1:a4 + 2] = new_tail
delta_tail = len(new_tail) - 3

# === 编辑 B: 插入 _found = True (在 for _k 之前) ===
ins = ["            _found = True      # V2.6.84: 文件已成功打开且解析出 stocks 字典(内容可能为空)"]
lines[a2:a2] = ins
delta_b = len(ins)

# === 编辑 C: 初始化 _found ===
lines[a1] = "    data, used, err = {}, '', ''"
lines[a1:a1 + 1] = [
    "    data, used, err = {}, '', ''",
    "    _found = False     # V2.6.84: 是否找到并成功解析清单文件(用于区分\"文件不存在\"与\"清单为空\")",
]
delta_c = 1

out = '\r\n'.join(lines)
assert out.count('\r\n') == len(lines) - 1, 'CRLF 计数异常'
try:
    compile(out.replace('#coding:gbk', '#coding:utf-8'), P, 'exec')
except SyntaxError as e:
    print('FAIL 语法: %s line %s' % (e, e.lineno))
    sys.exit(2)
out.encode('gbk')
open(P, 'wb').write(out.encode('gbk'))
print('OK: 3 处编辑, lines %d -> %d (delta %+d)' % (n0, len(lines), len(lines) - n0))
print('   文案块 %+d / _found插入 %+d / 初始化 %+d' % (delta_tail, delta_b, delta_c))
