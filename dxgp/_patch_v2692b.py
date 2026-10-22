# -*- coding: utf-8 -*-
"""V2.6.92b 补丁(自查补漏): 
  [1] 装载成功后必须记账 G.risk_ex_sig —— 否则每 60 秒都判"清单已更新", 反复重载刷屏。
  [2] 重载后 0 只的判定收紧 —— 只有"真解析失败(err 非空)或文件没读成(_found=False)"才沿用旧表;
      文件读到了但确实 0 只(极端情形)不该被说成"解析失败"。
"""
import hashlib
import io
import re

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'

EDITS = [
    ('装载成功记账文件指纹',
     r'^            used = cand\n',
     "            used = cand\n"
     "            G.risk_ex_sig = _risk_ex_sig_of(cand)      # V2.6.92: 记账, 供下次指纹比对\n",
     re.M),
    ('重载后0只的判定收紧',
     r'^    if _reload and not data and _prev:\n',
     "    if _reload and not data and _prev and (err or not _found):\n",
     re.M),
]


def main():
    raw = io.open(P, 'rb').read()
    txt = raw.decode('gbk')
    crlf = txt.count('\r\n')
    print('原始: %d 字节 / CRLF=%d / 纯LF=%d' % (len(raw), crlf, txt.count('\n') - crlf))
    t = txt.replace('\r\n', '\n')
    for name, pat, new, flags in EDITS:
        n = len(re.findall(pat, t, flags))
        if n != 1:
            raise SystemExit('[中止] 锚点不唯一/未命中: %s (count=%d)' % (name, n))
        t = re.sub(pat, lambda m: new, t, count=1, flags=flags)
        print('  [OK] %-24s 1处' % name)
    out = t.replace('\n', '\r\n')
    if out.count('\r\n') != out.count('\n'):
        raise SystemExit('[中止] 存在非CRLF换行残留')
    compile(out, P, 'exec')
    io.open(P, 'wb').write(out.encode('gbk'))
    nb = io.open(P, 'rb').read()
    print('完成: %d 行 / %d 字节 / MD5 %s'
          % (out.count('\n'), len(nb), hashlib.md5(nb).hexdigest()))


if __name__ == '__main__':
    main()
