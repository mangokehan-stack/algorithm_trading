# -*- coding: utf-8 -*-
"""V2.6.92 -> V2.6.93 补丁: 纯日志可读性三项(不改交易/取数行为)

1) 排雷装载告警: 重复 + 异常文本截断
2) 沿用旧信号: 打印实际参数覆写(哪个参数/从多少到多少/方向)
3) 取数预算: 补批数、均秒每批、实际耗时与常态倍数

约定: 全部为局部变量/日志文案, 不新增大写常量(参数指纹必须仍是 8a4ab7e8)。
"""
import io
import os
import shutil
import time

P = 'zt_shrink_strategy_gbk.py'
BAK = os.path.join('_baseline', 'V2.6.92.py')

HDR = (u'版本号: V2.6.93              修改时间: 2026-10-20 00:20 '
       u'(V2.6.93记录: 用户回"1 + 2 + 3(纯日志, 零风险)先做", 三项全是日志可读性, '
       u'不改任何交易/取数与风控行为 —— 起因是 2026-10-19 23:44 V2.6.92 首份实跑日志。'
       u'【1 排雷告警重复且截断】装载时 log 与 pnl_alert 打同一件事, 而 pnl_alert 也写同一份 '
       u'run.log, 于是两条告警挨着出现, 读起来像"生成失败一次 + 加载又失败一次"两次故障; '
       u'且 err 取前40字符把 RemoteDisconnected(\'Remote end closed connection without response\') '
       u'切成 "Remote end closed co", 引号不闭合像乱码。改: 异常文本优先取类名(新增 '
       u'_risk_src_err_short), 推送副本改为只报类别并注明"本条是上一行的推送副本"。'
       u'【2 沿用旧信号不报覆写值】23:38 那轮取数只覆盖 23.0% 被拒, 沿用 20261016 的 '
       u'sentiment=-1.27 / regime=panic, 而日志只有一句"档位/覆写仍生效"; 实际 panic 档覆写是 '
       u'SHRINK_BUY_RATIO=0.30 + BUY_MIN_ELAPSED_MIN=45, 等于次日按"更难买"的档跑却看不出来。'
       u'改: 沿用分支复用 _sent_override_note 打印"哪个参数 从多少 到多少(方向)", 无覆写也明说。'
       u'【3 预算超出无解释】23:38 那轮耗时 195 秒 > 预算 180 秒; 预算只在批间检查、单批 300 只'
       u'接口调用不可中断, 真实上限是"预算+最后一批耗时"。改: 告警补 批数/均秒每批/实际耗时/'
       u'相对常态(约2秒每批)的倍数。三项均为局部变量与文案, 未新增大写常量, 参数指纹仍 8a4ab7e8。)')

HELPER = [
    u'def _risk_src_err_short(e):',
    u'    # V2.6.93(1): 数据源异常压成一行可读文本。旧写法统一取 err 前 40 字符, 于是',
    u'    #   RemoteDisconnected(\'Remote end closed connection without response\') 被切成',
    u'    #   "RemoteDisconnected(\'Remote end closed co" —— 引号不闭合, 日志里像乱码, 也看不出',
    u'    #   到底是哪类异常(连接被对端关闭 / 超时 / 解析失败)。现在优先取异常类名, 只有拿不到',
    u'    #   类名(纯文本报错)时才按 40 字符截断并加 "...", 保证读者一眼能分类。',
    u'    try:',
    u'        _s = str(e or \'\').strip()',
    u'    except Exception:',
    u'        return \'失败\'',
    u'    if not _s:',
    u'        return \'失败\'',
    u'    _cls = _s.split(\'(\')[0].strip()',
    u'    if _cls and _cls != _s and len(_cls) <= 40:',
    u'        return _cls',
    u'    if len(_s) > 40:',
    u'        return _s[:40] + \'...\'',
    u'    return _s',
    u'',
    u'',
]

BDET_OLD = [
    u"            _bdet = ', '.join('%s:%s' % (k, str((_src.get(k) or {}).get('err') or '失败')[:40])",
    u"                              for k in _bad)",
]

BDET_NEW = [
    u'            # V2.6.93(1): 两处文案修复。①截断: 旧写法取 err 前 40 字符, 把',
    u'            #   RemoteDisconnected 的整句切在半个单词上, 引号还不闭合; 现在走',
    u'            #   _risk_src_err_short(优先异常类名)。②重复: 下面 pnl_alert 与本行内容',
    u'            #   几乎一致, 而 pnl_alert 也写同一份 run.log —— 2026-10-19 23:44 的日志里',
    u'            #   两条告警紧挨着, 像"生成清单失败 + 装载清单失败"两次故障, 实际只有一次。',
    u"            _bdet = ', '.join('%s:%s' % (k, _risk_src_err_short((_src.get(k) or {}).get('err')))",
    u'                              for k in _bad)',
]

