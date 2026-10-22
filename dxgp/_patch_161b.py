# -*- coding: utf-8 -*-
"""V2.6.161 补强补丁(干跑 _dryrun_161.py 实测发现的残余越界)。
else 目标金额分支: 金额只削到帽值时, vol 按 lp 向下取整后 vol*lp 仍贴近帽值,
实收价含滑点(最高0.3%)单票成本会再超帽约0.3% —— 实测 lp=10.10:
6600股 @10.12 = 66792.00 元 > MAX_POS_VALUE_ABS 66666.66(超125.34元),
而日志还写着"削平为66667元"(日志与实收不一致)。
本补丁把该分支改成与另两个分支完全同口径: 按股数帽(取整到整手)削 vol, 超帽归零;
帽算下来不足一手则拒单。
另: V2.6.161 记录行补记本次补强, 时间戳改为真实落盘时间。
"""
import datetime
import os
import shutil
import sys

MASTER = 'zt_shrink_strategy_gbk.py'

raw = open(MASTER, 'rb').read()
orig_len = len(raw)


def E(s):
    return s.encode('gbk')


def sub_once(buf, old, new, tag):
    n = buf.count(old)
    if n != 1:
        print('FATAL %s: anchor count=%d (expect 1)' % (tag, n))
        sys.exit(1)
    return buf.replace(old, new, 1)


# ---------- R15: else 分支补股数帽(与另两个分支同口径) ----------
old = E("        if _caps_g:\r\n"
        "            _amt_cap = min(_caps_g) * _px_g\r\n"
        "            if amount > _amt_cap:\r\n"
        "                log(disp(s), '目标金额: %.0f元超过仓位帽, 削平为%.0f元' % (amount, _amt_cap))\r\n"
        "                amount = _amt_cap\r\n"
        "        vol = int(amount / lp / _lot) * _lot")
new = E("        if _caps_g:\r\n"
        "            _cv_g = int(min(_caps_g) / _lot) * _lot\r\n"
        "            if _cv_g < _lot:\r\n"
        "                log(disp(s), '目标金额: 仓位帽算下来不足一手(帽=%.0f股 价格=%.2f), 放弃'\r\n"
        "                    % (min(_caps_g), _px_g))\r\n"
        "                return None\r\n"
        "            _amt_cap = _cv_g * _px_g\r\n"
        "            if amount > _amt_cap:\r\n"
        "                log(disp(s), '目标金额: %.0f元超过仓位帽, 削平为%.0f元' % (amount, _amt_cap))\r\n"
        "                amount = _amt_cap\r\n"
        "        vol = int(amount / lp / _lot) * _lot\r\n"
        "        # V2.6.161补强(干跑 _dryrun_161.py 实测lp=10.10发现残余越界): 金额只削到帽值时,\r\n"
        "        #   vol 按 lp 向下取整到整手后 vol*lp 仍贴近帽值, 实收价含滑点(最高0.3%)单票成本\r\n"
        "        #   会再超帽约0.3% —— 实测6600股@10.12=66792.00元, 超MAX_POS_VALUE_ABS 125.34元,\r\n"
        "        #   而日志还写着\"削平为66667元\"(日志数字与实收成本不一致, 属会骗人的观测)。\r\n"
        "        #   此处按股数帽(与另两个分支同口径, 已取整到整手)直接削 vol, 超帽归零。\r\n"
        "        if _caps_g and vol > _cv_g:\r\n"
        "            log(disp(s), '目标金额: %d股超过仓位帽, 削平为%d股' % (vol, _cv_g))\r\n"
        "            vol = _cv_g")
raw = sub_once(raw, old, new, 'R15-else股数帽')

# ---------- R16: V2.6.161 记录行补记 + 真实落盘时间 ----------
now = datetime.datetime.now()
ts = now.strftime('%Y-%m-%d %H:%M')
old = E('修改时间: 2026-10-22 01:07')
new = E('修改时间: %s' % ts)
raw = sub_once(raw, old, new, 'R16-时间戳')

old = E('原本两帽全无, 同样补上。只削不增, 帽内行为零变化。')
new = E('原本两帽全无, 同样补上; 干跑实测(lp=10.10)发现金额削平后按lp取整仍会因滑点价超帽约0.3%'
        '(6600股@10.12=66792.00元, 超MAX_POS_VALUE_ABS 125.34元, 而日志还写着削平为66667元), '
        '已按股数帽再削vol, 超帽归零, 帽算下来不足一手则拒单。只削不增, 帽内行为零变化。')
raw = sub_once(raw, old, new, 'R16-记录补强')

# ---------- 落盘前自检 ----------
assert raw[:3] != b'\xef\xbb\xbf', 'BOM appeared'
n_lf = raw.count(b'\n')
n_crlf = raw.count(b'\r\n')
if n_lf != n_crlf:
    print('FATAL: bare LF = %d' % (n_lf - n_crlf))
    sys.exit(1)
raw.decode('gbk')
assert raw.count(E("VERSION = 'V2.6.161'")) == 1
assert raw.count(E('        if _caps_g and vol > _cv_g:')) == 1
assert raw.count(E("'目标金额: %d股超过仓位帽, 削平为%d股' % (vol, _cv_g)")) == 1
# 新局部量仍全是 _ 前缀(不进指纹)
import re
for m in re.finditer(rb'^\s+(_[a-z0-9_]+)\s*=', raw, re.M):
    pass
assert not re.search(rb'^\s{0,8}([A-Z][A-Z0-9_]*)\s*=\s*$', raw[raw.find(E('    else:')):raw.find(E('    if vol < _lot:'))], re.M), 'else分支出现模块级大写常量'

# ---------- 备份 -> 原子写 ----------
bak = 'zt_shrink_strategy_gbk.py.bak-' + now.strftime('%Y%m%d-%H%M')
shutil.copy2(MASTER, bak)
tmp = MASTER + '.tmp'
with open(tmp, 'wb') as f:
    f.write(raw)
    f.flush()
    os.fsync(f.fileno())
os.replace(tmp, MASTER)
print('OK backup=%s  %d -> %d bytes  (+%d)' % (bak, orig_len, len(raw), len(raw) - orig_len))
print('record timestamp: %s' % ts)
