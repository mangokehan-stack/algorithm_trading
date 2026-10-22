# -*- coding: utf-8 -*-
p = r'C:/广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_run.log'
try:
    d = open(p, 'rb').read()
    t = d.decode('gbk', 'replace')
    ls = [x for x in t.split('\r\n') if x.strip()]
    print('bytes', len(d), 'lines', len(ls))
    for x in ls[-25:]:
        print(x[:260])
except Exception as e:
    print('ERR', type(e).__name__, e)
