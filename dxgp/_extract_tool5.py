# -*- coding: utf-8 -*-
"""跨会话搜索 download_risk_exclude.py 源码。"""
import io, json, os, re, sys, glob

BASE = r'C:\Users\MangoKehan\.workbuddy\projects'
files = []
for d in os.listdir(BASE):
    p = os.path.join(BASE, d)
    if os.path.isdir(p):
        files += glob.glob(os.path.join(p, '*.jsonl'))
    else:
        files.append(p)

best = []   # (score, len, content, path, ln)
for p in files:
    if os.path.getsize(p) > 60_000_000:
        continue
    try:
        with io.open(p, 'r', encoding='utf-8', errors='replace') as f:
            for ln, line in enumerate(f, 1):
                if 'add_argument' not in line:
                    continue
                if 'ann' not in line and 'risk_exclude' not in line:
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
                            if isinstance(v, str) and 'add_argument' in v and len(v) > 5000:
                                sc = v.count('def ') + v.count('add_argument')
                                best.append((sc, len(v), v, p, ln))
                            elif isinstance(v, (dict, list)):
                                stack.append(v)
                    elif isinstance(cur, list):
                        stack.extend(cur)
    except Exception as e:
        print('skip', p, e)

best.sort(key=lambda x: (-x[0], -x[1]))
print('候选:', len(best))
for sc, L, v, p, ln in best[:10]:
    print('  score=%-4d len=%-7d %s L%d' % (sc, L, os.path.basename(os.path.dirname(p)), ln))
if best:
    out = r'E:\桌面\666666\dxgp\_tool_risk_exclude.py'
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(best[0][2])
    print('已写出最高分候选:', len(best[0][2]), 'chars  来源', best[0][3], 'L%d' % best[0][4])
