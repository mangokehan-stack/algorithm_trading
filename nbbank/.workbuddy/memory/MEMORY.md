# 项目长期记忆 — nbbank 广发 QMT 策略

## 交付件与真源

`gf_qmt_native_multi_gbk.py` = **唯一交付件**，GBK 编码、LF 行尾，单股 002142.SZ 宁波银行，20 万预算。
当前 **v1.2.80**（519,871 B / 9,516 行 / md5 `c887a4c8a2f14cd40b19ac5a6b378dd1`）。
UTF-8 版与聚宽版**故意不同步**，用户只要 GBK 版。

改前备份（近期优先）：`.bak_20261022_v1279_pre_aud97`(v1.2.80 前,514194)、
`.bak_20261021_v1277_pre_aud95`(v1.2.78 前,505145)、
`.bak_20261021_v1276_pre_logtxt`(v1.2.77 前)、`.bak_20261021_v1275_pre_aud94`(v1.2.76 前)、
`.bak_20261021_v1274_pre_aud93`(v1.2.75 前)、`.bak_20261021_v1271_pre_aud35`(v1.2.72 前)、
`.bak_20261020_v1265_pre_aud28`(v1.2.66 前)、`.bak_20261020_v1264_pre_aud27`(v1.2.65 前)。
更早的 `pre_aud17~25 / pre_P0 / pre_f2fix / pre_audit` 同理命名。
**注：v1.2.79（AUD96 十一项）由上一轮直接改盘，无改前备份** —— 备份链在此处断了一节。

### 验收脚本（改完必跑）

| 脚本 | 项数 | 何时必跑 |
|---|---|---|
| `_verify_final.py` | **165** | 每次改动（硬闸门：当前版本必有对应变更记录块，防版本漂移） |
| `_test_aud97.py` | 35 | 改委托侧代码匹配/方向翻译/落盘首次创建/版本收尾 |
| `_test_aud95.py` | 19 | 改 `_probe_trade_mode`/`_INIT_START_TS`/框架日志解析 |
| `_test_aud94.py` | 45 | 改 `_sync_state_to_actual`/`_r1_net_profit_gate`/锁/情绪 EWMA |
| `_test_manual_aud27.py` | 47 | 动手工仓、卖出闸门 |
| `_test_aud28.py` | 27 | 改外部同步/两本账判定 |
| `_test_aud35.py` | 38 | 改同步分类/卖出股数 |
| `_test_aud92.py` | 33 | 改写盘守卫/持久化降级 |
| `_test_aud93.py` | 26 | 改费用公式/下单预留 |
| `_test_market_filter.py` | 34 | F2 大盘过滤 + 数据门（会 exec GBK 交付件） |
| `_test_dlinject.py` | 12 | 改补下载注入链路 |
| `_regress_v1258.py` | 行为级 | 改止盈/费率/风控 |

工具类：`backtest_optimize.py`（回测内核 747 行）、`_tune_tp_grid.py`（384 组网格）、
`_tune_roll.py`（33 滚动半年窗）、`_tune_frame.py`/`_tune_frame2.py`、`_diag_f2.py`、`_diag_gate.py`。

## 编辑铁律（违反会出事）

1. **GBK 原件绝不经 Edit/Write 工具**（会写 UTF-8）。必须 Python `io.open(p,"rb").read().decode("gbk")`
   → 改字符串 → `io.open(p,"wb").write(txt.encode("gbk"))`。
2. **行尾是 LF，不是 CRLF**。不要加 CRLF。
3. 每次改动前 `sub_once` 唯一匹配断言，匹配数 != 1 立即中止。
3b. **先编码预检 + 原子替换**：`blob = txt.encode("gbk")` 成功后才写 `.tmp_w` 再 `shutil.move`。
   **绝不直接 `open(P,"wb")`**——打开即清空，encode 抛异常会让交付件变 0 字节（已踩两次）。
   GBK 不支持 `▸`(U+25B8)，注释用 `·` 等可编码字符。
3c. **同一补丁脚本内绝不混用「行号替换」与「字符串替换」**（AUD34 踩坑：行号块会用旧 lines
   列表重建全文，静默冲掉中间修改）。span 替换 end 锚点必须含整行（含缩进与 `#`）。
   落盘后必须 `py_compile`。