ALERT_OLD = [
    u"                    pnl_alert('[排雷][告警] 清单数据源失败: %s' % _bdet)",
]

ALERT_NEW = [
    u"                    pnl_alert('[排雷][告警] 清单生成时%d类数据源失败(%s), 覆盖不全; '",
    u"                              '本条是上一行日志的推送副本, 不是第二次故障'",
    u'                              % (len(_bad), \',\'.join(_bad)))',
]

CARRY_ANCHOR = u"            _sent_wlog('[告警] %s; 已沿用上一次成功信号(数据日=%s sentiment=%.2f regime=%s), '"

CARRY_TAIL = u"                       % (why, _d, _f(_g.get('sentiment')), _g.get('regime')))"

CARRY_ADD = [
    u'            # V2.6.93(2): 旧版只说"档位/覆写仍生效", 从不写覆写成了什么。实测',
    u'            #   2026-10-19 23:38 沿用 20261016 的 sentiment=-1.27 / regime=panic,',
    u'            #   而 panic 档覆写 = SHRINK_BUY_RATIO 0.30 + BUY_MIN_ELAPSED_MIN 45,',
    u'            #   等于次日按"缩量要求更严 + 开盘要等45分钟"跑, 买点大概率全被卡掉,',
    u'            #   日志里却只有"覆写仍生效"这种零信息量的话。现在把覆写翻译成人话:',
    u'            #   哪个参数、从多少到多少、往哪个方向偏。',
    u'            _ovc = _sent_override_note(_g.get(\'overrides\') or {})',
    u'            if _ovc:',
    u'                _sent_wlog(\'       沿用信号携带的参数覆写(%s档): %s —— 若这不是你要的口径, \'',
    u'                           \'请先修好行情接口让取数恢复, 或临时把 _SENTIMENT_ON 置 False\'',
    u'                           % (_g.get(\'regime\'), _ovc))',
    u'            else:',
    u'                _sent_wlog(\'       沿用信号未携带参数覆写(%s档): 按策略默认参数跑\'',
    u'                           % (_g.get(\'regime\'),))',
]

BUDGET_OLD = [
    u'        if _budget_hit:',
    u"            _sent_wlog('[告警] 情绪取数触发总预算(%d秒): 已取到%d只/请求%d只即中止, 余下%d只'",
    u"                       '本轮放弃 —— 正常应40秒内完成, 明显超时说明接口异常或拆批被放大'",
    u"                       % (int(_BUDGET_SEC), int(_cov['ok']), int(_cov['req']),",
    u"                          max(0, int(_cov['req']) - int(_cov['ok']))))",
]

BUDGET_NEW = [
    u'        if _budget_hit:',
    u'            # V2.6.93(3): 旧文案只说"触发180秒预算", 而实测 2026-10-19 23:38 那轮',
    u'            #   耗时 195 秒(超 15 秒) —— 预算只在批与批之间检查, 单批 300 只的接口调用',
    u'            #   不可中断, 所以真实上限是"180 + 最后一批耗时"。不给这层解释, 看到',
    u'            #   195 > 180 只会怀疑预算失效或日志算错。同时给出 均X秒/批 与常态',
    u'            #   (约2秒/批, 全场约40秒)的对比倍数, 一眼分清是"接口慢了"还是"参数问题"。',
    u'            _el_bg = time.time() - _t_beg',
    u'            _per_b = (_el_bg / _nb_ok) if _nb_ok > 0 else 0.0',
    u'            _slow = (_per_b / 2.0) if _per_b > 0 else 0.0',
    u"            _sent_wlog('[告警] 情绪取数触发总预算(%d秒): 已取到%d只/请求%d只即中止'",
    u"                       '(%d批x300只, 均%.0f秒/批), 余下%d只本轮放弃 —— 实际耗时%.0f秒:'",
    u"                       '预算只在批间检查、单批接口调用不可中断, 故真实上限是\"预算+最后一批\"; '",
    u"                       '常态约2秒/批(全场约40秒), 本轮慢%.0f倍 —— 优先查QMT行情接口/登录/多实例争用'",
    u"                       % (int(_BUDGET_SEC), int(_cov['ok']), int(_cov['req']),",
    u"                          _nb_ok, _per_b,",
    u"                          max(0, int(_cov['req']) - int(_cov['ok'])),",
    u"                          _el_bg, _slow))",
]


