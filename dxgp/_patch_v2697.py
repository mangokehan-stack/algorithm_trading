# -*- coding: utf-8 -*-
u"""V2.6.97 补丁: ② 优选截断留痕 / ③ 下载耗时并入进度行 / ④ 公告覆盖缺口量化

三项全部只改日志, 不改任何交易/取数/风控行为。
新增变量全部是函数内局部变量或 G 属性(G.dl_t0), 不新增模块级大写常量 -> 参数指纹不变。
"""
import io
import os
import shutil
import hashlib

P = 'zt_shrink_strategy_gbk.py'
NEW_VER = 'V2.6.97'

raw = io.open(P, 'rb').read()
src = raw.decode('gbk')
L = src.split('\r\n')
print('原文件: %d 行 / %d 字节' % (len(L), len(raw)))

# ---------- 备份 ----------
try:
    os.makedirs('_baseline', exist_ok=True)
    if not os.path.exists('_baseline/V2.6.96.py'):
        shutil.copyfile(P, '_baseline/V2.6.96.py')
        print('备份 -> _baseline/V2.6.96.py')
    else:
        print('备份已存在, 跳过')
except Exception as e:
    print('备份失败(继续): %r' % (e,))


def rep_block(old, new, tag):
    u"""整块唯一替换, 命中数必须为 1"""
    global src
    n = src.count(old)
    assert n == 1, '%s: 锚点命中 %d 次' % (tag, n)
    src = src.replace(old, new, 1)
    print('OK %s' % tag)


# ---------- R1 版本头: 新增 V2.6.97 记录行 ----------
hdr_new = (
    u'版本号: V2.6.97              修改时间: 2026-10-20 00:45 '
    u'(V2.6.97记录: 用户回\u201c先让我把 \u2461\u2462\u2463 改完\u201d, '
    u'三项全只改日志, 不改任何交易/取数/风控行为, 参数指纹 8a4ab7e8 不变 '
    u'—— 起因是 2026-10-20 00:22 V2.6.95 完整日志(首次跑到候选生成完毕)的逐行复核: '
    u'账目四段首次全部闭合(5222-2-4917-77-79-31=116; 116-46-12-23-11-15-1-4=4), '
    u'但暴露三处\u201c数字对得上、真相看不见\u201d。'
    u'【2 优选截断零留痕】G.candidates[:MAX_DAILY_PICKS] 直接切片, '
    u'日志只有\u201c候选4只 优选保留2只\u201d加两条\u201c第N优先\u201d, '
    u'被剔的 2 只叫什么/量比多少/为什么排后面一个字没有 —— 排序键出错也发现不了; '
    u'现在截断前逐只打\u201c落选(超出每日优选上限) 代码 名称 昨量/基准量 昨收回撤 第N天\u201d。'
    u'【3 下载耗时没进日志】旧版只有\u201c下载进度 5226 / 5226\u201d, '
    u'明天验证 V2.6.96 串行化省了几分钟只能说\u201c好像快了\u201d; '
    u'现在 G.dl_t0 记起始时刻(局部 G 属性, 不进参数指纹), '
    u'完成行补\u201c耗时N秒 均速X只/秒\u201d(2026-10-20 00:22:33->00:35:39 实测 786 秒 / 5226 只 / 6.6 只每秒)。'
    u'【4 公告覆盖只报天数不报缺口】旧文案\u201c公告实扫仅7天, 未达45天窗口\u201d不给数量级, '
    u'ann=22 只看着像\u201c本来就这么多\u201d; '
    u'现在补\u201c仅覆盖45天窗口的16%, ann类22只, 同比推算满覆盖约141只, 缺约119只\u201d, '
    u'让要不要加 --ann-pages 有数字依据。)'
)
i_hdr = [i for i, l in enumerate(L) if l.startswith(u'版本号: V2.6.96')]
assert len(i_hdr) == 1, u'版本头 V2.6.96 命中 %d 次' % len(i_hdr)
old_hdr = L[i_hdr[0]]
src = src.replace(old_hdr, hdr_new + '\r\n' + old_hdr, 1)
print('OK R1 版本头新增一行')

