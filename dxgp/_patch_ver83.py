# -*- coding: utf-8 -*-
"""V2.6.83 版本升级：文件头插入版本记录行 + VERSION 常量同步。
仅新增一行头注释 + 改一行常量，不触碰任何交易逻辑。
"""
import io
import sys

P = 'zt_shrink_strategy_gbk.py'

NEW_LINE = (
    "版本号: V2.6.83              修改时间: 2026-10-19 22:40 "
    "(V2.6.83记录: 第十四轮零预设独立审计收尾 + 提前排雷功能上线, 用户确认\"全部干\" —— "
    "【一】P3 批次 22 项(拆分到 29 处代码改动)全部落地: "
    "1情绪预下载遇 NameError 时补 G.no_download 标记, 否则每轮反复尝试且日志无说明; "
    "2SENT_LAG_DAYS 只参与判断不参与裁剪, 情绪数据滞后天数形同虚设; "
    "3情绪线程启动失败文案误称\"退回同步取数\", 实际无同步兜底易误导; "
    "4_sent_roll 补注 ddof=0 口径, 防与样本标准差混淆; "
    "5删死字段 G.param_verify_note; "
    "6轮询守卫 5.0 秒硬编码改为 RUN_ROUND_GUARD_SEC 常量(新增定义于费率区), 与配置同源; "
    "7删 pyramid_add 内死变量 fee(算出即弃); "
    "8detect_confirm_entry/detect_ma5_break 的 continue 改 break, 指标序列单调, 无谓空转; "
    "9_pick_latest_fin_row 报告期单侧缺失容错(只有披露日或只有报告期均可判); "
    "10历史 ST 清单缺失时补强提醒(不再静默放行); "
    "11-14删 4 处死字段 G.vol_unit_confirmed 及 G.banner_note_date; "
    "15MARKET_CAP_CACHE_SEC 由 3600 收紧到 300, 盘中流通市值不再用一小时前旧值; "
    "16删常量 FEE_RATE_EST(与真实费率表冲突, 易被误用); "
    "17_prod_of 补 LOF 识别(15/16/18 开头), 费率档不再错配; "
    "18删死字段 G.hourly_buy_note/G.hourly_sell_note; "
    "19G.notify_ip_ok 由 set 改为 G.notify_lock(线程安全队列去重); "
    "20trigger_log 静默 pass 改为响亮打印(格式化失败不再无声); "
    "21save_state 备份日期改为\"成功才置位\", 失败允许当日重试(旧版失败也置位, 当日不再重试); "
    "22load_state 兼容旧 UTF-8 状态文件(UnicodeDecodeError 回退 GBK), 迁移不再因编码崩; "
    "23notify_enqueue/notify_drain 全程持 G.notify_lock; "
    "24BUY_MIN_ELAPSED_MIN 改为经 sent_param 取值, 参数面板生效; "
    "25abs_cap_left 价格无效返回 0.0(旧版返回 None 被当作\"不限制\", 等于放开全部仓位帽); "
    "26strategy_status_signature 整体持 G.state_lock(RLock 可重入, 不死锁); "
    "27atr_of/退潮过滤改用 _bardate_loose 容错取日期; "
    "28exit_price_needed 按 fee_profile(code) 分档取费率, 可转债卖用 FEE_CBOND_SELL_RATE, "
    "并以 net_pnl_if_sell 口径计算保本价(旧版一律按股票的万0.841 估算, 可转债/ETF 保本价失真); "
    "29新增 RUN_ROUND_GUARD_SEC=5.0 常量定义. "
    "【二】提前排雷功能(全新): "
    "新增配套工具 download_risk_exclude.py(纯标准库, 零依赖), 五源抓取 "
    "ST/临近解禁/大股东减持/业绩亏损/监管立案处罚, 输出 zt_shrink_risk_exclude.json; "
    "策略侧新增 risk_exclude_path/_risk_exclude_candidates/load_risk_exclude/risk_excluded 四函数, "
    "每日装载一次、结构校验、清单过期强提醒但仍拦截(偏紧不放松), "
    "在选股层 excluded() 与发单前 buy_stock/pyramid_add 形成双重拦截; "
    "只拦新增买入, 卖出与持仓管理完全不受影响(不违反\"绝不止损\"铁律); "
    "开关 RISK_EXCLUDE_ON 默认开启. "
    "【三】排雷装载缺陷修补(自查发现): "
    "旧写法把\"装载动作执行过\"当作\"装载成功\"锁定当日, 若先启策略后跑工具, "
    "当天清单为空且全天不再重试(空窗一整天); 现改为只有真正读到非空清单才置 G.risk_ex_date, "
    "空清单不锁定并 60 秒节流重试. "
    "本次不改任何买卖判据、止盈口径、仓位约束与费用口径; 坚决不止损铁律原样保留, "
    "股票移交人工处理后同时释放股票额度与资金额度原样保留.)"
)

src = open(P, 'rb').read()
text = src.decode('gbk')
lines = text.split('\r\n')

# 定位当前版本行(L5 附近): 必须是 '版本号: V2.6.82'
idx = None
for i in range(0, 12):
    if lines[i].startswith('版本号: V2.6.82'):
        idx = i
        break
if idx is None:
    print('FAIL: 未找到 V2.6.82 版本行')
    sys.exit(1)
print('OK 版本行定位: line %d' % (idx + 1))

# 定位 VERSION 常量
vidx = None
for i, l in enumerate(lines):
    if l.startswith("VERSION = 'V2.6.82'"):
        vidx = i
        break
if vidx is None:
    print('FAIL: 未找到 VERSION 常量')
    sys.exit(1)
print('OK VERSION 定位: line %d' % (vidx + 1))

# 倒序应用: 先改后面的 VERSION, 再插前面的版本行
lines[vidx] = "VERSION = 'V2.6.83'    # 当前版本号(与启动日志和横幅展示一致; 改版需同步文件头版本注释)"
lines.insert(idx, NEW_LINE)

out = '\r\n'.join(lines)
assert out.count('\r\n') == len(lines) - 1, 'CRLF 计数异常'
# 语法熔断
try:
    compile(out.replace('#coding:gbk', '#coding:utf-8'), P, 'exec')
except SyntaxError as e:
    print('FAIL 语法: %s' % e)
    sys.exit(2)
out.encode('gbk')     # 编码熔断
open(P, 'wb').write(out.encode('gbk'))
print('OK: 插入 1 行版本记录 + 改 VERSION, lines %d -> %d' % (len(lines) - 1, len(lines)))