4. **含反引号或大量中文的脚本一律写入 `.py` 文件再执行**，不要 bash `-c` 内嵌
   （反引号会被 shell 当命令替换，把文本吃掉一段）。
5. 审计号用高位（AUD92+），先 grep 查最高号。历史撞号已修：v1.2.46→46A/B/C、v1.2.37→37A/37。
6. **审计结论落进代码注释前必须先跑数值实测**（v1.2.60 曾把「金字塔第4档被封顶」写进注释，
   实测根本没触顶）。**档位预算 = capital_cap × pyramid 权重（合计 0.9×20万）**，
   不是「按 18 万切分」。
7. **改版本号必须同步 7 处**：交付件 3 处（文件头 `#  策略版本:` / `STRATEGY_VERSION` /
   变更记录块 `── v1.x.y = `）+ 脚本 4 处（`_verify_final` 两处、`_test_aud28`、`_test_aud35`、
   `_test_manual_aud27`）。

## 策略铁律（用户明确要求，零触碰）

- **坚决不止损**：任何止损单/止损参数/强制平仓一律不得加入。`hard_stop_dd_pct=None`；
  `check_stop_loss_alert` 仅告警不卖出。
- **扣费后真赚钱才卖**：所有卖出路径走 `_r1_net_profit_gate(code, actual_vol, broker_avg,
  price, state, reason, sub_vol=None, exact_avg=False)`——保守成交价 `price*(1-0.003)` 扣佣金
  (万0.841，**每委托单 5 元起**) + 印花(万5 卖出单边) + 过户(万1 双边)，净到手 <= 成本一律拒绝。
  默认成本取 `max(券商均价, 策略均价, 手工均价)`；`exact_avg=True` 时只按传入均价
  （v1.2.76 起 sell_all 按「本次卖的那本账」分别判）。`sell_all` 未传 state 直接拒绝。
- **手工仓不占策略名额与投资金额**（用户 2026-10-20 反复确认三次）：只写 `manual_shares/manual_cost`，
  **不进** `position_shares/total_cost/deployed/tier`，机器不加仓。`manual_takeover=True`
  = **只管卖、不管买**。**不要试图把这笔仓「升级」成策略仓**——15:15 曾按选项做 AUD29 被当场中断。
- **股票移交人工处理后释放股票额度与资金额度**（用户本轮再次强调，必须原样保留）。
- 移动止盈口径统一为 `_ref_px_tp`：peak 写入、回撤计算、pnl_pct 三者同用。

## 两本账（AUD27 核心架构）

| 账本 | 字段 | 谁写 | 占额度 |
|---|---|---|---|
| 策略 | `position_shares`/`expected_shares`/`total_cost`/`deployed`/`tier`/`last_add_price` | 只有策略自己下的单 | 占 |
| 手工 | `manual_shares`/`manual_cost`/`manual_peak_cost`/`manual_sell_pending_until` | `_sync_state_to_actual` | 不占 |

**致命陷阱**：手工仓移出后 `position_shares` 恒 0，原 R1 `if position_shares > 0:` 会整段跳过
= 给亏损卖出开后门。故 R1 一律按券商实际持仓+实际成本判，绝不依赖账本。
`tier` 空仓恒 -1，否则下次开首仓从第 2 档起步少买 5 万。
`verify_position_before_order` 第 4 个返回值是**原因文本**不是均价——sell_all 里单独
`query_position_safe` 取券商均价（3s 缓存）。

## 关键参数（以代码为准）

固定止盈 4% / 移动止盈 激活 3% + 回撤 2% / 熊市过滤 MA20<MA60 / 追涨上限 6% /
金字塔 [0.50,0.25,0.10,0.05] 每跌 2% 一档 / 资金 20 万 / max_position_pct 90%(+600 缓冲 →
硬顶 180600) / DAILY_ADD_CAP=90000（M2+M3 共享）/ M3_LEVELS 四档各 6000 / M3 软暂停 2 档 /
首仓分批 [0.40,0.30,0.30] / F2 大盘过滤(沪深300 MA20>=MA60，只挡首仓；不复权优先、末根按日期判断、
n=60 请求 n+10 最低收 n+1) / 情绪 SENTIMENT_ENABLED=False + block_euphoric_only=True（狂热单态）。
费率：股票全佣金万0.841（5元起）、印花万5卖出单边、过户万1双边。

