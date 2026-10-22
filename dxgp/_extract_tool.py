# -*- coding: utf-8 -*-
"""从对话记录中提取 download_risk_exclude.py 的源码（Write 工具调用的 content）。"""
import io, json, re, sys

P = r'C:\Users\MangoKehan\.workbuddy\projects\e-桌面-666666-dxgp\91daf907-b950-4139-acbe-20a9f5bc49bc.jsonl'

cands = []   # (len, content, lineno)
with io.open(P, 'r', encoding='utf-8', errors='replace') as f:
    for ln, line in enumerate(f, 1):
        line = line.strip()
        if not line or 'download_risk_exclude' not in line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        # 递归找 content 字段
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if k in ('content', 'text', 'input') and isinstance(v, str):
                        if 'ann' in v and ('eastmoney' in v or 'cninfo' in v or 'argparse' in v):
                            cands.append((len(v), v, ln))
                    elif isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)

cands.sort(key=lambda x: -x[0])
print('候选内容块数:', len(cands))
for L, _, ln in cands[:8]:
    print('  len=%d  line=%d' % (L, ln))

if not cands:
    sys.exit('未找到')

best = cands[0][1]
out = r'E:\桌面\666666\dxgp\_tool_risk_exclude.py'
with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
    f.write(best)
print('已写出:', out, len(best), 'chars')
