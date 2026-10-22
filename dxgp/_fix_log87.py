# -*- coding: utf-8 -*-
"""修复被 bash 反引号吞掉的工作日志段落"""
p = '.workbuddy/memory/2026-10-19.md'
t = open(p, 'rb').read().decode('utf-8')
i = t.find('## 22:45 V2.6.87')
assert i > 0
t = t[:i]

add = '''## 22:45 V2.6.87 六项全部落地(用户: 全部做)
- 母版 11998 行 / 685019 字节 / MD5 F66011BF83BAE6531DBC2954DEF93F90
- 参数指纹 8a4ab7e8 / 版本指纹 9c3f03da。较 V2.6.86 的 392cbf3a 变了 —— 新增 7 个行为常量(SENT_COVERAGE_MIN/SENT_CARRY_LOG_SEC/SENT_CACHE_FILE/HEARTBEAT_FILE/HEARTBEAT_SEC/HEARTBEAT_STALE_SEC/HEARTBEAT_ALERT_SEC), 属真参数变化, 需样本外复跑后写入 verified_fp。
- 【1】新增 _sent_fetch_md_batch: 300 失败拆 100 -> 30 重试; _exc_text() 输出 类型+str+repr兜底(str 常为空, 日志原是一片空白); 完成日志改 "请求N只 成功M只(覆盖率x%) 失败K只 拆分重试T次" + 最多3条失败样本。
- 【2B】SENT_COVERAGE_MIN=0.90; _sent_use_last_good() 沿用上次成功信号; 缓存 zt_shrink_sent_cache_<账号>.json(原子写, 跨重启可用); 无历史/已过期才降级中性; **沿用不写 last_fetch_date**(否则回到 V2.6.85 锁日坑, 当天不再重试真实数据)。取数早期失败(G.C不可用/股票列表空/外层异常)也把 cover.ratio 置 0, 一并走沿用。
- 【3】_sent_comp_note() 打 "信号分量: 涨跌广度,涨停家数(2/3, 缺成交额 -> 权重已按剩余分量归一化...)"; _sent_compute 返回 comp_have/comp_miss/comp_total。
- 【4】SENT_STATE[fetching] 三态横幅(True / 取数中(后台线程) / 尚未发起取数); worker finally 无条件复位。
- 【5】心跳 zt_shrink_heartbeat_<账号>_<PID>.json(每实例独立文件; 共用一份会互相覆盖, 双方都以为只有自己), 120 秒新鲜判定, 300 秒告警节流, after_init 强制首检 + timer_poll 每 30 秒; 只告警不阻断。
- 【6】buy_stock 开头 if _f(lp) <= 0: log + return None。
- **自查踩坑**: 心跳扫描首版循环变量写成 _f, 遮蔽模块级 float 转换函数 _f -> _f(...) 抛 UnboundLocalError, 又被 except: pass 静默吞掉, 心跳永远检测不到同伴(T5h 因此假通过)。改 _fn 并把探测异常改为显式提示。教训: 短变量名 _f/_d/_t 在长函数里极易与模块级辅助函数撞名, 撞了还被 bare except 吞掉。
- 回归九套全绿: 不变量 150/150, BugCD 31/31, P2C ALL PASS, 排雷 36/36, 情绪幂等 9/9, V2687 专项 46/46, 主E2E 29/29, 排雷E2E 9/9, 双指纹 PASS。
- _verify_fp.py 第5项断言改为 85->86(纯文档版参数必同) + 86->87(参数必变属预期), 不再写死"当前应与85同指纹"。
'''

open(p, 'wb').write((t + add).encode('utf-8'))
print('ok len=%d' % len(t + add))