## 运行时事实

- **`gf_native_trade.log` 是 UTF-8 不是 GBK**（2026-10-21 实测），用 GBK 解码得「寮�濮�」乱码。
  按大小轮转 `.log.1`~`.log.20`，历史「版本自检/参数指纹」从轮转文件回溯——这是核对
  「参数有没有被动过」最硬的证据。
- **参数指纹 `_PARAM_FP`** 只对 PARAMS 求 sha256 不含版本号；无「参数变更告警」= 与上次逐位一致。
  已知基线：`bbbb0fed8635`（v1.2.74~v1.2.78 一致）。
- QMT 内置 Python 无 akshare → `gf_tradeday_cache.json` 删除后无法自愈，交易日历靠内置节假日表
  + 仅周末 + 拦截三级兜底。
- 成交量单位统一「手」：参与率闸门 `_max_vol = avg_vol * 100 * max_participation_pct`，
  `_day_vwap` 固定 ×100 换算股。
- **改完代码必须重载模型**。QMT 不会自动读磁盘新代码——v1.2.63 曾因未重载误判「修复无效」。
  以启动日志 `版本自检 | 策略版本=vX` 为准。
- 本机 QMT 只暴露 `download_history_data`（老接口），`download_history_data2` 未暴露，属正常；
  补下载走「5参→4参→3参」降级链。`_DL_FUNCS` 定义时为 None，靠 `_inject_dl_funcs` 三路取名注入
  （模块全局/ContextInfo 方法/`__builtins__`），init/handlebar/`_try_download_hist` 三处幂等调用。
