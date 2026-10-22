# -*- coding: utf-8 -*-
"""诊断 push2.eastmoney.com 为何 RemoteDisconnected，并测试替代 ST 数据源。"""
import json, ssl, time, urllib.request, urllib.error

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
      'Referer': 'https://data.eastmoney.com/'}
PUSH = 'https://push2.eastmoney.com/api/qt/clist/get'
DC = 'https://datacenter-web.eastmoney.com/api/data/v1/get'


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
            code = r.getcode()
        dt = time.time() - t0
        try:
            j = json.loads(raw.decode('utf-8', errors='replace'))
            n = len((j.get('data') or {}).get('diff') or []) if isinstance(j, dict) else '?'
            return '%-28s OK  code=%s %.2fs rows=%s len=%d' % (tag, code, dt, n, len(raw))
        except Exception:
            return '%-28s OK  code=%s %.2fs 非JSON len=%d head=%r' % (tag, code, dt, len(raw), raw[:60])
    except Exception as e:
        return '%-28s FAIL %.2fs %s: %s' % (tag, time.time() - t0, type(e).__name__, str(e)[:90])


tests = []
# 1) 工具正在用的 st 源（第1页）
tests.append(('push2 st 源(工具原样)', PUSH + '?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3'
              '&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f13,f14'))
# 2) 控制组：datacenter-web（其他四类源用的域）
tests.append(('datacenter-web(控制组)', DC + '?reportName=RPTDATAFKRISKST&columns=ALL&pageSize=5'))
# 3) 同 host 换个接口（行情列表）
tests.append(('push2 行情列表(沪深A)', PUSH + '?pn=1&pz=5&po=1&np=1&fltt=2&invt=2&fid=f3'
              '&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14'))
# 4) push2 镜像 host
for h in ('82.push2.eastmoney.com', '61.push2.eastmoney.com'):
    tests.append((h.split('/')[0], 'https://' + h + '/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2'
                  '&invt=2&fid=f3&fs=m:0+t:6,m:1+t:2&fields=f12,f14'))
# 5) 东财 ST 专题页接口（datacenter 域）
tests.append(('datacenter ST专题', DC + '?reportName=RPT_EMP_STOCKSTLIST&columns=ALL&pageSize=5'))

print('=' * 100)
for tag, url in tests:
    print(probe(tag, url))
    print('-' * 100)
