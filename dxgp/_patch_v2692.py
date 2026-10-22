# -*- coding: utf-8 -*-
"""V2.6.92 补丁: 排雷清单链路收口(用户回"2 + 3 + 5 → 1 → 6 + 7")

【6 当日重载】load_risk_exclude 旧版 G.risk_ex_date==G.today 直接返回缓存,
  当天重跑工具生成的新清单要等次日或重启才生效, 与文案"生成后自动装载, 无需重启"矛盾。
  -> 比对 (路径, mtime, 大小) 指纹, 变了当日重载; stat 60 秒节流;
     重载失败时沿用更新前旧表(绝不用空表覆盖已生效清单)。
【7 数据源健康】装载日志新增 sources 失败告警 + 公告实扫天数比对, 让"st 源挂了"可见。

设计纪律: 不新增任何模块级大写常量(否则参数指纹漂移, verified_fp 比对失效),
  新增状态一律挂在 G 上(小写属性), 新增函数用小写+下划线前缀。
"""
import hashlib
import io
import os
import re
import shutil

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
BAK = r'E:\桌面\666666\dxgp\_baseline\V2.6.91.py'

HDR = (u'版本号: V2.6.92              修改时间: 2026-10-20 00:05 '
       u'(V2.6.92记录: 用户回"2 + 3 + 5 → 1 → 6 + 7", 排雷清单链路收口 —— 起因是 '
       u'2026-10-19 23:31 工具首跑日志(594只)的逐行复核, 暴露"清单生成了但策略看不到真相"。'
       u'【0 病因】生成端把"st 源失败"只写进 JSON 的 sources/errors, 策略侧 load_risk_exclude '
       u'只读 stocks/asof, 于是日志"[排雷] 已装载...st=35"看着像 ST 已全覆盖, 实际 35 只全是'
       u'公告简称兜底(本地权威名单 145 只, 真实覆盖 24%); 同理 ann 只扫到 4 天、却显示 [OK]。'
       u'【6】当日重载: 旧版 G.risk_ex_date==G.today 直接返回缓存, 当天重跑工具生成的新清单'
       u'要等次日或重启才生效, 与"生成后自动装载无需重启"自相矛盾(实测 23:31 重跑, 策略仍读 '
       u'23:24 那份); 现比对 (路径,mtime,大小) 指纹, 变了当日重载, stat 60 秒节流, 重载失败时'
       u'沿用更新前旧表(绝不用空表覆盖已生效清单)。【7】数据源健康: 装载日志新增'
       u'"清单生成时N类数据源失败: st:RemoteDisconnected —— 覆盖不全, 不等于该类无风险", '
       u'并 pnl_alert 每日一次; 另把公告实扫天数(cover_from~cover_to)与 window_days 比对, '
       u'不足则提示立案/处罚漏检。工具侧同步(download_risk_exclude.py): 920xxx 补 .BJ 后缀'
       u'(北交所漏排)、公告"最近五年未被…"合规说明句过滤(实测 13 只中 5 只假阳性)、'
       u'解禁市值 0.0亿→<0.1亿/市值未知、公告覆盖区间实打实打印(--ann-pages 默认 60)、'
       u'完成行补账目自洽(594只/612标签/18只重叠)。')

NEW_G = """G.risk_ex_try_ts = 0.0         # V2.6.83: 清单缺失时的上次尝试时间(60秒节流重试, 使当日补跑工具可即时生效)
G.risk_ex_sig = None             # V2.6.92: 已装载清单的文件指纹(路径,mtime,大小); 变了=当日重载
G.risk_ex_stat_ts = 0.0          # V2.6.92: 指纹比对节流(60秒), 避免选股循环里每只票都 stat
G.risk_ex_src_warn_date = ''     # V2.6.92: 数据源健康告警日(每日一次), 防刷屏"""

NEW_HELPER = '''def _risk_ex_sig_of(path):
    """V2.6.92新增: 清单文件指纹 (路径, mtime整秒, 字节数); 取不到返回 None。
    用途: "当日已装载"不再等于"当天不再看文件" —— 工具随时可以重跑, 指纹变了就重装。"""
    try:
        _st = os.stat(path)
        return (str(path), int(_st.st_mtime), int(_st.st_size))
    except Exception:
        return None


def _risk_ex_cur_sig():
    """V2.6.92新增: 按 candidates 顺序取第一个存在文件的指纹(与装载顺序保持一致)。"""
    for _c in _risk_exclude_candidates():
        _sg = _risk_ex_sig_of(_c)
        if _sg is not None:
            return _sg
    return None


def risk_exclude_path():'''

