# -*- coding: utf-8 -*-
"""探测新浪 hs_a 节点: 总分页/全市场覆盖/ST命中数/耗时, 判断能否替代 push2 作 st 源。"""
import json
import time
import urllib.request
import collections

BASE = ('http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
        'Market_Center.getHQNodeData?page=%d&num=100&sort=symbol&asc=1&node=hs_a&symbol=')

HDRS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Referer': 'https://finance.sina.com.cn'}


def fetch_page(p, num=100):
    url = BASE % p
    if num != 100:
        url += '&num=%d' % num
    req = urllib.request.Request(url, headers=HDRS)
    raw = urllib.request.urlopen(req, timeout=15).read().decode('gbk', 'ignore')
    return json.loads(raw)


def main():
    # 先试 num=500 是否被服务端接受(减少请求数)
    t0 = time.time()
    try:
        rows = fetch_page(1, num=500)
        print('num=500 page1 rows=%d' % len(rows))
        if len(rows) > 100:
            print('=> num=500 有效, 可用大页')
        else:
            print('=> num=500 被服务端截断到 %d, 仍用 100/页' % len(rows))
    except Exception as e:
        print('num=500 失败: %r' % e)

    all_rows = []
    p = 1
    empty = 0
    t0 = time.time()
    while p <= 120:
        try:
            rows = fetch_page(p)
        except Exception as e:
            print('page %d ERR %r' % (p, e))
            break
        if not rows:
            empty += 1
            if empty >= 2:
                break
            p += 1
            continue
        empty = 0
        all_rows.extend(rows)
        p += 1
        time.sleep(0.12)
    dt = time.time() - t0
    print('----')
    print('TOTAL_ROWS', len(all_rows))
    print('LAST_PAGE', p - 1, 'ELAPSED_SEC', round(dt, 1))

    mk = collections.Counter()
    st = []
    bj = []
    for r in all_rows:
        sym = r.get('symbol', '')
        code = r.get('code', '')
        name = r.get('name', '')
        pre = sym[:2] if len(sym) >= 2 else '??'
        mk[pre] += 1
        if pre == 'bj':
            bj.append((code, name))
        up = name.upper().replace(' ', '')
        if ('ST' in up) or (u'退' in name):
            st.append((code, name))
    print('MARKET', dict(mk))
    print('ST_COUNT', len(st))
    print('BJ_TOTAL', len(bj))
    bj_st = [x for x in bj if 'ST' in x[1].upper() or u'退' in x[1]]
    print('BJ_ST', len(bj_st), bj_st[:10])
    # 北交所 920 段覆盖
    bj920 = [x for x in bj if x[0].startswith('920')]
    print('BJ_920_COUNT', len(bj920), bj920[:5])
    print('ST_SAMPLE', st[:15])
    # 名称空值/异常检查
    bad = [r for r in all_rows if not r.get('code') or not r.get('name')]
    print('BAD_ROWS', len(bad))


if __name__ == '__main__':
    main()
