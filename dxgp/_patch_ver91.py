# -*- coding: utf-8 -*-
"""V2.6.91 升版: 版本记录 + VERSION 常量"""
P = 'zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')
assert t.count('\r\n') == t.count('\n')
t = t.replace('\r\n', '\n')
lines = t.split('\n')

assert lines[4].startswith('版本号: V2.6.90'), lines[4][:40]

for i, l in enumerate(lines):
    if l.startswith("VERSION = 'V2.6.90'"):
        i_ver = i
        break
else:
    raise AssertionError('VERSION 常量未找到')
assert i_ver is not None

REC = (
    "版本号: V2.6.91              修改时间: 2026-10-19 23:26 "
    "(V2.6.91记录: 用户回\"改\", 落地三项 —— 前两项源自 2026-10-19 23:16 那份启动日志里被挖出的"
    "\"同一进程内两代代码并存\", 第三项是同一晚实测出的心跳节拍偏差。 "
    "【0 先讲清病因】QMT 里点\"停止/重新启动\"并不会杀掉已经创建的 threading.Thread。旧代脚本的取数线程"
    "带着旧代全局变量继续跑, 同时往同一个 zt_shrink_run.log 写日志; 新代在 after_init 后照常发起自己的取数。"
    "实证: 22:55:42(旧代)发起取数 -> 23:16:43 启动 V2.6.90(新代, PID 仍是 37300, 说明是同一 OS 进程内的"
    "脚本重载而不是两个进程) -> 23:17:04 打出\"内置通道取数完成 5226/5226\", 而新代此时还没发起过任何取数 -> "
    "23:17:11 新代又发起一次全量取数。旧代那一轮从 22:55:42 跑到 23:17:04, 共 21 分 22 秒。"
    "两代并行打同一个行情接口, 正是历史上\"18批里14批失败\"\"覆盖率只有23%\"的物理原因; 更麻烦的是旧代跑完"
    "会写 SENT_STATE 并打一行\"取数完成\", 让人误以为那是新代的结果。 "
    "【1】世代标记(已修): 新增 gen_path()/gen_announce()/_gen_superseded(), 启动时写 zt_shrink_gen_<账号>.json"
    "(原子替换, 内容 gen=启动时刻 pid ver), 取数线程在\"进函数\"与\"每批开始前\"各比对一次; 判定为旧代残留时"
    "打一行[提示]并直接 return None —— 不写 cover、不写结果、不覆盖状态。三个条件同时满足才算被取代: "
    "①本代成功宣告过 ②文件里的 gen 严格大于本代 ③那一代 PID 的心跳仍在 HEARTBEAT_STALE_SEC 内。"
    "第③条不能省: 少了它, 一次\"新代启动又退出\"或上一次运行留下的旧文件就会永久压制本代, 情绪整天取不到数。"
    "任何异常一律返回 False(按无法判定处理) —— 宁可两代并行, 也不能让取数停摆。 "
    "【2】取数完成行带耗时(已修可观测性): 旧版只有\"请求/成功/失败/重试\", 单看这行分不出 17 秒还是 21 分钟; "
    "今晚那次 21 分 22 秒是靠\"22:55:42 发起、23:17:04 完成\"两头时间戳手算出来的, 日志本身看不出异常。"
    "现在追加\"耗时N秒\"。 "
    "【3】心跳节拍修正(已修): 实测心跳文件 mtime 为 23:18:14 -> 23:19:14 -> 23:20:14, 是 60 秒一拍, "
    "不是设计的 30 秒 —— timer_poll 每 30 秒回调, 而 _now - last_ts 恰在 30.0 附近, 用 >= HEARTBEAT_SEC 比较时"
    "差一点点就被 return 掉, 每两轮才落一拍。后果不只是\"心跳看起来慢\": V2.6.89 把\"算不算真活着\"的分档阈值"
    "定成 HEARTBEAT_SEC*1.5=45 秒, 按 60 秒节拍只覆盖 0.75 个周期, 真出现双实例时约有 1/4~1/2 的时间会被"
    "降级成[提示]而不是[告警], 等于把最该喊的那一下喊轻了。现改为 < HEARTBEAT_SEC * 0.8 (24 秒), 每次回调"
    "都能过闸, 节拍回到 30 秒; 阈值仍由 HEARTBEAT_SEC 派生, 不新增常量。 "
    "【重要实现约束】本版一个新模块级大写常量都没加: _fp_keys() 用 globals() 收集全部 UPPER_CASE 常量进参数"
    "指纹, 新增一个就会让参数指纹漂移、使 verified_fp 比对凭空失效。世代文件前缀以字面量写在 gen_path() 里, "
    "节流系数写成 HEARTBEAT_SEC * 0.8, 与 V2.6.89/V2.6.90 的处理一致。参数指纹仍为 8a4ab7e8, 仅版本指纹变化。 "
    "核对结论(未改项): 铁律(绝不止损/扣费净利为正才卖/移交释放双额度)未触碰, stop_order 计数仍为 0, "
    "NEVER_STOP_LOSS=True 未动; 三项均不改变任何买卖判据 —— 旧代线程主动退出只会减少接口争用, 情绪未就绪期间"
    "买入侧仍全部中性; 全文件仍只有一处 threading.Thread(取数线程), 旧代遗留不可能重复下单, 心跳文件 mtime "
    "严格落在同一单点序列也证明旧代定时器回调已死。排雷清单 zt_shrink_risk_exclude* 仍不存在(需在 QMT 机器"
    "手动拷贝并运行 download_risk_exclude.py); verified_fp 仍为空。)"
)
lines.insert(4, REC)

for i, l in enumerate(lines):
    if l.startswith("VERSION = 'V2.6.90'"):
        lines[i] = l.replace("VERSION = 'V2.6.90'", "VERSION = 'V2.6.91'", 1)
        break

t = '\n'.join(lines).replace('\n', '\r\n')
open(P, 'wb').write(t.encode('gbk'))
compile(t, P, 'exec')
print('OK V2.6.91 升版, 行数 %d, 版本记录 %d 条, 字节 %d'
      % (len(lines), sum(1 for l in lines if l.startswith('版本号: V')), len(t.encode('gbk'))))