NEW_RELOAD = '''    if G.risk_ex_date == G.today:
        # V2.6.92: 旧版此处直接返回当日缓存 —— 当天重跑工具生成的新清单不会生效, 只能等次日
        #   或重启, 与"生成后自动装载, 无需重启"自相矛盾(实测 23:31 重跑后策略仍读 23:24 那份)。
        #   现比对 (路径, mtime, 大小) 指纹: 变了就当日重载; 指纹比对本身 60 秒节流, 不拖慢选股。
        if time.time() - _f(getattr(G, 'risk_ex_stat_ts', 0.0)) < 60.0:
            return G.risk_ex if isinstance(G.risk_ex, dict) else {}
        G.risk_ex_stat_ts = time.time()
        _cur_sig = _risk_ex_cur_sig()
        if _cur_sig is None or _cur_sig == getattr(G, 'risk_ex_sig', None):
            return G.risk_ex if isinstance(G.risk_ex, dict) else {}
        log('[排雷] 清单文件已更新(%s), 当日重新装载'
            % (os.path.basename(_cur_sig[0]) if _cur_sig[0] else '?'))
        _reload = True
        G.risk_ex_date = ''      # 放行到下方装载流程; 重载失败则由 _prev 兜底
    data, used, err = {}, '', \'\''''

NEW_PREV = '''    if not RISK_EXCLUDE_ON:
        return {}
    _prev = G.risk_ex if isinstance(getattr(G, 'risk_ex', None), dict) else {}
    _reload = False      # V2.6.92: 本次是否为"当日清单文件更新后的重载"(失败时保留旧表)'''

NEW_CYC = '''    _src, _src_errs, _wd_decl = {}, [], 0    # V2.6.92: 生成端的数据源健康信息
    for cand in _risk_exclude_candidates():'''

NEW_FOUND = '''            _found = True      # V2.6.84: 文件已成功打开且解析出 stocks 字典(内容可能为空)
            # V2.6.92: 记下生成端写的数据源健康信息(旧版只读 stocks, 这几项被整体忽略)
            _sj = j.get('sources')
            if isinstance(_sj, dict):
                _src = _sj
            _se = j.get('errors')
            if isinstance(_se, list):
                _src_errs = [str(x)[:80] for x in _se[:5]]
            try:
                _wd_decl = int(j.get('window_days') or 0)
            except Exception:
                _wd_decl = 0'''

NEW_KEEP = '''    # V2.6.92: 当日重载失败(文件更新后损坏)绝不能用空表覆盖已生效的旧表 —— 否则排雷静默失效
    if _reload and not data and _prev:
        data = dict(_prev)
        err = (err + '; ' if err else '') + '清单更新后解析失败, 沿用更新前旧表'
    G.risk_ex = data
    if data:
        G.risk_ex_date = G.today'''

NEW_LOG = """        log('[排雷] 已装载提前排雷清单%d只(%s) 文件=%s'
            % (len(data), ', '.join('%s=%d' % (k, v) for k, v in sorted(_cnt.items())) or '-',
               os.path.basename(used) if used else u'(沿用旧表)'))
        # V2.6.92: 数据源健康 —— 生成端只把失败写进 JSON 的 sources/errors, 策略旧版压根不读,
        #   于是"st 源挂了、st=35 只来自公告简称兜底"在策略日志里完全看不出来, 看着像 ST 全覆盖。
        _bad = [k for k, v in _src.items() if isinstance(v, dict) and v.get('ok') is False]
        if _bad:
            _bdet = ', '.join('%s:%s' % (k, str((_src.get(k) or {}).get('err') or '失败')[:40])
                              for k in _bad)
            log('[排雷][告警] 清单生成时%d类数据源失败: %s —— 这些类别覆盖不全, 不等于'
                '"该类无风险"; 请重跑 download_risk_exclude.py' % (len(_bad), _bdet))
            if getattr(G, 'risk_ex_src_warn_date', '') != G.today:
                G.risk_ex_src_warn_date = G.today
                try:
                    pnl_alert('[排雷][告警] 清单数据源失败: %s' % _bdet)
                except Exception:
                    pass
        elif _src_errs:
            log('[排雷][告警] 清单生成端报错: %s' % ('; '.join(_src_errs))[:160])
        _annc = _src.get('ann') if isinstance(_src, dict) else None
        if isinstance(_annc, dict) and _annc.get('cover_from') and _annc.get('cover_to') \\
                and _wd_decl > 0:
            try:
                _cfrom = datetime.datetime.strptime(str(_annc['cover_from']), '%Y-%m-%d').date()
                _cto = datetime.datetime.strptime(str(_annc['cover_to']), '%Y-%m-%d').date()
                _cdays = (_cto - _cfrom).days + 1
                if _cdays < _wd_decl:
                    log('[排雷][提示] 公告实扫仅%d天(%s~%s), 未达%d天窗口 —— 立案/处罚/'
                        '退市风险警示可能漏检, 需加大 --ann-pages'
                        % (_cdays, _annc['cover_from'], _annc['cover_to'], _wd_decl))
            except Exception:
                pass"""

