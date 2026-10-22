# -*- coding: utf-8 -*-
"""测试新浪全A列表接口能否替代 push2 做 ST 过滤。"""
import json, ssl, time, urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
      'Referer': 'https://finance.sina.com.cn'}


def ctx():
    try:
        return ssl._create_unverified_context()
    except Exception:
        return None


def get(url, timeout=20, enc='gbk'):
    t0 = time.time()
    req = urllib.request.Request(url, headers=UA)
    kw = {}
    c = ctx()
    if c is not None:
        kw['context'] = c
    with urllib.request.urlopen(req, timeout=timeout, **kw) as r:
        raw = r.read()
    return raw.decode(enc, errors='replace'), time.time() - t0


BASE = ('http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
        'Market_Center.getHQNodeData?page=%d&num=100&sort=symbol&asc=1&node=%s')

for node in ('hs_a', 'st_category', 'st', 'sh_a'):
    try:
        txt, dt = get(BASE % (1, node))
        print('node=%-12s %.2fs len=%-7d head=%s' % (node, dt, len(txt), txt[:110].replace('\n', ' ')))
    except Exception as e:
        print('node=%-12s FAIL %s: %s' % (node, type(e).__name__, str(e)[:70]))
    print('-' * 100)

# 解析 hs_a 看结构
try:
    txt, dt = get(BASE % (1, 'hs_a'))
    rows = json.loads(txt)
    print('hs_a 返回行数:', len(rows))
    print('字段:', sorted(rows[0].keys()) if rows else None)
    if rows:
        print('样例:', {k: rows[0][k] for k in list(rows[0])[:8]})
    st = [r for r in rows if 'ST' in str(r.get('name', '')).upper()]
    print('本页 ST 命中:', len(st), [r.get('symbol') + ' ' + r.get('name') for r in st[:5]])
    print('total(接口报的总数):', get(BASE % (1, 'hs_a'))[0][:0] or '?')
except Exception as e:
    print('解析失败:', type(e).__name__, e)
