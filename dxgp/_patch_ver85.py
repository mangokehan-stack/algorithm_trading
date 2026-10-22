# -*- coding: utf-8 -*-
"""V2.6.85 版本升级: 插入版本记录行 + 改 VERSION 常量"""

P = 'zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
text = raw.decode('gbk')
lines = text.split('\r\n')
N0 = len(lines)

REC = (
    "版本号: V2.6.85              修改时间: 2026-10-19 22:15 "
    "(V2.6.85记录: 客户端 V2.6.84 实跑日志复核, 用户确认\"1 2 3 都改\" —— "
    "【1】情绪降级即锁日导致全天中性: _sent_apply_rows 在函数入口就写 "
    "SENT_STATE['last_fetch_date']=今天, 之后才判断有无昨日完成数据/数据是否陈旧/"
    "信号能否算出, 四个降级分支直接 return 却已写死标记, sent_daily_refresh 见"
    "\"今天已刷新\"当日不再重试 -> 早上启动时若 QMT 日线尚未落盘完整, 首次取数算不出信号"
    "即锁定全天, L1闸门/L3覆写/L4缩仓全部失效, 而日志只有一行\"降级中性\"(历轮 "
    "ready=False 的真因, 已用 _test_sent_idem.py 复现 C2 FAIL); 现移至信号真正算出之后, "
    "只有成功才锁日, 降级按 SENT_RETRY_SEC 正常重试; "
    "【2】参数指纹含 VERSION 导致 verified_fp 比对永久失效: V2.6.83=a36ba5ec / "
    "V2.6.84=77b9f089 而参数一行未改, 每次升版必红标\"参数未经样本外验证\", 告警疲劳使"
    "真参数变更也被忽略; 现拆双指纹 —— param_fingerprint 只含行为参数(VERSION 进 _FP_DENY, "
    "供 verified_fp 比对, 实测 V2.6.83/V2.6.84/当前 三版恒定 94d5c464), 新增 "
    "code_fingerprint=参数+VERSION(供\"代码是否变更\"提示), 启动增打一行[版本指纹]; "
    "【3】情绪 overrides 无中文释义: 旧版只打 "
    "overrides=BUY_MIN_ELAPSED_MIN=45;SHRINK_BUY_RATIO=0.3, 用户看不出\"买点窗口从 10:00 "
    "推到 10:15\"; 新增 _sent_override_note 把键译为\"原名 旧值->新值(方向)\", 如"
    "\"开盘等待分钟 30->45 (越长越晚: 开盘后要等更久才允许买入) | 缩量阈值 0.36->0.3 "
    "(越低越严: 要求当日量能更小才算缩量到位)\"; "
    "三项均不触碰买卖判定逻辑、止损口径与移交释放额度)"
)

# 断言文件头现状
assert lines[4].startswith('版本号: V2.6.84'), lines[4][:60]

lines.insert(4, REC)

# VERSION 常量
hit = [i for i, l in enumerate(lines) if l.startswith("VERSION = 'V2.6.84'")]
assert len(hit) == 1, 'VERSION 常量命中 %d' % len(hit)
lines[hit[0]] = lines[hit[0]].replace("'V2.6.84'", "'V2.6.85'", 1)

out = '\r\n'.join(lines)
assert out.count('\r\n') == len(lines) - 1, 'CRLF 不一致'
compile(out, P, 'exec')
open(P, 'wb').write(out.encode('gbk'))
print('OK: lines %d -> %d, VERSION=V2.6.85, 版本记录行数=%d'
      % (N0, len(lines), sum(1 for l in lines if l.startswith('版本号: V'))))
