# -*- coding: utf-8 -*-
"""排雷清单 vs 选股漏斗 对账小工具(只读, 不改任何文件)

用途: 回答一个问题 —— 2026-10-19 23:44 那份清单 594 只里, ann/lift/decrease/st
      四类为什么在这批候选里一只都没命中(漏斗"避雷风险10"恰好等于"财务亏损10")。

跑法(在你自己的终端里, 不要让我这边跑, 我的进程被安全策略拦了):
    python E:\\桌面\\666666\\dxgp\\_chk_overlap.py
    python E:\\桌面\\666666\\dxgp\\_chk_overlap.py 别的账号
"""
import io
import json
import os
import sys
import collections

BASE = r'C:\广发证券QMT量化交易系统 - 交易端\bin.x64'
ACC = sys.argv[1] if len(sys.argv) > 1 else '8973786'
P = os.path.join(BASE, 'zt_shrink_risk_exclude_%s.json' % ACC)

# 2026-10-19 23:44 日志里"亏损筛选剩余表"的 25 只保留票(已过避雷闸门)
KEEP = ('001229 001299 002184 002317 002441 002549 002576 002591 002862 002979 '
        '002980 601566 603155 603336 603353 603466 603500 603980 688196 688517 '
        '688655').split()


def main():
    if not os.path.exists(P):
        print('找不到: %s' % P)
        return 2
    j = json.load(io.open(P, encoding='utf-8'))
    st = j.get('stocks') or {}
    ks = list(st.keys())
    print('文件: %s (%d 字节)' % (os.path.basename(P), os.path.getsize(P)))
    print('顶层键: %s' % ', '.join(sorted(j.keys())))
    print('清单只数: %d' % len(ks))

    sfx = collections.Counter(k.split('.')[-1] if '.' in k else 'NO_SUFFIX' for k in ks)
    print('键后缀分布: %s' % dict(sfx))
    nosfx = [k for k in ks if '.' not in k]
    if nosfx:
        print('  [注意] 无后缀键 %d 个(策略按 000001.SZ 形式查, 这些永远查不到): %s'
              % (len(nosfx), nosfx[:10]))

    print('样本键: %s' % ks[:5])

    tags = collections.Counter()
    notags = 0
    for v in st.values():
        t = (v or {}).get('tags') or []
        if not t:
            notags += 1
        for x in t:
            tags[x] += 1
    print('标签分布(去重后仍按出现计): %s' % dict(tags))
    print('无 tags 的条目: %d' % notags)

    src = j.get('sources') or {}
    print('sources:')
    for k in sorted(src.keys()):
        v = src[k] if isinstance(src[k], dict) else {}
        print('  %-9s ok=%s n=%s err=%s cover=%s~%s'
              % (k, v.get('ok'), v.get('n'), str(v.get('err'))[:50],
                 v.get('cover_from'), v.get('cover_to')))
    if src and not any((src.get('ann') or {}).get('cover_from') for _ in [0]):
        print('  [提示] 没有 ann.cover_from/cover_to -> 这份清单是旧版工具生成的,')
        print('         策略侧"公告实扫仅N天"那条提示不会出现; 重跑新版工具后才有。')

    print('--- 25 只保留票是否误入清单(应为 0) ---')
    bad = 0
    for c in KEEP:
        hit = [k for k in ks if k.startswith(c)]
        if hit:
            bad += 1
            print('  [误入] %s -> %s tags=%s reasons=%s'
                  % (c, hit[0], (st[hit[0]] or {}).get('tags'),
                     ((st[hit[0]] or {}).get('reasons') or [])[:2]))
    print('误入数: %d / %d' % (bad, len(KEEP)))

    print('--- 四类各自覆盖到哪些板块(前 5 个代码前缀) ---')
    for want in ('ann', 'lift', 'decrease', 'st', 'loss'):
        sub = [k for k, v in st.items() if want in ((v or {}).get('tags') or [])]
        pre = collections.Counter(k[:3] for k in sub)
        print('  %-9s %4d 只  代码段Top5=%s  样例=%s'
              % (want, len(sub), dict(pre.most_common(5)), sub[:3]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
