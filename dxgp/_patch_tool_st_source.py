# -*- coding: utf-8 -*-
"""2026-10-20: 排雷工具 st 数据源 push2 -> 新浪 hs_a。
五处改动, 每处都有唯一锚点断言; 文件为纯 LF, 保持 LF 写回。
用法: python _patch_tool_st_source.py  (可重复跑, 已打过则第2次因锚点失效而中止)"""
import io
import sys

FN = '_tool_risk_exclude.py'

with io.open(FN, 'r', encoding='utf-8', newline='') as f:
    src = f.read()

if '\r' in src:
    print('ABORT: 文件含 CR, 不是纯 LF')
    sys.exit(1)


def swap(old, new, tag):
    global src
    c = src.count(old)
    if c != 1:
        print('ABORT[%s]: 锚点命中 %d 次(期望1)' % (tag, c))
        sys.exit(1)
    src = src.replace(old, new, 1)
    print('OK[%s]' % tag)


# ---------------------------------------------------------------- 1) PUSH -> SINA_HS
swap("PUSH = 'https://push2.eastmoney.com/api/qt/clist/get'",
     "SINA_HS = ('http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/'\n"
     "           'Market_Center.getHQNodeData')",
     'PUSH->SINA_HS')

# ---------------------------------------------------------------- 2) http_json enc
swap('def http_json(url, timeout=15, retries=2):',
     'def http_json(url, timeout=15, retries=2, enc=\'utf-8\'):',
     'http_json 签名')
swap("                return json.loads(r.read().decode('utf-8', errors='replace'))",
     "                return json.loads(r.read().decode(enc, errors='replace'))",
     'http_json 解码')

# ---------------------------------------------------------------- 3) fetch_st 整体重写
NEW_FETCH_ST = u'''def fetch_st(bag, timeout):
    u"""全A名称 -> 含 ST/*ST/退 的票。返回命中数。

    2026-10-20 换源: 旧走 push2.eastmoney.com 名称接口, 该 host 对本机 IP 反爬封锁
    (RemoteDisconnected 0.1~0.33s, 服务端主动断连, 镜像 82./61. 同样, 重试无效;
    同刻 datacenter-web / np-anotice / qt.gtimg 均 200 正常, 坐实单 host 封锁),
    st 类从在线 203 只掉到本地兜底 145 只。改新浪 hs_a 列表接口 —— GBK JSON,
    100 行/页; 2026-10-20 实测 56 页 5574 只全市场(沪2317/深2906/北351),
    名称含 ST/退 命中 202 只, 与 push2 健康时一致, 北交所 920 段全覆盖。
    失败时本函数抛异常由上层记录, 不影响其它数据源; ST 另有三条兜底 ——
    ①本地策略清单(fetch_st_local, 策略每日写入, 实测145只)
    ②下面的公告名称识别(fetch_ann)
    ③策略侧 QMT 实时名称检查(inst_name + P1-1 名称失败保守剔除), 后者才是权威。
    u"""
    n, page = 0, 1
    while page <= 80:
        u = (SINA_HS + '?page=%d&num=100&sort=symbol&asc=1&node=hs_a&symbol=' % page)
        rows = http_json(u, timeout=timeout, enc='gbk')
        if not rows:
            break
        for r in rows:
            code6 = str(r.get('code') or '')
            name = str(r.get('name') or '')
            if not code6 or not name:
                continue
            code = suffix_of(code6)
            if '.' not in code:      # 只收能映射到交易所后缀的代码, 挡掉杂项行
                continue
            up = name.upper().replace(' ', '')
            if ('ST' in up) or (u'退' in name):
                bag.add(code, 'st', u'ST/退市风险(名称:%s)' % name)
                n += 1
        if len(rows) < 100:
            break
        page += 1
        time.sleep(0.12)      # 轻微间隔, 降低被限流概率
    if n < 100:
        # 2026-10-20 防御: 新浪若静默返回空页/半页(UA 变更/参数变更/深页被截),
        # 老逻辑会 ok:True + n=0 写进 JSON, 策略侧当天零 st 拦截还不报警;
        # 现直接抛异常走 fetch_st_local 兜底(145 只), 并让 sources.st 记 err。
        raise IOError(u'st 源异常: 新浪 hs_a 仅命中 %d 只(正常约200), 疑似空响应或翻页被截' % n)
    return n'''

_i = src.find('def fetch_st(bag, timeout):')
_j = src.find('    return n', _i)
if _i < 0 or _j < 0:
    print('ABORT[fetch_st]: 找不到函数起止')
    sys.exit(1)
_j += len('    return n')
_old_block = src[_i:_j]
if 'PUSH + ' not in _old_block or 'fetch_st_local' not in src[_j:_j + 400]:
    print('ABORT[fetch_st]: 旧块特征不符(不是预期的 push2 版)')
    sys.exit(1)
src = src[:_i] + NEW_FETCH_ST + src[_j:]
print('OK[fetch_st 重写] 旧块 %d 字符 -> 新块 %d 字符' % (len(_old_block), len(NEW_FETCH_ST)))

# ---------------------------------------------------------------- 4) 变更记录
CHLOG = u'''2026-10-20 (st 数据源切换 push2 -> 新浪 hs_a, 依据 push2 反爬封锁实测 + 新浪全市场探测)
  [7] fetch_st 换源 —— push2.eastmoney.com 对本机 IP 反爬封锁(RemoteDisconnected
      0.1~0.33s 服务端主动断连, 镜像 82./61. 同样, 重试无效), st 类从在线 203 只
      掉到本地兜底 145 只(少的 58 只多为近期无公告 ST 票, 选股/买入闸门漏排);
      改新浪 hs_a 列表接口(GBK, 100行/页, 实测 56 页 5574 只全市场, 命中 202 只,
      北交所 920 段全覆盖: 920023/920090/920575), 失败仍走 fetch_st_local。
  [8] fetch_st 增 n<100 熔断 —— 新浪若静默返回空页(UA/参数变更/深页被截),
      老逻辑会 ok:True+n=0 写进 JSON, 策略侧当天零 st 拦截且不报警; 现抛异常
      走本地兜底, 并让 sources.st 记 err。
  [9] http_json 增 enc 参数 —— 新浪返回 GBK, utf-8 强解会把"退市"解成乱符,
      "退"字检测失效; 默认 utf-8, 不影响其余四个东财数据源。
'''
swap(u'2026-10-19 (三项零风险修正, 依据当晚 23:31 实跑日志 594 只)',
     CHLOG + u'2026-10-19 (三项零风险修正, 依据当晚 23:31 实跑日志 594 只)',
     '变更记录')

# ---------------------------------------------------------------- 5) main 兜底注释补注
swap(u'                #   兜底文件是策略自己写的当前名称快照, 属同一台机器上的权威数据, 比公告兜底可靠。',
     u'                #   兜底文件是策略自己写的当前名称快照, 属同一台机器上的权威数据, 比公告兜底可靠。\n'
     u'                # 2026-10-20 晚: st 主源已切新浪 hs_a(见 fetch_st [7]), 本兜底降级为\n'
     u'                #   "新浪也失败"时的第二道防线, 兜底文件名与读取逻辑不变。',
     'main 兜底注释')

# ---------------------------------------------------------------- 写回 + 自检
with io.open(FN, 'w', encoding='utf-8', newline='') as f:
    f.write(src)

compile(src, FN, 'exec')
print('COMPILE_OK')
print('NEW_LEN', len(src), 'NEW_LINES', src.count('\n') + 1)