- 指数日线含当日实时 bar 时 MA20/MA60 用「昨日及以前」口径；末根是否当日**必须按日期判**。
- 镜像目录 `C:\...\userdata_mini\gf_qmt_mirror\` 常被安全中心拦截，失败只记日志，60s 自动重试。
- 测试时须把 `ns` 里所有 `.json`/`.log` 路径重定向到 `tempfile.mkdtemp()`。
- **凡打开 `DATA_GATE_POPUP` 的测试，两个弹窗函数必须全部打桩**（含 `_popup_data_gate_interactive`，
  否则 ctypes MessageBoxW 模态框挂死脚本，已踩过一次）。
- 模拟测场景**必须单进程单场景**，同进程连跑必被 `_STATES`/`_IDX_ALERT`/`_SETTLE_COOLDOWN`
  残留污染，曾因此误判「修复无效」。

## 历史审计关键结论（浓缩）

- **AUD23（v1.2.61）**：情绪模块在狂热单态下曾取数失败即 fail-closed 关死所有买入，被 30 分钟
  暖机期遮蔽 → 表现为「开盘半小时能买、之后一笔不买」。已改 fail-open。实证手法：把
  `_SENT_PROC_START_TS` 往前拨 1860 秒对比。
- **AUD24（v1.2.62）**：「数据都下载了还说没就绪」主因是门槛多一根（请求 n+5 又无条件剔末根再要
  n+5）。指数不该复权（front_ratio 返回被缩放点位，29.9077 真根因）→ none 优先。老接口
  `get_history_data` 对指数是假兜底（不吃 code、返回个股序列）→ 加 require_code 严格匹配。
- **AUD25（v1.2.63）**：自检打印配置原值 = 会说谎（情绪有覆盖逻辑）。「没有数据就绪拦截」=
  数据门通过，不要因没看到那行就以为没检查。
- **AUD26（v1.2.64）**：「请求多少就要求多少」是最危险的阈值写法。改阈值必须全局搜同款表达式。
  门槛降低须同步检查下游（中间隔着 `_closed_slice` 剔末根）。
- **AUD94（v1.2.76，2026-10-21 零预设审计十项）**：两本账的「市值/额度/入口」三处仍混用券商实际持仓，
  是最大系统性缺陷。P1 权益市值扣手工份额 / P2 加仓链入口判 `position_shares` /
  P3 在途买单期间手工份额只增不减 / P3b 份额未变保留原 `manual_cost`（原按券商混合均价重算会
  低估手工成本 → R1 误判已赚 → **破铁律**，教训：**凡「用账户级均价推算单本账成本」的写法都必然
  污染另一本账**）/ P4 卖出按本次卖的那本账分别判 / P5 额度只算策略市值 / P6 锁续命回读校验 pid /
  P7 情绪 EWMA 每交易日只平滑一次 / P8 cash 注释如实化 / P9 释放锁前校验归属。
- **AUD95（v1.2.78）**：运行模式误报。`_probe_trade_mode` 用固定 60 秒滑动窗口判「本次运行」且命中即
  返回，会读到上一轮残留（15:24:46 simulation 被 15:25:22 的 init 误认）。修法：新增 `_INIT_START_TS`
  + `_MODE_PRE_INIT_SEC=10`，早于「init 起始−10 秒」的行判为残留不采纳，走「不作结论 + 首根 bar
  补测」兜底。**`_trade_mode` 只是 init 局部变量，不参与任何交易判定。**
  **判运行模式的正确姿势**：看框架日志末条 `output = [trade]start <mode> mode` 或界面首行。
- **AUD96（v1.2.79）**：十一项全新独立审计。P1 save_state/save_m3 读失败中止写入；P2 挂单强清先查券商
  活跃委托；P3 方向字段分字段翻译（统一 0=买/1=卖/None=未知）；P4 佣金异常返回保守最低值；
  P5 冷却字段类型异常保守视为冷却中；P6 风险日志读失败中止写入；P7 R1 成本未知发告警；
  P8 load_state/load_m3 读失败一次性告警；P9 在途台账断路恢复改 max() 合并；P10 持仓代码匹配大小写
  不敏感 + 品种费率提醒；P11 init 兜底重载台账 + 锁 fail-open 告警 + sync 显式返回。
  **AUD96 引入的回归已由 AUD97-P4 修复**（见「已知未闭环」第一条）。
- **AUD97（v1.2.80）**：五项收尾。P1 委托侧 4 处代码匹配改大小写不敏感（AUD96-P10 只改了持仓侧，
  委托侧漏改 → 活跃买单查不到 → 在途台账被清 → **重复下单**）；P2 方向翻译逐字段回退
  （首字段值域不认时继续试下一字段，不再一票否决）；P3 方向自检改用与运行时同一翻译口径统计并如实
  描述未知委托处置；P4 修 AUD96 落盘回归（首次创建必须能落盘）；P5 版本收尾（文件头版本行 +
  v1.2.79 记录块补齐）。**教训：修复「同类问题」时必须把同类代码点全查一遍**——AUD96-P10 改了
  持仓侧，委托侧 4 处同款漏改；只有逐个 grep `pid != code` 才抓得到。

## 已知未闭环

- **`_read_file_bytes` 返回 None 有二义性**（AUD96/AUD97 踩坑，已修但需记住）：
  「文件不存在」与「三通道都读不出来」都返回 `(None, err)`。AUD96 曾一律当「读失败→中止写入」，
  导致状态文件/M3台账/风险日志**首次创建时永远写不进去**。修法：`os.path.exists(path)` 为真
  才中止（`os.path.exists` 在 QMT 沙箱可用，代码里已有 30+ 处既有用法）。
  **凡写「读失败就不写」的逻辑，必须先区分文件不存在。**
- `_HB_LAST_BEAT_TS`/`_QMT_MODE_LOG`/`_TRADEDAY_LAST_DATE`/`ENTRY_OPT_ENABLED`/`_DATA_GATE_SYM`/
  `_MANUAL_WATCH_GAP` 是只写不读（用户拍板保留，文件头 L330 附近已如实标注）。
- **单实例锁的固有盲区**：锁记的是 QMT 客户端进程号（同进程内多窗口 pid 相同）。同进程 + 卡顿超
  600 秒 + 另开窗口三条件同时成立时 AUD94-P6 认不出易主。QMT 无窗口级唯一标识，无法彻底解决。
- **过拟合**：当前参数由 384 组网格寻优 + 33 个滚动半年窗稳健性对比得来，属策略设计层，
  改代码解决不了。内核费率是历史口径（佣金万2.5 ≠ 实盘万0.841），只用于横向比参数。
- 拟合验证能力已于 2026-10-19 恢复（早前记为「永久丢失」有误），详见
  `.workbuddy/拟合验证能力恢复说明_20261019.md`。**教训：清理目录务必先生成清单，历史会话
  jsonl 是可恢复备份。**