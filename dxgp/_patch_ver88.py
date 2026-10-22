# -*- coding: utf-8 -*-
"""V2.6.88 升版: 版本记录 + VERSION 常量 + 心跳注释口径"""
P = 'zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
t = t.replace('\r\n', '\n')
lines = t.split('\n')

assert lines[4].startswith('版本号: V2.6.87'), lines[4][:40]
assert lines[337].startswith("VERSION = 'V2.6.87'"), lines[337][:40]

# 1) 心跳段注释与新行为对齐(原写"写失败静默")
old_c = '# 1) 写自己的心跳(原子替换, 写失败静默 —— 心跳不是交易必需)'
n = sum(1 for l in lines if old_c in l)
assert n == 1, n
lines = [('# 1) 写自己的心跳(原子替换; 首次启动失败会显式提示, 其余轮次静默 —— 心跳不是交易必需)'
          if old_c in l else l) for l in lines]

REC = (
    "版本号: V2.6.88              修改时间: 2026-10-19 22:55 "
    "(V2.6.88记录: 客户端 V2.6.87 首份实盘启动日志(22:42:34~22:43:14)逐行复核, 用户回\"改\"四项全改 —— "
    "【1】换手率闸门 100% 失效(真问题, 已修): 日志\"换手率不符0(字段缺失121)\"——进入判定的 121 只全部取不到换手率。"
    "根因: QMT get_market_data_ex 日线结果里没有 turnover / turnover_ratio 两列, load_history 写进 rows 的换手率恒为 0, "
    "判定随之落到\"缺失即放行\"分支, 于是 ZT_TURNOVER_MIN=0.05 / ZT_TURNOVER_MAX=0.20 自上线起一次都没生效: "
    "一字板(换手<5%)与过热出货(>20%)全部被放行进候选(按当日基准量反推, 603466 风语筑基准日换手量级约30%, 本应被 20% 上限剔除)。"
    "现新增 _float_share(取 CirculatingVolume/FloatVolume/FloatVolumn, 与 _float_market_cap_yi 同口径, 缓存1小时), "
    "字段缺失时自算 换手率 = 成交量(手) x DAILY_VOL_UNIT / 流通股本(股); 两路都取不到才按\"缺失放行\"(不误杀)。"
    "漏斗该行改为\"换手率不符N(自算X/缺失放行Y)\"并新增 st_turnover_calc。风险: 闸门首次真正生效, 候选会变少甚至为0, "
    "属恢复设计意图; ZT_TURNOVER_MIN/MAX 数值未动(参数指纹不变), 仅代码逻辑变更(版本指纹变)。 "
    "【2】心跳启动自证: 旧版心跳全程无日志, 在跑/写失败都看不出来(本次核对只能靠人翻 bin.x64 数 json 文件), "
    "现 after_init 强制首检时打\"[安全] 心跳已就绪: 文件 PID 检测间隔\", 写失败打\"[安全][提示] 心跳文件写入失败\"。 "
    "【3】亏损筛选文案: \"按亏损筛选剔除12只\"与漏斗\"避雷风险12\"是同一批(亏损筛选并入 st_risk 计数), "
    "旧文案读起来像两批共24只; 改为\"其中财务亏损剔除N只(... 已计入上方漏斗\\\"避雷风险\\\", 不重复扣除)\"。 "
    "【4】漏斗\"基准量不足N\"数字贴中文, 改为\"基准量不足 N\"。 "
    "核对结论(未改项): 漏斗账目自洽(5222->121->46->34->9->优选2 逐环可验, 亏损筛选剩余表恰34行); "
    "心跳文件仅1个(PID 18792/V2.6.87), 22:42 之后为单实例; 排雷清单 zt_shrink_risk_exclude* 仍不存在(待用户部署); "
    "铁律(绝不止损/扣费净利为正才卖/移交释放双额度)未触碰。)"
)
lines.insert(4, REC)

for i, l in enumerate(lines):
    if l.startswith("VERSION = 'V2.6.87'"):
        lines[i] = l.replace("VERSION = 'V2.6.87'", "VERSION = 'V2.6.88'", 1)
        break
else:
    raise AssertionError('VERSION 常量未找到')

t = '\n'.join(lines).replace('\n', '\r\n')
open(P, 'wb').write(t.encode('gbk'))
compile(t, P, 'exec')
print('OK V2.6.88 升版, 行数 %d, 版本记录 %d 条, 字节 %d'
      % (len(lines), sum(1 for l in lines if l.startswith('版本号: V')), len(t.encode('gbk'))))
