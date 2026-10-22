# -*- coding: utf-8 -*-
"""测试可用的替代 ST 数据源（只在已通的 host 上找）。"""
import json, ssl, time, urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
      'Referer': 'https://data.eastmoney.com/'}


def ctx():
    try:
        return ssl._create_unverified_context()
    except Exception:
        return None


def probe(tag, url, timeout=15):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        kw = {}
        c = ctx()
        if c is not None:
            kw['context'] = c
        with urllib.request.urlopen(req, timeout=timeout, **kw) as r:
            raw = r.read()
        dt = time.time() - t0
        txt = raw.decode('utf-8', errors='replace')
        head = txt[:160].replace('\n', ' ')
        return '%-26s OK  %.2fs len=%-7d %s' % (tag, dt, len(raw), head)
    except Exception as e:
        return '%-26s FAIL %.2fs %s: %s' % (tag, time.time() - t0, type(e).__name__, str(e)[:80])


tests = [
    # 新浪 风险警示板
    ('新浪 ST板', 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'
                  'Market_Center.getHQNodeData?page=1&num=20&sort=symbol&asc=1&node=st_category'),
    # 东财 datacenter 各种可能名
    ('dc RPT_ST_LIST', 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ST_LIST&columns=ALL&pageSize=5'),
    ('dc STBOARDLIST', 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_STBOARDLIST&columns=ALL&pageSize=5'),
    ('dc RPT_RISKSTOCK', 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_RISKSTOCK&columns=ALL&pageSize=5'),
    # 东财公告域(np-anotice-stock) 已知通
    ('ann 域(已知通)', 'https://np-anotice-stock.eastmoney.com/api/security/ann?page_size=1&page_index=1&ann_type=A'),
    # push2his 历史域
    ('push2his', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.000001&fields1=f1&fields2=f51&klt=101&fqt=0&end=20500101&lmt=1'),
    # 腾讯行情
    ('腾讯 qt.gtimg', 'http://qt.gtimg.cn/q=sh600000'),
    # 东财 datacenter 沪深个股(行情中心)
    ('dc 沪深A股列表', 'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_MS_PERFORMANCE&columns=ALL&pageSize=3'),
]

print('=' * 110)
for tag, url in tests:
    print(probe(tag, url))
    print('-' * 110)
