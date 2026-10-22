# -*- coding: utf-8 -*-
"""找工具源码：抓取含 push2.eastmoney / cninfo 的片段看上下文。"""
import io, json, re, sys

P = r'C:\Users\MangoKehan\.workbuddy\projects\e-桌面-666666-dxgp\91daf907-b950-4139-acbe-20a9f5bc49bc.jsonl'

hits = []
with io.open(P, 'r', encoding='utf-8', errors='replace') as f:
    for ln, line in enumerate(f, 1):
        if 'eastmoney' not in line and 'cninfo' not in line:
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
                    if isinstance(v, str) and ('eastmoney' in v or 'cninfo' in v):
                        hits.append((ln, k, v))
                    elif isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)

print('命中片段:', len(hits))
for ln, k, v in hits[:40]:
    # 打印含 eastmoney/cninfo 的行
    for m in re.finditer(r'.{0,90}(eastmoney|cninfo).{0,90}', v):
        print('L%-6d [%s] %s' % (ln, k, m.group(0).replace('\n', ' | ')))
        break
