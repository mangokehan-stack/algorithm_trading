# -*- coding: utf-8 -*-
"""V2.6.87 升版: 插入版本记录 + 改 VERSION 常量"""
P = 'zt_shrink_strategy_gbk.py'
lines = open(P, 'rb').read().decode('gbk').split('\r\n')

assert lines[4].startswith('版本号: V2.6.86'), lines[4][:40]
assert lines[336].startswith("VERSION = 'V2.6.86'"), lines[336][:40]

REC = (
    "版本号: V2.6.87              修改时间: 2026-10-19 22:45 "
    "(V2.6.87记录: 客户端 V2.6.86 实跑日志(22:25:53)复核, 用户确认\"全部做\" —— "
    "【1】批量取数失败整批丢弃且报错为空: sent_fetch_sync 每批300只失败只 continue, 该批300只直接消失, "
    "而完成日志打的是\"标的%d只\"=股票池长度; 实测18批里第5~18批全失败(仅剩1200只/23%), 日志仍显示满覆盖; "
    "且排序后前1200只全是000/001/002段(缺创业板/科创板/沪市/北交所), 涨跌广度与涨停占比被系统性带偏"
    "(同一数据日20261016: 18批全过时 sentiment=-1.27, 只剩4批时 -1.00)。现新增 "
    "_sent_fetch_md_batch: 失败自动拆 300->100->30 逐级重试, 成功/失败/拆分次数全部统计; "
    "异常文本改用 _exc_text(type+str+repr兜底), 不再出现\"第N批失败: \"后面一片空白; "
    "完成日志改为\"请求N只 成功M只(覆盖率x%) 失败K只 拆分重试T次\", 并输出最多3条失败样本。 "
    "【2B】覆盖率不足时沿用上一次成功信号(用户选B): 新增 SENT_COVERAGE_MIN=0.90 与 "
    "zt_shrink_sent_cache(账号隔离, 原子写)缓存; 覆盖率<90%时不采用残缺样本(残缺样本会按剩余分量"
    "重新归一化权重, 等于悄悄换了一条指数而阈值仍按3分量标定, 实测 -1.00 正卡在 panic 阈值 -1.0 上, "
    "档位会在临界点随机跳变), 改为 _sent_use_last_good 沿用上次信号; 无历史缓存或历史已过期"
    "(_sent_fresh_enough 不过)才降级中性; 沿用时不写 last_fetch_date, 保证 SENT_RETRY_SEC 继续"
    "节流重试真实数据(不能重蹈 V2.6.85\"降级即锁日\"的坑)。 "
    "【3】信号行补一行\"信号分量: 涨跌广度,涨停家数(2/3, 缺成交额 -> 权重已按剩余分量归一化, "
    "阈值仍按3分量标定)\", 旧版只打总 sentiment, 指数定义被悄悄改了也看不出来。 "
    "【4】启动横幅情绪就绪状态改三态(已就绪/取数中(后台线程)/尚未发起取数): 该行产生于 init 阶段, "
    "后台线程必然还没置位, 旧版固定打 ready=False, 与同一秒的\"信号刷新\"互相矛盾; 新增 "
    "SENT_STATE['fetching'] 在发起取数时置True、worker finally 无条件复位。 "
    "【5】双实例检测(只告警不阻断): 2026-10-19 22:25:55 已\"信号刷新\"(last_fetch_date 已写今天), "
    "11秒后又出现\"情绪取数已移交后台线程\", 单进程不可能(单测A1已证幂等), 只能是两个进程共写"
    "同一个 zt_shrink_run.log; 双实例会重复下单并互相覆盖状态文件/分批计划/额度。现每实例写独立心跳"
    "文件 zt_shrink_heartbeat_<账号>_<PID>.json(互不覆盖), 扫描同账号其它心跳 ts 仍在120秒内即判活跃, "
    "打[安全][告警]+手机强提醒(300秒最多一次), 同伴退出时提示恢复单实例; after_init 强制首检, "
    "timer_poll 每30秒节流检查。 "
    "【6】buy_stock 入参契约: 开头补 if _f(lp)<=0: return None —— 下方 int(amount/lp/_lot) 在 lp<=0 时"
    "除零崩溃, 崩溃点不在 try 内会中断整轮 timer_poll(买卖全停); 主循环虽已拦 lp<=0, 但函数级不应"
    "依赖调用方(将来新增调用点即踩坑)。 "
    "【自查】心跳扫描首版把循环变量写成 _f, 遮蔽模块级 float 转换函数 _f, 导致 _f(...) 抛 "
    "UnboundLocalError 又被 except 静默吞掉 —— 心跳\"看起来在检测实则永远检测不到同伴\"; "
    "已改为 _fn 并把探测异常改为显式提示(不再静默), 专项测试 T5c/T5h 由此从假通过转为真通过。)"
)
lines.insert(4, REC)

# VERSION 常量位置随插入后移 1 行
for i, l in enumerate(lines):
    if l.startswith("VERSION = 'V2.6.86'"):
        lines[i] = l.replace("VERSION = 'V2.6.86'", "VERSION = 'V2.6.87'", 1)
        break
else:
    raise AssertionError('VERSION 常量未找到')

t = '\r\n'.join(lines)
open(P, 'wb').write(t.encode('gbk'))
compile(t, P, 'exec')
print('OK V2.6.87 升版, 行数 %d, 版本记录 %d 条'
      % (len(lines), sum(1 for l in lines if l.startswith('版本号: V'))))
