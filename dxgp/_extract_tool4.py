# -*- coding: utf-8 -*-
"""定位 download_risk_exclude.py 的 st 源实现。"""
import io, json, re, sys

P = r'C:\Users\MangoKehan\.workbuddy\projects\e-桌面-666666-dxgp\91daf907-b950-4139-acbe-20a9f5bc49bc.jsonl'

PAT = re.compile(r'(def\s+\w*st\w*|st_source|fetch_st|get_st|st_list|ST_LIST|clist/get|RPT_F10|namechange|f10\s)', re.I)

hits = []
with io.open(P, 'r', encoding='utf-8', errors='replace') as f:
    for ln, line in enumerate(f, 1):
        if 'risk_exclude' not in line and 'ann-pages' not in line and '排雷' not in line:
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
                    if isinstance(v, str) and PAT.search(v):
                        hits.append((ln, k, v))
                    elif isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)

print('命中:', len(hits))
seen = set()
for ln, k, v in hits:
    for m in PAT.finditer(v):
        s = v[max(0, m.start()-100):m.end()+160].replace('\n', ' | ')
        h = hash(s)
        if h in seen: continue
        seen.add(h)
        print('L%-6d [%s] %s' % (ln, k, s))
        if len(seen) > 30: sys.exit()
