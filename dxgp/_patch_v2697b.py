# -*- coding: utf-8 -*-
u"""V2.6.97b 补丁: ④ 的兜底分支 —— ann 类 0 只时不许打出"缺约0只"

R6 的同比算式在 ann_n=0 时会输出 "满覆盖约0只, 缺约0只", 读起来像"没有风险",
实际是"这一类根本没采到"。方向必须说清, 否则日志比不说还误导。
"""
import io
import hashlib

P = 'zt_shrink_strategy_gbk.py'
raw = io.open(P, 'rb').read()
src = raw.decode('gbk')
before = src.count('\r\n') + 1

OLD = (
    u"                    _ann_n = _cnt.get('ann', 0)\r\n"
    u"                    _ann_est = int(round(float(_ann_n) * _wd_decl / float(_cdays))) if _cdays > 0 else 0\r\n"
    u"                    log('[排雷][提示] 公告实扫仅%d天(%s~%s, 仅覆盖%d天窗口的%.0f%%), '\r\n"
    u"                        'ann类仅%d只; 同比推算%d天满覆盖约%d只, 缺约%d只 \u2014\u2014 '\r\n"
    u"                        '立案/处罚/退市风险警示可能漏检, 需加大 --ann-pages'\r\n"
    u"                        % (_cdays, _annc['cover_from'], _annc['cover_to'], _wd_decl,\r\n"
    u"                           _cdays * 100.0 / _wd_decl, _ann_n, _wd_decl, _ann_est,\r\n"
    u"                           max(_ann_est - _ann_n, 0)))\r\n"
)

NEW = (
    u"                    _ann_n = _cnt.get('ann', 0)\r\n"
    u"                    if _ann_n > 0 and _cdays > 0:\r\n"
    u"                        _ann_est = int(round(float(_ann_n) * _wd_decl / float(_cdays)))\r\n"
    u"                        _ann_txt = ('ann类%d只; 同比推算%d天满覆盖约%d只, 缺约%d只'\r\n"
    u"                                    % (_ann_n, _wd_decl, _ann_est,\r\n"
    u"                                       max(_ann_est - _ann_n, 0)))\r\n"
    u"                    else:\r\n"
    u"                        # V2.6.97(4b): ann 类 0 只时同比算式会打出\u201c满覆盖约0只, 缺约0只\u201d,\r\n"
    u"                        #   读起来像\u201c没有风险\u201d, 实际是\u201c这一类根本没采到\u201d。\r\n"
    u"                        #   方向必须说清, 否则这条日志比不打还误导。\r\n"
    u"                        _ann_txt = 'ann类0只(该类可能完全未采到, 不等于无风险)'\r\n"
    u"                    log('[排雷][提示] 公告实扫仅%d天(%s~%s, 仅覆盖%d天窗口的%.0f%%), %s \u2014\u2014 '\r\n"
    u"                        '立案/处罚/退市风险警示可能漏检, 需加大 --ann-pages'\r\n"
    u"                        % (_cdays, _annc['cover_from'], _annc['cover_to'], _wd_decl,\r\n"
    u"                           _cdays * 100.0 / _wd_decl, _ann_txt))\r\n"
)

n = src.count(OLD)
assert n == 1, u'R7 锚点命中 %d 次' % n
src = src.replace(OLD, NEW, 1)

compile(src, P, 'exec')
out = src.encode('gbk')
io.open(P, 'wb').write(out)
t = out.decode('gbk')
print('OK R7 ann=0 兜底分支')
print('行数 %d -> %d / 字节 %d / CRLF %d / MD5 %s'
      % (before, t.count('\r\n') + 1, len(out), out.count(b'\r\n'),
         hashlib.md5(out).hexdigest().upper()))
