# -*- coding: utf-8 -*-
"""V2.6.100 补丁: 三处纯文案口径标注(②③④), 不改任何交易/取数/风控/买卖逻辑, 参数指纹 8a4ab7e8 不变。
② 盈亏账本"持仓成本合计"补注"(含买入费用; 上方单票金额为不含费口径)"
③ 换手率漏斗行区分"剔除:过低/过高"与"旁注:自算/缺失放行"
④ 排雷清单装载行补"标签重叠N只"(分项之和 > 清单总数 即重叠)
"""
import io, hashlib, re, sys

P = 'zt_shrink_strategy_gbk.py'
raw = io.open(P, 'rb').read()
t = raw.decode('gbk')
L = t.split('\r\n')
orig_n = len(L)


def find_one(sub, start=0):
    hits = [i for i in range(start, len(L)) if sub in L[i]]
    if len(hits) != 1:
        raise SystemExit(u'锚点命中 %d 次: %r' % (len(hits), sub[:60]))
    return hits[0]


def insert_before(idx, lines):
    for k, ln in enumerate(lines):
        L.insert(idx + k, ln)


def insert_after(idx, lines):
    for k, ln in enumerate(lines):
        L.insert(idx + 1 + k, ln)


# ---------- 头部 ----------
hdr_new = (u'版本号: V2.6.100             修改时间: 2026-10-20 02:05 (V2.6.100记录: '
           u'用户回"优先处理 ②③④ 三处纯文案补注", 三项全是日志口径标注, 不改任何交易/取数/风控/买卖逻辑, '
           u'参数指纹 8a4ab7e8 不变。'
           u'【② 持仓成本口径】盈亏账本"持仓成本合计"补注"(含买入费用; 上方单票金额为不含费口径)": '
           u'单票金额按不含费显示(启明9360/江南11535=20895), 持仓成本合计按 cost_total=fill_sum+fee 含费(20905), '
           u'差10元=两笔买入各5元最低佣金, 两口径并排易误读为账错10元。'
           u'【③ 换手率旁注】漏斗行改"换手率不符%d(剔除:过低%d/过高%d; 旁注:自算%d/缺失放行%d)": '
           u'旧格式"46(过低37/过高9/自算116/缺失放行0)"易把自算116当排除项相加得162≠46, 实际116是走自算通道的只数旁注, '
           u'过低37+过高9=46才是剔除合计。'
           u'【④ 排雷标签重叠】装载行补"标签重叠N只": 旧格式只给分项(ann=22+decrease=289+lift=222+loss=24+st=166=723)'
           u'与总数691对不上, 差32是标签重叠(一只票命中多标签), 现显式打印重叠数。')
i_hdr = find_one(u'版本号: V2.6.99')
insert_before(i_hdr, [hdr_new])

i_ver = find_one(u"VERSION = 'V2.6.99'")
L[i_ver] = L[i_ver].replace(u"V2.6.99", u"V2.6.100")

# ---------- ② 持仓成本口径 ----------
i_cost = find_one(u'持仓成本合计=%.2f元 | 明细%d笔')
assert L[i_cost].lstrip().startswith(u"log('盈亏账本: 在持"), repr(L[i_cost])
L[i_cost] = L[i_cost].replace(
    u'持仓成本合计=%.2f元 | 明细%d笔',
    u'持仓成本合计=%.2f元(含买入费用; 上方单票金额为不含费口径) | 明细%d笔')

# ---------- ③ 换手率旁注 ----------
i_turn = find_one(u'-> 换手率不符%d(过低%d/过高%d/自算%d/缺失放行%d) / 成交额不足%d / ')
L[i_turn] = L[i_turn].replace(
    u'换手率不符%d(过低%d/过高%d/自算%d/缺失放行%d) / 成交额不足%d / ',
    u'换手率不符%d(剔除:过低%d/过高%d; 旁注:自算%d/缺失放行%d) / 成交额不足%d / ')

# ---------- ④ 排雷标签重叠 ----------
# 先插 _overlap 计算(在 _st_note 三分支之后、log 之前, 与 log 同级 8 空格)
i_note = find_one(u"_st_note = u''")
insert_after(i_note, [
    u"        _overlap = max(0, sum(_cnt.values()) - len(data))   # V2.6.100(4): 标签重叠只数(一只票命中多标签, 分项之和>清单总数即重叠)",
])
# 重新定位 log 行(索引已因插入 +1)
i_log = find_one(u"log('[排雷] 已装载提前排雷清单%d只(%s) 文件=%s%s'")
assert u"os.path.basename(used)" in L[i_log + 2], repr(L[i_log + 2])
L[i_log] = u"        log('[排雷] 已装载提前排雷清单%d只(%s, 标签重叠%d只) 文件=%s%s'"
L[i_log + 1] = u"            % (len(data), ', '.join('%s=%d' % (k, v) for k, v in sorted(_cnt.items())) or '-',"
L[i_log + 2] = u"               _overlap, os.path.basename(used) if used else u'(沿用旧表)', _st_note))"

out = '\r\n'.join(L)
compile(out, P, 'exec')
b = out.encode('gbk')
io.open(P, 'wb').write(b)
m = re.search(r"VERSION = '(V2\.6\.\d+)'", out)
print(u'OK: %d -> %d 行 / %d 字节 / MD5 %s / %s / CRLF %d'
      % (orig_n, len(L), len(b), hashlib.md5(b).hexdigest().upper(),
         m.group(1), b.count(b'\r\n')))