# ---------- R2 VERSION ----------
rep_block("VERSION = 'V2.6.96'", "VERSION = 'V2.6.97'", 'R2 VERSION')

# ---------- R3 下载起始时刻 ----------
rep_block(
    u"        G.dl_i = 0\r\n"
    u"        G.dl_phase = 1\r\n"
    u"        G.dl_mark = -1      # V2.6.95: 新一轮重新计桶, 保证首轮就打印进度(不再静默10分钟)\r\n",
    u"        G.dl_i = 0\r\n"
    u"        G.dl_phase = 1\r\n"
    u"        G.dl_mark = -1      # V2.6.95: 新一轮重新计桶, 保证首轮就打印进度(不再静默10分钟)\r\n"
    u"        # V2.6.97(3): 下载起始时刻。写成 G 属性而非模块级常量, 否则 _fp_keys() 会把它\r\n"
    u"        #   收进参数指纹, 改日志而已指纹却漂了。\r\n"
    u"        G.dl_t0 = time.time()\r\n",
    'R3 下载起始时刻'
)

# ---------- R4 进度行补耗时 ----------
rep_block(
    u"        if _bucket != getattr(G, 'dl_mark', -1) or G.dl_i >= _u_tot:\r\n"
    u"            G.dl_mark = _bucket\r\n"
    u"            log('\u4e0b\u8f7d\u8fdb\u5ea6', min(G.dl_i, _u_tot), '/', _u_tot)\r\n",
    u"        if _bucket != getattr(G, 'dl_mark', -1) or G.dl_i >= _u_tot:\r\n"
    u"            G.dl_mark = _bucket\r\n"
    u"            # V2.6.97(3): 完成那行补总耗时与均速。旧版只有\u201c下载进度 5226 / 5226\u201d,\r\n"
    u"            #   2026-10-20 00:22:33->00:35:39 这轮下了 786 秒(5226 只 / 6.6 只每秒,\r\n"
    u"            #   当时情绪取数在并发抢接口), 但日志里没有任何时间账可对;\r\n"
    u"            #   明天验证 V2.6.96 串行化到底省了多少, 没有基线就说不出口。\r\n"
    u"            if G.dl_i >= _u_tot:\r\n"
    u"                _dl_el = time.time() - _f(getattr(G, 'dl_t0', 0.0))\r\n"
    u"                _dl_sp = (float(min(G.dl_i, _u_tot)) / _dl_el) if _dl_el > 0 else 0.0\r\n"
    u"                log('\u4e0b\u8f7d\u8fdb\u5ea6', min(G.dl_i, _u_tot), '/', _u_tot,\r\n"
    u"                    '(\u5b8c\u6210, \u8017\u65f6%d\u79d2 \u5747\u901f%.1f\u53ea/\u79d2)' % (int(_dl_el), _dl_sp))\r\n"
    u"            else:\r\n"
    u"                log('\u4e0b\u8f7d\u8fdb\u5ea6', min(G.dl_i, _u_tot), '/', _u_tot)\r\n",
    'R4 进度行补耗时'
)

