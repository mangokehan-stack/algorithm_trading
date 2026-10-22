# -*- coding: utf-8 -*-
"""V2.6.84: 文件头插入版本记录 + VERSION 常量同步。仅注释与常量, 不碰交易逻辑。"""
import sys

P = 'zt_shrink_strategy_gbk.py'

NEW_LINE = (
    "版本号: V2.6.84              修改时间: 2026-10-19 22:10 "
    "(V2.6.84记录: 排雷模块启动日志口径纠偏, 用户确认\"改\" —— 原\"[排雷] 未发现排雷清单文件(可选功能)\""
    "一处文案带出三重误导: "
    "①说\"可选功能\", 但 RISK_EXCLUDE_ON 实为 True, 功能本是开着的, 只是清单文件没生成; "
    "用户看到\"可选\"会以为没启用, 于是永远不去补清单, 排雷等于永久空转; "
    "②没提\"生成清单后自动装载、无需重启策略\"(这恰是 V2.6.83 修掉\"装载失败也锁定当日\"带来的能力), "
    "用户会误以为要等次日才生效; "
    "③文件存在但 stocks 为空时也走同一个 else 分支, 把\"清单为空\"误报成\"文件不存在\", "
    "排查方向直接跑偏(去翻目录而不是看工具输出)。 "
    "现拆为三种情形分别输出: 文件不存在=醒目[待办]两行, 写明开关已开启、今日仅靠实时闸门、"
    "运行 download_risk_exclude.py 后自动装载无需重启; 文件存在但清单为空=单独[提示], "
    "引导确认工具输出是否正常; 解析失败=保留原[告警]+pnl_alert 强推送。 "
    "三种提示均改为每日一次(G.risk_ex_note_date 去重), 防止 60 秒节流重试在盘中反复刷屏; "
    "60 秒重试装载逻辑本身不变, 清单随时生成仍当轮生效。 "
    "本次仅改日志文案与输出频次, 不改变清单解析规则、风险拦截判据、买入/卖出逻辑; "
    "坚决不止损铁律与\"移交人工后同时释放股票额度与资金额度\"逻辑原样保留.)"
)

raw = open(P, 'rb').read()
lines = raw.decode('gbk').split('\r\n')
n0 = len(lines)


def find(pred, desc, lo=0, hi=None):
    hi = hi if hi is not None else len(lines)
    hits = [i for i in range(lo, hi) if pred(lines[i])]
    if len(hits) != 1:
        print('FAIL 定位[%s]: %d 处 -> %r' % (desc, len(hits), [h + 1 for h in hits]))
        sys.exit(1)
    return hits[0]


i_hdr = find(lambda l: l.startswith('版本号: V2.6.83'), 'V2.6.83 版本行', 0, 12)
i_ver = find(lambda l: l.startswith("VERSION = 'V2.6.83'"), 'VERSION 常量')
print('OK 版本行 L%d / VERSION L%d' % (i_hdr + 1, i_ver + 1))

lines[i_ver] = "VERSION = 'V2.6.84'    # 当前版本号(与启动日志和横幅展示一致; 改版需同步文件头版本注释)"
lines.insert(i_hdr, NEW_LINE)

out = '\r\n'.join(lines)
assert out.count('\r\n') == len(lines) - 1, 'CRLF 计数异常'
try:
    compile(out.replace('#coding:gbk', '#coding:utf-8'), P, 'exec')
except SyntaxError as e:
    print('FAIL 语法: %s line %s' % (e, e.lineno))
    sys.exit(2)
out.encode('gbk')
open(P, 'wb').write(out.encode('gbk'))
print('OK: 插入 1 行版本记录 + 改 VERSION, lines %d -> %d' % (n0, len(lines)))
