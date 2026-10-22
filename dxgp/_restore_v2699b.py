# -*- coding: utf-8 -*-
"""反向还原 _baseline/V2.6.99.py: V2.6.100 相对 V2.6.99 只改了版本头+VERSION+三处文案,
故从 V2.6.100 精确回退即可还原 V2.6.99, 用 memory 记录的 MD5 校验。
"""
import io, hashlib, sys

SRC = '_baseline/V2.6.100.py'
DST = '_baseline/V2.6.99.py'
EXPECT_MD5 = '78AC2EE6F0FD4C5DB0ECB1D216092F67'

raw = io.open(SRC, 'rb').read()
t = raw.decode('gbk')
L = t.split('\r\n')


def find_one(sub):
    hits = [i for i in range(len(L)) if sub in L[i]]
    if len(hits) != 1:
        raise SystemExit(u'锚点命中 %d 次: %r' % (len(hits), sub[:60]))
    return hits[0]


# 1 删 V2.6.100 版本头
del L[find_one(u'版本号: V2.6.100')]

# 2 VERSION 还原
i_ver = find_one(u"VERSION = 'V2.6.100'")
L[i_ver] = L[i_ver].replace(u"V2.6.100", u"V2.6.99")

# 3 ② 还原
i_cost = find_one(u'持仓成本合计=%.2f元(含买入费用; 上方单票金额为不含费口径) | 明细%d笔')
L[i_cost] = L[i_cost].replace(
    u'持仓成本合计=%.2f元(含买入费用; 上方单票金额为不含费口径) | 明细%d笔',
    u'持仓成本合计=%.2f元 | 明细%d笔')

# 4 ③ 还原
i_turn = find_one(u'换手率不符%d(剔除:过低%d/过高%d; 旁注:自算%d/缺失放行%d) / 成交额不足%d / ')
L[i_turn] = L[i_turn].replace(
    u'换手率不符%d(剔除:过低%d/过高%d; 旁注:自算%d/缺失放行%d) / 成交额不足%d / ',
    u'换手率不符%d(过低%d/过高%d/自算%d/缺失放行%d) / 成交额不足%d / ')

# 5 ④ 还原：删 _overlap 行 + 格式串去重叠 + % 参数去 _overlap
del L[find_one(u'_overlap = max(0, sum(_cnt.values()) - len(data))')]
i_log = find_one(u"log('[排雷] 已装载提前排雷清单%d只(%s, 标签重叠%d只) 文件=%s%s'")
L[i_log] = L[i_log].replace(u', 标签重叠%d只', u'')
i_pct = i_log + 2
assert u'_overlap, os.path.basename(used)' in L[i_pct], repr(L[i_pct])
L[i_pct] = L[i_pct].replace(u'_overlap, ', u'')

out = '\r\n'.join(L)
compile(out, SRC, 'exec')
b = out.encode('gbk')
io.open(DST, 'wb').write(b)
md5 = hashlib.md5(b).hexdigest().upper()
ok = (md5 == EXPECT_MD5)
print(u'V2.6.99 反向还原: %d 行 / %d 字节 / MD5=%s 期望=%s -> %s'
      % (len(L), len(b), md5, EXPECT_MD5, 'PASS' if ok else 'MISMATCH'))
sys.exit(0 if ok else 1)
