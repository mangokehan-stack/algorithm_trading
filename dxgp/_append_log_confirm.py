# -*- coding: utf-8 -*-
import sys, io, os
sys.stdout.reconfigure(encoding="utf-8")
P = r"E:\桌面\666666\dxgp\.workbuddy\memory\2026-10-21.md"
add = u"""
### 13:49 用户确认：002232 是手机手工卖出

> 手机上卖的。

→ 手工卖出识别链路**闭环验证完成**，无外部未知委托、无账户被操作风险。
→ 同一链路 2026-10-21 13:28:40 已逐环节核对：成交回报无 BUY/SELL 备注 → 本策略持仓四重判据 →
   入账 → 柜台清零后结算 → 解锁。费用 9.78 = 佣金5(起收)+印花4.78+过户0(深市)，净利 +183.22 分毫吻合。
→ 无需任何代码动作。
"""
with open(P, "a", encoding="utf-8") as f:
    f.write(add)
print("appended, size =", os.path.getsize(P))
