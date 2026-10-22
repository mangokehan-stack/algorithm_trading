# -*- coding: utf-8 -*-
"""V2.6.99 补丁: 情绪取数连续预算命中的收口(3 项)
【1】退避: 连续>=2轮预算命中 -> 重试间隔 300->1800 秒(SENT_STATE 计数, 不新增常量)
【2】告警顺序: 预算命中/中止告警挪到"取数完成"行之后
【3】沿用信号时效: _sent_use_last_good 加严为交易日龄<=2天(局部算式, 不动 SENT_MONITOR_MAX_STALE_DAYS)
"""
import io, hashlib, sys

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


def insert_after(idx, lines):
    for k, ln in enumerate(lines):
        L.insert(idx + 1 + k, ln)


def insert_before(idx, lines):
    for k, ln in enumerate(lines):
        L.insert(idx + k, ln)


# ---------- 头部 ----------
hdr_new = (u'版本号: V2.6.99              修改时间: 2026-10-20 01:42 (V2.6.99记录: '
           u'用户回"全部一起修复, 根据你推荐思路修复, 直到完成为止", 落地 3 项 —— '
           u'情绪取数连续预算命中的收口, 不改任何交易/风控逻辑, 参数指纹 8a4ab7e8 不变。'
           u'【1 退避】连续>=2轮预算命中后重试间隔300->1800秒(SENT_STATE[bh_streak]计数, '
           u'不新增常量): 2026-10-20 00:53~01:34 连续8轮全败、每轮烧180~210秒接口, '
           u'300秒一轮等于六成时间在空打接口且可能自我加重; 任一轮不再命中即自动恢复300秒。'
           u'【2 告警顺序】预算命中/中止两类告警挪到"内置通道取数完成"行之后 '
           u'(旧版告警比完成行早约10秒, 日志时间倒流)。'
           u'【3 沿用信号时效】_sent_use_last_good 加严: 沿用信号的交易日龄>2个交易日即降级中性 '
           u'(局部算式不新增常量, SENT_MONITOR_MAX_STALE_DAYS=5 保持不动) —— 5天上限对数据通道'
           u'合理, 但沿用是把旧档位(含贪婪覆写)直接套到买入上, 拿2天前的贪婪档开盘比中性更危险; '
           u'日历缺失按自然日折半近似, 日龄算不出时保持旧行为(沿用)。)')
i_hdr = find_one(u'版本号: V2.6.98')
insert_before(i_hdr, [hdr_new])

i_ver = find_one(u"VERSION = 'V2.6.98'")
L[i_ver] = L[i_ver].replace(u"V2.6.98", u"V2.6.99")

# ---------- 【1a】worker: 预算命中计数 ----------
i_bh = find_one(u"_cov['budget_hit'] = bool(_budget_hit)")
assert u"SENT_STATE['cover'] = _cov" in L[i_bh + 1]
insert_after(i_bh, [
    u"        # V2.6.99(1): 连续预算命中计数(供调度侧退避) —— 连续>=2轮把重试间隔",
    u"        #   300->1800秒; 本轮未命中即清零。放 SENT_STATE, 不新增模块级常量。",
    u"        SENT_STATE['bh_streak'] = (int(SENT_STATE.get('bh_streak') or 0) + 1) if _budget_hit else 0",
])

# ---------- 【1b】调度侧退避门 ----------
i_gate = find_one(u"if (_now - (SENT_STATE.get('last_try_ts') or 0.0)) < SENT_RETRY_SEC:")
assert L[i_gate - 1] == u'        _now = time.time()', repr(L[i_gate - 1])
assert L[i_gate + 1] == u'            return                      # 重试节流'
new_gate = [
    u'        _now = time.time()',
    u'        # V2.6.99(1): 连续预算命中退避 —— 每轮烧180~210秒接口还被拒, 300秒一轮等于',
    u'        #   六成时间在空打接口, 还可能反过来加重接口慢(2026-10-20 00:53~01:34 连续8轮全败)。',
    u'        #   连续>=2轮预算命中 -> 重试间隔 300->1800秒; 任一轮不再命中(bh_streak清零)即恢复。',
    u"        _bh_streak = int(SENT_STATE.get('bh_streak') or 0)",
    u'        _retry_sec = 1800.0 if _bh_streak >= 2 else SENT_RETRY_SEC',
    u"        if (_now - (SENT_STATE.get('last_try_ts') or 0.0)) < _retry_sec:",
    u"            if _bh_streak >= 2 and (_now - (SENT_STATE.get('bh_backoff_log_ts') or 0.0)) >= _retry_sec:",
    u"                SENT_STATE['bh_backoff_log_ts'] = _now",
    u"                _sent_wlog('情绪取数已连续%d轮触发总预算(接口慢约11~21倍), 重试间隔退避300->1800秒;'",
    u"                           '某轮不再命中预算即自动恢复300秒' % _bh_streak)",
    u'            return                      # 重试节流',
]
L[i_gate - 1:i_gate + 2] = new_gate