# ---------- R5 优选截断留痕 ----------
rep_block(
    u"    total = len(G.candidates)\r\n"
    u"    if total > MAX_DAILY_PICKS:\r\n"
    u"        # P2-6: \u6784\u5efa\u7eaa\u5f8b \u2014\u2014 \u6574\u8868\u622a\u65ad\u66ff\u6362(\u539f\u5b50\u5f15\u7528\u6362\u65b0\u5217\u8868), \u4e0d\u5c40\u90e8\u5220\u6539\r\n"
    u"        G.candidates = G.candidates[:MAX_DAILY_PICKS]\r\n",
    u"    total = len(G.candidates)\r\n"
    u"    if total > MAX_DAILY_PICKS:\r\n"
    u"        # V2.6.97(2): 截断留痕。旧写法直接切片, 被剔的票在日志里查无此人 ——\r\n"
    u"        #   2026-10-20 00:36 那次: \u201c候选4只 优选保留2只\u201d只列出 001299(0.48)/002549(0.51)\r\n"
    u"        #   两条, 另 2 只叫什么、量比多少、为什么排后面, 日志一个字没有。\r\n"
    u"        #   若排序键写错把更好的剔了, 用户从日志完全无法发现。\r\n"
    u"        #   注: 必须在切片前打, 切片后对象就没了。\r\n"
    u"        for _rlc in G.candidates[MAX_DAILY_PICKS:]:\r\n"
    u"            log('  \u843d\u9009(\u8d85\u51fa\u6bcf\u65e5\u4f18\u9009\u4e0a\u9650%d\u53ea, \u6309\u91cf\u6bd4\u5347\u5e8f\u8d8a\u5c0f\u8d8a\u4f18) %s %s '\r\n"
    u"                '\u6628\u91cf/\u57fa\u51c6\u91cf=%.2f \u6628\u6536\u56de\u64a4=%.1f%% \u7b2c%d\u5929'\r\n"
    u"                % (MAX_DAILY_PICKS, _rlc['stock'], _rlc.get('name') or u'(\u540d\u79f0\u7f3a\u5931)',\r\n"
    u"                   _rlc['shrink_rank'], _rlc['pullback'] * 100, _rlc['offset']))\r\n"
    u"        # P2-6: \u6784\u5efa\u7eaa\u5f8b \u2014\u2014 \u6574\u8868\u622a\u65ad\u66ff\u6362(\u539f\u5b50\u5f15\u7528\u6362\u65b0\u5217\u8868), \u4e0d\u5c40\u90e8\u5220\u6539\r\n"
    u"        G.candidates = G.candidates[:MAX_DAILY_PICKS]\r\n",
    'R5 优选截断留痕'
)

# ---------- R6 公告覆盖缺口量化 ----------
rep_block(
    u"                if _cdays < _wd_decl:\r\n"
    u"                    log('[排雷][提示] 公告实扫仅%d天(%s~%s), 未达%d天窗口 \u2014\u2014 立案/处罚/'\r\n"
    u"                        '退市风险警示可能漏检, 需加大 --ann-pages'\r\n"
    u"                        % (_cdays, _annc['cover_from'], _annc['cover_to'], _wd_decl))\r\n",
    u"                if _cdays < _wd_decl:\r\n"
    u"                    # V2.6.97(4): 旧文案只说\u201c仅7天\u201d, 不给数量级 —— 2026-10-20 00:36 那次\r\n"
    u"                    #   ann=22 只 / 实扫 7 天, 单看这行很像\u201cann 类本来就少\u201d,\r\n"
    u"                    #   实际按同比推算 45 天应有约 141 只, 缺了约 119 只的拦截。\r\n"
    u"                    _ann_n = _cnt.get('ann', 0)\r\n"
    u"                    _ann_est = int(round(float(_ann_n) * _wd_decl / float(_cdays))) if _cdays > 0 else 0\r\n"
    u"                    log('[排雷][提示] 公告实扫仅%d天(%s~%s, 仅覆盖%d天窗口的%.0f%%), '\r\n"
    u"                        'ann类仅%d只; 同比推算%d天满覆盖约%d只, 缺约%d只 \u2014\u2014 '\r\n"
    u"                        '立案/处罚/退市风险警示可能漏检, 需加大 --ann-pages'\r\n"
    u"                        % (_cdays, _annc['cover_from'], _annc['cover_to'], _wd_decl,\r\n"
    u"                           _cdays * 100.0 / _wd_decl, _ann_n, _wd_decl, _ann_est,\r\n"
    u"                           max(_ann_est - _ann_n, 0)))\r\n",
    'R6 公告覆盖缺口量化'
)

# ---------- 写回 ----------
compile(src, P, 'exec')
out = src.encode('gbk')
io.open(P, 'wb').write(out)
t = out.decode('gbk')
print('写回: %d 行 / %d 字节 / CRLF=%d / MD5=%s'
      % (t.count('\r\n') + 1, len(out), out.count(b'\r\n'),
         hashlib.md5(out).hexdigest().upper()))
