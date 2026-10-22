# -*- coding: utf-8 -*-
"""
V2.6.103 修复1: 覆盖率门槛悖论(预算截断 -> 门槛 98% -> 永远够不到 -> 情绪信号冻结在隔夜值)
  修复1-A: 取数顺序由"代码升序"改为"按当日固定种子打乱", 保证被截断时取到的是全市场均匀抽样
  修复1-B: 截断时判定标准由"覆盖率"改为"零失败 + 样本量 >= 800 只", 够就采用本轮实测值
铁律: 只改情绪取数侧的"采不采用本轮结果", 不碰买卖判据/止损; 不新增模块级大写常量
"""
import io, hashlib, py_compile

SRC = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
NL = '\r\n'
t = io.open(SRC, 'r', encoding='gbk', newline='').read()
orig = len(t.encode('gbk'))
print('ORIG_BYTES=%d  CHARS=%d  CRLF=%d' % (orig, len(t), t.count(NL)))

def rep(old, new, tag):
    global t
    n = t.count(old)
    if n != 1:
        raise SystemExit('ANCHOR FAIL [%s]: count=%d' % (tag, n))
    t = t.replace(old, new, 1)
    print('OK [%s]' % tag)

# ---------------- 1) 文件头版本记录 ----------------
HDR = (
    '版本号: V2.6.103             修改时间: 2026-10-20 09:15 (V2.6.103记录: 用户选"修复1", 处理'
    '"覆盖率门槛悖论": 预算截断会把覆盖率门槛临时从90%提到98%, 但被截断的轮次最多只取到28%~34%, '
    '永远够不到98% -> 情绪信号被永久冻结在上一次成功信号(2026-10-20 实跑: 连续3轮 truncated, '
    '全天沿用 20261019 的 panic 档, 开盘等45分钟/缩量阈值0.30 都是昨天的情绪, 不是今天的)。'
    '本版拆成两件事做, 缺一不可:'
    '【修复1-A 先解决代表性】原取数顺序是 sorted(代码升序), 被截断时只能取到代码最小的那一段 —— '
    '代码注释里已有实测: 前1200只全是 000/001/002 深市主板, 缺沪市/创业板/科创板/北交所, '
    '涨跌占比系统性偏差(同一分钟 sentiment 从 -1.27 漂到 -1.00)。'
    '改为"按当日固定种子打乱": 截断时取到的是全市场均匀抽样; 同一天多次取数顺序一致(可复现), 跨天不同。'
    '未截断(整轮跑完)时顺序不影响统计结果, 与旧行为完全一致。'
    '【修复1-B 再改判定口径】截断 != 取数失败: 改为"零失败 且 已取到 >= 800 只"(约全市场15%, '
    '抽样误差约±3.5%, 且样本已由 A 保证均匀) -> 采用本轮实测值; 否则仍维持98%门槛沿用上次成功信号(保守不变)。'
    '真实例子: 2026-10-20 08:46 那轮取到1800只/失败0只, 旧口径判28.7%<98%丢弃、沿用隔夜 panic; '
    '新口径判"零失败+1800只够" -> 采用当天实测情绪。'
    '风险: 采用半截数据会引入约±3.5%抽样误差, 但优于用隔夜信号卡当天的买入闸门; 若接口恢复整轮跑完, '
    '两口径结果相同(覆盖率自然达标)。800 为局部字面量(未提模块级常量, 参数指纹 8a4ab7e8 不变))'
    + NL + '版本号: V2.6.102'
)
rep('版本号: V2.6.102', HDR, 'hdr-version-note')

# ---------------- 2) VERSION 常量 ----------------
rep("VERSION = 'V2.6.102'", "VERSION = 'V2.6.103'", 'VERSION-const')