# ---------- 【2】挪告警 ----------
i_ab = find_one(u'        if _abort:')
i_bud = find_one(u'        if _budget_hit:')
i_stats = find_one(u'        if not _stats:')
assert i_ab < i_bud < i_stats
block_abort = L[i_ab:i_bud]
block_bud = L[i_bud:i_stats]
del L[i_ab:i_stats]
# 在"内置通道取数完成"行(其语句结束于 if _cov['samples']: 之前)之后插入
i_smp = find_one(u"        if _cov['samples']:")
block_bud = block_bud + [
    u"            if (int(SENT_STATE.get('bh_streak') or 0)) >= 2:",
    u"                _sent_wlog('已连续%d轮预算命中, 调度侧重试间隔退避至1800秒(原300秒); '",
    u"                           '某轮不再命中预算即自动恢复300秒'",
    u"                           % int(SENT_STATE.get('bh_streak') or 0))",
]
insert_before(i_smp, block_abort + block_bud)

# ---------- 【3】沿用信号时效 ----------
i_fresh = find_one(u'        if not _sent_fresh_enough(_d, _sent_today()):')
# fresh_enough 块: if + 2行体 + return False
assert L[i_fresh + 3].strip() == u'return False', repr(L[i_fresh + 3])
i_ready = i_fresh + 4
assert u"SENT_STATE['ready'] = True" in L[i_ready]
blk3 = [
    u'        # V2.6.99(3): 沿用信号加严的交易日龄上限(2个交易日; 局部算式, 不新增常量):',
    u"        #   _sent_fresh_enough 的 5 交易日上限针对\"数据通道整体\"合理, 但\"沿用\"是把旧档位",
    u'        #   (含panic/贪婪覆写)直接套到今天的买入上 —— 拿2天前的贪婪档开盘买入比中性更危险。',
    u'        #   交易日历缺失时按自然日折半近似; 日龄算不出来时保持旧行为(沿用)。',
    u'        _age_td = None',
    u'        try:',
    u"            _cal = getattr(G, 'calendar', None)",
    u"            _cal = [str(x)[:8] for x in _cal] if _cal else []",
    u'            _td = _sent_today()',
    u'            if _cal and _td in _cal and _d in _cal:',
    u'                _age_td = _cal.index(_td) - _cal.index(_d)',
    u'            else:',
    u'                import datetime as _dt',
    u"                _age_td = (_dt.datetime.strptime(_td, '%Y%m%d') -",
    u"                           _dt.datetime.strptime(_d, '%Y%m%d')).days // 2",
    u'        except Exception:',
    u'            _age_td = None',
    u'        if _age_td is not None and not (0 <= _age_td <= 2):',
    u"            _sent_degrade_alert(why + '(沿用信号过旧 last=%s, 超2个交易日)' % _d)",
    u"            _sent_reset_ready(why + '; 沿用信号过旧(last=%s, >2个交易日)' % _d)",
    u'            return False',
]
insert_before(i_ready, blk3)

out = '\r\n'.join(L)
compile(out, P, 'exec')
b = out.encode('gbk')
io.open(P, 'wb').write(b)
import re
m = re.search(r"VERSION = '(V2\.6\.\d+)'", out)
print(u'OK: %d -> %d 行 / %d 字节 / MD5 %s / %s / CRLF %d'
      % (orig_n, len(L), len(b), hashlib.md5(b).hexdigest().upper(),
         m.group(1), b.count(b'\r\n')))
