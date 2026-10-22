# -*- coding: utf-8 -*-
"""从对话记录中提取 download_risk_exclude.py 源码（严格筛选：像 Python 代码）。"""
import io, json, re, sys

P = r'C:\Users\MangoKehan\.workbuddy\projects\e-桌面-666666-dxgp\91daf907-b950-4139-acbe-20a9f5bc49bc.jsonl'

cands = []
with io.open(P, 'r', encoding='utf-8', errors='replace') as f:
    for ln, line in enumerate(f, 1):
        if 'download_risk_exclude' not in line and 'ann-pages' not in line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if k in ('content', 'text', 'input', 'new_string', 'old_string') and isinstance(v, str):
                        if ('argparse' in v or 'add_argument' in v) and len(v) > 3000:
                            cands.append((len(v), v, ln))
                    elif isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)

# 去重
seen = set(); uniq = []
for L, v, ln in cands:
    h = hash(v[:400])
    if h in seen: continue
    seen.add(h); uniq.append((L, v, ln))
uniq.sort(key=lambda x: -x[0])
print('候选:', len(uniq))
for L, v, ln in uniq[:10]:
    head = v[:70].replace('\n', '\\n')
    print('  len=%-7d line=%-6d head=%s' % (L, ln, head))