def main():
    raw = io.open(P, 'rb').read()
    txt = raw.decode('gbk')
    if txt.count('\r\n') != txt.count('\n'):
        raise SystemExit('[中止] 文件不是全 CRLF, 先查清再改')
    L = txt.split('\r\n')
    n0 = len(L)
    print('原行数 %d' % n0)

    if not os.path.exists(BAK):
        shutil.copy(P, BAK)
        print('备份 -> %s' % BAK)

    # --- 1 版本头
    idx = [i for i, l in enumerate(L) if l.startswith(u'版本号: V2.6.92')]
    if len(idx) != 1:
        raise SystemExit('[中止] 版本头锚点 %d 处' % len(idx))
    L.insert(idx[0], HDR)
    print('  [OK] 版本头插入 V2.6.93')

    # --- 2 VERSION 常量
    idx = [i for i, l in enumerate(L) if l.startswith(u"VERSION = 'V2.6.92'")]
    if len(idx) != 1:
        raise SystemExit('[中止] VERSION 锚点 %d 处' % len(idx))
    L[idx[0]] = L[idx[0]].replace("'V2.6.92'", "'V2.6.93'")
    print('  [OK] VERSION -> V2.6.93')

    # --- 3 新增辅助函数(放在 load_risk_exclude 之前)
    idx = [i for i, l in enumerate(L) if l.startswith(u'def load_risk_exclude(')]
    if len(idx) != 1:
        raise SystemExit('[中止] load_risk_exclude 锚点 %d 处' % len(idx))
    L[idx[0]:idx[0]] = HELPER
    print('  [OK] 新增 _risk_src_err_short (%d 行)' % len(HELPER))

    # --- 4 _bdet
    hits = [i for i in range(len(L)) if L[i:i + 2] == BDET_OLD]
    if len(hits) != 1:
        raise SystemExit('[中止] _bdet 锚点 %d 处' % len(hits))
    L[hits[0]:hits[0] + 2] = BDET_NEW
    print('  [OK] _bdet 改用异常类名')

    # --- 5 推送副本
    hits = [i for i in range(len(L)) if L[i:i + 1] == ALERT_OLD]
    if len(hits) != 1:
        raise SystemExit('[中止] pnl_alert 锚点 %d 处' % len(hits))
    L[hits[0]:hits[0] + 1] = ALERT_NEW
    print('  [OK] 推送副本去掉重复错误串')

    # --- 6 沿用信号打印覆写
    hits = [i for i, l in enumerate(L) if l == CARRY_ANCHOR]
    if len(hits) != 1:
        raise SystemExit('[中止] 沿用日志锚点 %d 处' % len(hits))
    if L[hits[0] + 2].strip() != CARRY_TAIL.strip():
        raise SystemExit('[中止] 沿用日志结尾不匹配: %r' % L[hits[0] + 2])
    L[hits[0] + 3:hits[0] + 3] = CARRY_ADD
    print('  [OK] 沿用信号补覆写人话 (%d 行)' % len(CARRY_ADD))

    # --- 7 _nb_ok 计数
    a = u'        _budget_hit = False     # V2.6.90(1): 已耗尽总预算, 带已取到的部分收尾'
    hits = [i for i, l in enumerate(L) if l == a]
    if len(hits) != 1:
        raise SystemExit('[中止] _budget_hit 锚点 %d 处' % len(hits))
    L.insert(hits[0] + 1, u'        _nb_ok = 0   # V2.6.93(3): 已完成批数, 供预算告警算"均X秒/批"(局部变量, 不入指纹)')
    print('  [OK] 新增 _nb_ok 计数')

    b = u'                _md = _sent_fetch_md_batch(C, _batch, _fields, _start, _cnt, _box, 0)'
    hits = [i for i, l in enumerate(L) if l == b]
    if len(hits) != 1:
        raise SystemExit('[中止] _md 锚点 %d 处' % len(hits))
    L.insert(hits[0] + 1, u'                _nb_ok += 1')
    print('  [OK] 每批完成计数')

    # --- 8 预算告警文案
    hits = [i for i in range(len(L)) if L[i:i + len(BUDGET_OLD)] == BUDGET_OLD]
    if len(hits) != 1:
        raise SystemExit('[中止] 预算告警锚点 %d 处' % len(hits))
    L[hits[0]:hits[0] + len(BUDGET_OLD)] = BUDGET_NEW
    print('  [OK] 预算告警补批次数/均秒/倍数')

    out = '\r\n'.join(L)
    if out.count('\n') != len(L) - 1 or '\r\r' in out:
        raise SystemExit('[中止] 行尾异常')
    compile(out, P, 'exec')
    print('  [OK] compile() 通过, 行数 %d -> %d (+%d)' % (n0, len(L), len(L) - n0))

    io.open(P, 'wb').write(out.encode('gbk'))
    import hashlib
    d = io.open(P, 'rb').read()
    print('完成: %d 字节 / MD5 %s / %s'
          % (len(d), hashlib.md5(d).hexdigest().upper(),
             time.strftime('%Y-%m-%d %H:%M:%S')))


if __name__ == '__main__':
    main()