# ---------------- 3) 修复1-A: 均匀抽样 ----------------
A_OLD = '        _stocks = sorted(set(_stocks))' + NL
A_NEW = (
    '        _stocks = sorted(set(_stocks))' + NL +
    '        # V2.6.103(\u4fee\u590d1-A): \u9884\u7b97\u622a\u65ad\u65f6\u82e5\u6309\u4ee3\u7801\u5347\u5e8f\u53d6\u6570, \u88ab\u622a\u65ad\u53ea\u80fd\u53d6\u5230\u4ee3\u7801\u6700\u5c0f\u7684\u90a3\u4e00\u6bb5' + NL +
    '        #   \u5b9e\u6d4b: \u524d 1200 \u53ea\u5168\u662f 000/001/002 \u6df1\u5e02\u4e3b\u677f, \u7f3a\u6caa\u5e02/\u521b\u4e1a\u677f/\u79d1\u521b\u677f/\u5317\u4ea4\u6240, ' + NL +
    '        #   \u6da8\u8dcc\u5360\u6bd4\u4f1a\u7cfb\u7edf\u6027\u504f\u5dee(\u540c\u4e00\u5206\u949f sentiment \u4ece -1.27 \u6f02\u5230 -1.00)\u3002' + NL +
    '        #   \u6539\u4e3a"\u6309\u5f53\u65e5\u56fa\u5b9a\u79cd\u5b50\u6253\u4e71": \u622a\u65ad\u65f6\u53d6\u5230\u7684\u662f\u5168\u5e02\u573a\u5747\u5300\u62bd\u6837; \u540c\u4e00\u5929\u591a\u6b21\u53d6\u6570' + NL +
    '        #   \u987a\u5e8f\u4e00\u81f4(\u53ef\u590d\u73b0\u6bd4\u5bf9), \u8de8\u5929\u4e0d\u540c\u3002\u672a\u622a\u65ad(\u6574\u8f6e\u8dd1\u5b8c)\u65f6\u987a\u5e8f\u4e0d\u5f71\u54cd\u7edf\u8ba1\u7ed3\u679c\u3002' + NL +
    '        try:' + NL +
    "            random.Random(str(G.today or '')).shuffle(_stocks)" + NL +
    '        except Exception:' + NL +
    '            pass' + NL
)
rep(A_OLD, A_NEW, 'fix1a-uniform-sample')

# ---------------- 4) 修复1-B: 调度侧门槛 ----------------
B_OLD = (
    '        _min_cov = 0.98 if _cov.get(\'budget_hit\') else SENT_COVERAGE_MIN' + NL
)
B_NEW = (
    '        # V2.6.103(\u4fee\u590d1-B): \u9884\u7b97\u622a\u65ad != \u53d6\u6570\u5931\u8d25\u3002\u65e7\u53e3\u5f84\u628a\u95e8\u69db\u63d0\u5230 98%, \u800c\u88ab\u622a\u65ad\u7684\u8f6e\u6b21' + NL +
    '        #   \u6700\u591a\u53ea\u53d6\u5230 28%~34%, \u6c38\u8fdc\u591f\u4e0d\u5230 -> \u60c5\u7eea\u4fe1\u53f7\u88ab\u51bb\u7ed3\u5728\u9694\u591c\u503c\u3002' + NL +
    '        #   \u65b0\u53e3\u5f84: \u622a\u65ad\u65f6\u6539\u5224"\u96f6\u5931\u8d25 + \u6837\u672c\u91cf\u591f\u4e0d\u591f"(\u6837\u672c\u5df2\u7531\u4fee\u590d1-A \u4fdd\u8bc1\u5747\u5300):' + NL +
    '        #     \u96f6\u5931\u8d25 \u4e14 \u5df2\u53d6\u5230 >= 800 \u53ea(\u7ea6\u5168\u5e02\u573a 15%, \u62bd\u6837\u8bef\u5dee\u7ea6\u00b13.5%) -> \u91c7\u7528\u672c\u8f6e\u5b9e\u6d4b\u503c;' + NL +
    '        #     \u5426\u5219\u4ecd\u7ef4\u6301 98% \u95e8\u69db -> \u6cbf\u7528\u4e0a\u4e00\u6b21\u6210\u529f\u4fe1\u53f7(\u4fdd\u5b88\u4e0d\u53d8)\u3002' + NL +
    '        _min_cov = SENT_COVERAGE_MIN' + NL +
    '        if _cov.get(\'budget_hit\'):' + NL +
    '            _min_cov = 0.0 if (int(_cov.get(\'fail\') or 0) == 0' + NL +
    '                               and int(_cov.get(\'ok\') or 0) >= 800) else 0.98' + NL
)
rep(B_OLD, B_NEW, 'fix1b-dispatch-gate')

