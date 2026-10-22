# -*- coding: utf-8 -*-
"""验证新浪 hs_a 在工具同款 UA(Referer=data.eastmoney.com)下是否可用。
换源最大隐患: 新浪若校验 Referer, 用东财 UA 会被 403/返回空, 必须先排除。"""
import json
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
      'Referer': 'https://data.eastmoney.com/'}
BASE = ('http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
        'Market_Center.getHQNodeData?page=%d&num=100&sort=symbol&asc=1&node=hs_a&symbol=')

for p in (1, 2, 57):
    u = BASE % p
    try:
        raw = urllib.request.urlopen(urllib.request.Request(u, headers=UA),
                                     timeout=15).read()
        j = json.loads(raw.decode('gbk', 'replace'))
    except Exception as e:
        print('PAGE %d FAIL %r' % (p, e))
        continue
    st = [x for x in j if 'ST' in x['name'].upper() or u'退' in x['name']]
    print('PAGE %d rows=%d first=%s|%s st_on_page=%d %s'
          % (p, len(j), j[0]['code'], j[0]['name'], len(st),
             [(x['code'], x['name']) for x in st][:4]))