EDITS = [
    ('版本头新增V2.6.92行', r'^版本号: V2\.6\.91', re.M, HDR + u'\n版本号: V2.6.91'),
    ('VERSION常量', r"^VERSION = 'V2\.6\.91'", re.M, "VERSION = 'V2.6.92'"),
    ('G新增三个小写状态', r'^G\.risk_ex_try_ts = 0\.0 .*$', re.M, NEW_G),
    ('新增指纹工具函数', r'^def risk_exclude_path\(\):$', re.M, NEW_HELPER),
    ('当日已装载改为按指纹重载',
     r'^    if G\.risk_ex_date == G\.today:\n'
     r'        return G\.risk_ex if isinstance\(G\.risk_ex, dict\) else \{\}\n'
     r"    data, used, err = \{\}, '', ''$", re.M, NEW_RELOAD),
    ('装载前记录旧表与重载标记',
     r'^    if not RISK_EXCLUDE_ON:\n        return \{\}$', re.M, NEW_PREV),
    ('装载循环前声明sources变量', r'^    for cand in _risk_exclude_candidates\(\):$', re.M, NEW_CYC),
    ('解析成功处记录sources与指纹', r'^            _found = True      # V2\.6\.84: .*$', re.M, NEW_FOUND),
    ('重载失败不得用空表覆盖',
     r'^    G\.risk_ex = data\n    if data:\n        G\.risk_ex_date = G\.today', re.M, NEW_KEEP),
    ('装载日志补数据源健康',
     r"^        log\('\[排雷\] 已装载提前排雷清单%d只\(%s\) 文件=%s'\n"
     r"            % \(len\(data\), .*\n"
     r"               os\.path\.basename\(used\)\)\)$", re.M, NEW_LOG),
]


def main():
    raw = io.open(P, 'rb').read()
    txt = raw.decode('gbk')
    crlf = txt.count('\r\n')
    lf_only = txt.count('\n') - crlf
    print('原始: %d 字节 / CRLF=%d / 纯LF=%d' % (len(raw), crlf, lf_only))
    if lf_only:
        raise SystemExit('[中止] 源文件存在非CRLF换行, 先人工确认, 避免整文件换行被改写')

    t = txt.replace('\r\n', '\n')
    for name, pat, flags, new in EDITS:
        n = len(re.findall(pat, t, flags))
        if n != 1:
            raise SystemExit('[中止] 锚点不唯一/未命中: %s (count=%d)' % (name, n))
        t = re.sub(pat, lambda m: new, t, count=1, flags=flags)
        print('  [OK] %-28s 1处' % name)

    out = t.replace('\n', '\r\n')
    if out.count('\r\n') != out.count('\n'):
        raise SystemExit('[中止] 存在非CRLF换行残留')
    compile(out, P, 'exec')
    print('  [OK] compile() 通过, 行数 %d -> %d(新增%d行), 全部CRLF'
          % (crlf, out.count('\n'), out.count('\n') - crlf))

    if not os.path.exists(BAK):
        shutil.copy2(P, BAK)
        print('  [OK] 备份 -> %s' % BAK)
    io.open(P, 'wb').write(out.encode('gbk'))
    nb = io.open(P, 'rb').read()
    print('完成: %d 字节 / MD5 %s' % (len(nb), hashlib.md5(nb).hexdigest()))


if __name__ == '__main__':
    main()