# ---------------- 5) 修复1-B: worker 侧门槛 ----------------
C_OLD = (
    '        _min_cov = 0.98 if _budget_hit else SENT_COVERAGE_MIN' + NL
)
C_NEW = (
    '        # V2.6.103(\u4fee\u590d1-B, \u4e0e\u8c03\u5ea6\u4fa7\u540c\u53e3\u5f84): \u9884\u7b97\u622a\u65ad\u65f6\u6539\u5224"\u96f6\u5931\u8d25 + \u6837\u672c\u91cf >= 800 \u53ea"' + NL +
    '        #   (\u6837\u672c\u5df2\u7531\u4fee\u590d1-A \u6253\u4e71\u4e3a\u5168\u5e02\u573a\u5747\u5300\u62bd\u6837); \u5426\u5219\u4ecd 98% \u6cbf\u7528\u4e0a\u6b21\u6210\u529f\u4fe1\u53f7\u3002' + NL +
    '        _min_cov = SENT_COVERAGE_MIN' + NL +
    '        if _budget_hit:' + NL +
    '            _min_cov = 0.0 if (int(_cov.get(\'fail\') or 0) == 0' + NL +
    '                               and int(_cov.get(\'ok\') or 0) >= 800) else 0.98' + NL +
    '        if _budget_hit and _min_cov <= 0.0:' + NL +
    '            _sent_wlog(\'[\u63d0\u793a] \u672c\u8f6e\u88ab\u603b\u9884\u7b97\u622a\u65ad, \u4f46\u96f6\u5931\u8d25\u4e14\u5df2\u53d6\u5230%d\u53ea' + NL +
    '                       (\u5168\u5e02\u573a\u5747\u5300\u62bd\u6837, \u8986\u76d6%.1f%%), \u6837\u672c\u91cf\u8db3\u591f: ' + NL +
    '                       \u91c7\u7528\u672c\u8f6e\u5b9e\u6d4b\u60c5\u7eea(\u4e0d\u518d\u6cbf\u7528\u4e0a\u6b21\u6210\u529f\u4fe1\u53f7)\'' + NL +
    '                       % (int(_cov.get(\'ok\') or 0), (_cov.get(\'ratio\') or 0) * 100.0))' + NL
)
rep(C_OLD, C_NEW, 'fix1b-worker-gate')

# ---------------- 6) 告警文案同步 ----------------
D_OLD = (
    "                          ('; \u672c\u8f6e\u89e6\u53d1\u53d6\u6570\u603b\u9884\u7b97(\u6570\u636e\u88ab\u622a\u65ad), \u95e8\u69db\u5df2\u4e34\u65f6\u4ece90%\u63d0\u9ad8\u523098%')" + NL +
    '                          if _budget_hit else \'\'))' + NL
)
D_NEW = (
    "                          ('; \u672c\u8f6e\u89e6\u53d1\u53d6\u6570\u603b\u9884\u7b97\u4e14\u6837\u672c\u4e0d\u8db3800\u53ea\u6216\u6709\u5931\u8d25, \u95e8\u69db\u7ef4\u630198%')" + NL +
    '                          if _budget_hit else \'\'))' + NL
)
rep(D_OLD, D_NEW, 'fix1b-worker-warn-text')

E_OLD = (
    "                   (', \u672c\u8f6e\u89e6\u53d1\u53d6\u6570\u603b\u9884\u7b97\u6545\u95e8\u69db\u4e34\u65f6\u4ece90%\u63d0\u9ad8\u523098%')" + NL
)
E_NEW = (
    "                   (', \u672c\u8f6e\u89e6\u53d1\u53d6\u6570\u603b\u9884\u7b97(\u6837\u672c\u4e0d\u8db3\u6216\u6709\u5931\u8d25, \u95e8\u69db\u7ef4\u630198%)')" + NL
)
rep(E_OLD, E_NEW, 'fix1b-dispatch-warn-text')

out = t.encode('gbk')
io.open(SRC, 'wb').write(out)
print('NEW_BYTES=%d DELTA=%d  CRLF=%d  LINES=%d' % (
    len(out), len(out) - orig, t.count(NL), len(t.split(NL))))

for fn in ['def _sent_fetch_sync', 'def sent_daily_refresh', 'def run_pyramid_adds',
           'def run_round', 'def sell_stock', 'def buy_stock']:
    if fn not in t:
        raise SystemExit('LOST FUNC: %s' % fn)
print('ALL_FUNC_ANCHORS_OK')
py_compile.compile(SRC, doraise=True)
print('PY_COMPILE_OK  MD5=%s' % hashlib.md5(out).hexdigest().upper())
