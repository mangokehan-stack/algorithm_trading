# -*- coding: utf-8 -*-
"""全文件关键使用点扫描（只读）。输出 UTF-8 结果文件供细读。
覆盖：import/数据通道(xtquant/xtdata/akshare/requests/urllib)、passorder 下单、
止损、回测/模拟撮合、心跳/双实例/单例锁、版本号引用、情绪累积池/排雷清单关键词。
"""
import io
import os
import re

BASE = r"E:\桌面\666666\dxgp"
SRC = os.path.join(BASE, "zt_shrink_strategy_gbk.py")
OUT = os.path.join(BASE, ".audit_20261021", "scan_all.txt")

raw = open(SRC, "rb").read()
text = raw.decode("gbk")
lines = text.splitlines()

buf = io.StringIO()

def dump(title, regex, flags=re.I, max_ctx=0, ctx_before=0, ctx_after=0, cap=400):
    buf.write("\n" + "=" * 100 + "\n")
    buf.write("[%s]\n" % title)
    buf.write("=" * 100 + "\n")
    pat = re.compile(regex, flags)
    n = 0
    for i, ln in enumerate(lines, 1):
        if pat.search(ln):
            n += 1
            if n > cap:
                buf.write("... (超出 %d 条, 截断)\n" % cap)
                break
            buf.write("L%05d: %s\n" % (i, ln.strip()[:220]))
            if ctx_after:
                for j in range(i + 1, min(len(lines) + 1, i + ctx_after + 1)):
                    buf.write("   L%05d| %s\n" % (j, lines[j - 1].strip()[:180]))
    buf.write("小计: %d 条\n" % n)

# 1. import 语句
dump("import 语句", r"^\s*import\s+\S+\s*$|^\s*from\s+\S+\s+import\s+\S+\s*$")

# 2. 数据通道关键字
dump("xtquant / xtdata 使用点", r"xtquant|xtdata")
dump("akshare 使用点", r"akshare|ak\.")
dump("requests / urllib / socket / http 使用点", r"requests\.|urllib|http\.|socket\.|httpx")
dump("内置行情接口 C. / G.C 调用(行情/交易)", r"\bC\.\w+|G\.C\." )

# 3. 下单与交易
dump("passorder / 下单", r"passorder|order\.send|send_order|insert_order|下单")
dump("撤单", r"cancel|撤单", max_ctx=0)

# 4. 止损相关（铁律核查）
dump("止损相关词", r"止损|stop_loss|stoploss|强制平仓|清仓")
dump("卖出条件(盈利才卖/费用)", r"net_pnl_if_sell|is_at_loss|min_profit_pct|fee_sell|DYN_PROFIT_FEE|SELL_MIN_PROFIT_PCT|绝不止损")

# 5. 回测 / 模拟撮合
dump("回测 / 模拟撮合", r"回测|backtest|_sim_|simulate|模拟")

# 6. 心跳 / 双实例 / 单例锁
dump("心跳 / 双实例 / 单例锁", r"heartbeat|心跳|单例|双实例|lock|Lock|互斥|pid|PID|instance")

# 7. 版本号引用
dump("版本号引用", r"V2\.6\.\d+|VERSION")

# 8. 情绪累积池 / 排雷清单
dump("情绪累积池相关", r"_SENT_ACC|累积池|_sent_acc|跨代恢复")
dump("排雷清单相关", r"排雷|排雷清单|雷")
dump("黑名单相关", r"blacklist|黑名单")

# 9. 策略限定投资金额
dump("投资金额限制", r"STRATEGY_CASH_CAP|TARGET_BUY_AMOUNT|FIXED_BUY_VOL|MAX_DAILY_BUYS|MAX_POSITIONS|MIN_BUY_AMOUNT|资金额度|金额")

with open(OUT, "w", encoding="utf-8") as f:
    f.write(buf.getvalue())

print("scan done, lines=%d, out=%s" % (len(lines), OUT))