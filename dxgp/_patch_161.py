# -*- coding: utf-8 -*-
"""V2.6.161 补丁脚本(第14轮零预设独立审计收尾)。
改动(全部先备份, 内存中完成全部替换后才落盘):
  R1 文件头插入 V2.6.161 记录行(真实落盘时间)
  R2 修正 V2.6.160 记录行失实表述"版本指纹不变"(实为 8e420f90->62d57b40), 同时归一该行行尾裸 LF
  R3 VERSION 常量升版 V2.6.160 -> V2.6.161(等长)
  R4 buy_stock 动态手数分支(want_vol)补双帽兜底(单票绝对额度 + 组合剩余额度)
  R5 buy_stock 目标金额回退分支(else)补同口径双帽
  R6 整块删除 V2.6.146 内嵌死代码(策略内自动排雷抓取, 359行), 原位留墓碑注释
  R7~R14 排雷提示 8 处引用的 download_risk_exclude.py(自 V2.6.83 起从未交付)改为如实描述
"""
import datetime
import os
import shutil
import sys

MASTER = 'zt_shrink_strategy_gbk.py'

raw = open(MASTER, 'rb').read()
orig_len = len(raw)


def E(s):
    return s.encode('gbk')


def sub_once(buf, old, new, tag):
    n = buf.count(old)
    if n != 1:
        print('FATAL %s: anchor count=%d (expect 1)' % (tag, n))
        sys.exit(1)
    return buf.replace(old, new, 1)


# ---------- R2: 修正失实表述 + 归一裸 LF(先做, 锚点含裸LF) ----------
old = E(', 铁律口径不变, 版本指纹不变。\n# 版本号: V2.6.158')
new = E(', 铁律口径不变, 版本指纹由8e420f90变为62d57b40(版本号计入版本指纹, 参数零漂移)。\r\n# 版本号: V2.6.158')
raw = sub_once(raw, old, new, 'R2-版本指纹失实+裸LF')

# ---------- R3: VERSION 升版 ----------
old = E("VERSION = 'V2.6.160'")
new = E("VERSION = 'V2.6.161'")
raw = sub_once(raw, old, new, 'R3-VERSION')

# ---------- R4: buy_stock 动态手数分支双帽兜底 ----------
old = E("    if want_vol and want_vol >= _lot:\r\n"
        "        vol = int(want_vol / _lot) * _lot\r\n"
        "    elif FIXED_BUY_VOL > 0:")
new = E("    if want_vol and want_vol >= _lot:\r\n"
        "        vol = int(want_vol / _lot) * _lot\r\n"
        "        # V2.6.161(第14轮审计-投资金额突破上限): 动态手数分支补双帽兜底, 与下方固定量回退分支同口径。\r\n"
        "        #   want_vol 上游虽已过 calc_size 的 n2(单票绝对额度)/n5(组合剩余额度), 但两者均按未含滑点的\r\n"
        "        #   价格折算; 实收价按动态滑点(低价股0.3%)成交时, 单票成本最高突破 MAX_POS_VALUE_ABS 约200元;\r\n"
        "        #   同轮多笔买入时在途委托额度的登记时序差, 也靠这两帽兜底。只削不增: 帽内时 vol 不变。\r\n"
        "        _px_g = _round2(lp * (1.0 + _slippage_for(lp)))\r\n"
        "        if _px_g <= 0:\r\n"
        "            _px_g = _round2(lp)\r\n"
        "        _caps_g = []\r\n"
        "        if MAX_POS_VALUE_ABS and MAX_POS_VALUE_ABS > 0:\r\n"
        "            _caps_g.append(MAX_POS_VALUE_ABS / _px_g)\r\n"
        "        _cl_g = abs_cap_left(_px_g)\r\n"
        "        if _cl_g is not None:\r\n"
        "            _caps_g.append(_cl_g)\r\n"
        "        if _caps_g:\r\n"
        "            _cv_g = int(min(_caps_g) / _lot) * _lot\r\n"
        "            if _cv_g < _lot:\r\n"
        "                log(disp(s), '动态手数: 仓位帽算下来不足一手(帽=%.0f股 价格=%.2f), 放弃'\r\n"
        "                    % (min(_caps_g), _px_g))\r\n"
        "                return None\r\n"
        "            if vol > _cv_g:\r\n"
        "                log(disp(s), '动态手数: %d股超过仓位帽, 削平为%d股' % (vol, _cv_g))\r\n"
        "                vol = _cv_g\r\n"
        "    elif FIXED_BUY_VOL > 0:")
raw = sub_once(raw, old, new, 'R4-want_vol双帽')

# ---------- R5: 目标金额回退分支双帽 ----------
old = E("    else:\r\n"
        "        amount = min(TARGET_BUY_AMOUNT, cash)\r\n"
        "        vol = int(amount / lp / _lot) * _lot")
new = E("    else:\r\n"
        "        amount = min(TARGET_BUY_AMOUNT, cash)\r\n"
        "        # V2.6.161(第14轮审计-投资金额突破上限): 目标金额分支原本两帽皆无(单票绝对额度与\r\n"
        "        #   组合剩余额度都不校验), 用户若把 TARGET_BUY_AMOUNT 设得超过帽子即可越界; 此处补同口径双帽。\r\n"
        "        _px_g = _round2(lp * (1.0 + _slippage_for(lp)))\r\n"
        "        if _px_g <= 0:\r\n"
        "            _px_g = _round2(lp)\r\n"
        "        _caps_g = []\r\n"
        "        if MAX_POS_VALUE_ABS and MAX_POS_VALUE_ABS > 0:\r\n"
        "            _caps_g.append(MAX_POS_VALUE_ABS / _px_g)\r\n"
        "        _cl_g = abs_cap_left(_px_g)\r\n"
        "        if _cl_g is not None:\r\n"
        "            _caps_g.append(_cl_g)\r\n"
        "        if _caps_g:\r\n"
        "            _amt_cap = min(_caps_g) * _px_g\r\n"
        "            if amount > _amt_cap:\r\n"
        "                log(disp(s), '目标金额: %.0f元超过仓位帽, 削平为%.0f元' % (amount, _amt_cap))\r\n"
        "                amount = _amt_cap\r\n"
        "        vol = int(amount / lp / _lot) * _lot")
raw = sub_once(raw, old, new, 'R5-目标金额双帽')

# ---------- R6: 删除死代码块(策略内自动排雷抓取), 留墓碑注释 ----------
i0 = raw.find(E('# -*- coding: utf-8 -*-'))
i1 = raw.find(E('def risk_excluded(s):'))
if i0 < 0 or i1 < 0 or i1 <= i0:
    print('FATAL R6: dead-block boundary not found (%d, %d)' % (i0, i1))
    sys.exit(1)
if raw.count(E('# -*- coding: utf-8 -*-')) != 1 or raw.count(E('def risk_excluded(s):')) != 1:
    print('FATAL R6: boundary anchor not unique')
    sys.exit(1)
if raw[i0 - 2:i0] != b'\r\n' or raw[i1 - 2:i1] != b'\r\n':
    print('FATAL R6: boundary not at line start')
    sys.exit(1)
dead_lines = raw[i0:i1].count(b'\r\n')
tomb = E("# V2.6.161(第14轮审计-死代码清理): 原 V2.6.146 内嵌的\"策略内自动排雷抓取\"整块已删除\r\n"
         "#   (含 5 个外部抓取函数/聚合类/_http_risk/_suffix_risk/_norm_risk/_iso_risk,\r\n"
         "#    以及 _ssl_excl/_uparse_excl/_urequest_excl 三个导入与 _RISK_* 系列常量, 约360行)。\r\n"
         "#   删除原因: ① _auto_risk_exclude 自 V2.6.160 起零调用点(纯死代码);\r\n"
         "#   ② 其内部经东方财富/新浪的外部 HTTP 抓取, 正是触发 QMT「非法IP」安全拦截强退事故的根因\r\n"
         "#      (V2.6.160 已移除调用); 排雷清单改为仅本地 JSON 后, 该块永无恢复必要。\r\n"
         "#   ★ 教训: 绝不在策略进程内直接抓取外部行情接口 —— 会触发 QMT IP 安全拦截强退。")
raw = raw[:i0] + tomb + b'\r\n\r\n' + raw[i1:]
print('R6: deleted %d lines, tombstone inserted' % dead_lines)

# ---------- R7~R14: 排雷提示引用不存在的脚本, 改为如实描述(锚点取自母版实测行) ----------
rw = [
    # R7 RISK_EXCLUDE_FILE 常量注释
    (E('# 排雷清单(仅纯文件名, 与脚本同目录; 由 download_risk_exclude.py 生成)'),
     E('# 排雷清单(仅纯文件名, 与脚本同目录; 在QMT外部生成后放入, 策略只读)'), 'R7'),
    # R8 Phase2 注释
    (E('    #   排雷清单由独立脚本 download_risk_exclude.py 在QMT外部生成, 策略仅读取本地JSON'),
     E('    #   排雷清单在QMT外部生成后放入脚本同目录, 策略仅读取本地JSON(策略内不抓取外部接口)'), 'R8'),
    # R9 Phase2 日志行
    (E("        log('[排雷] 如需更新排雷清单, 请在QMT外部运行: python download_risk_exclude.py --update')"),
     E("        log('[排雷] 排雷清单为本地JSON(与脚本同目录); 更新请在QMT外部生成后替换该文件, 策略内不做外部抓取(防非法IP拦截)')"), 'R9'),
    # R10 load_risk_exclude docstring
    (E('    """V2.6.83新增: 每日装载一次提前排雷清单(由 download_risk_exclude.py 生成)。'),
     E('    """V2.6.83新增: 每日装载一次提前排雷清单(本地JSON, 与脚本同目录; 在QMT外部生成)。'), 'R10'),
    # R11 schema 校验失败提示
    (E('\'"该类无风险"; 请重跑 download_risk_exclude.py\''),
     E('\'"该类无风险"; 请在QMT外部按schema=1重新生成清单\''), 'R11'),
    # R12 装载告警日志
    (E("'[排雷][告警] %s —— 仍按现有清单拦截(偏紧), 请重新运行 download_risk_exclude.py'"),
     E("'[排雷][告警] %s —— 仍按现有清单拦截(偏紧), 请在QMT外部更新本地清单文件'"), 'R12'),
    # R13 强提醒
    (E("pnl_alert('[排雷][告警] %s, 请重新运行 download_risk_exclude.py 更新清单' % err)"),
     E("pnl_alert('[排雷][告警] %s, 请在QMT外部更新本地清单文件(策略内不抓取外部接口)' % err)"), 'R13'),
    # R14 清单缺失引导
    (E("' 请运行 download_risk_exclude.py 生成清单 —— 生成后自动装载, 无需重启策略'"),
     E("' 请在QMT外部按schema=1生成清单并放入脚本同目录 —— 放入后自动装载, 无需重启策略'"), 'R14'),
]
for old, new, tag in rw:
    raw = sub_once(raw, old, new, tag)

# ---------- R1: 插入 V2.6.161 记录行(真实落盘时间) ----------
now = datetime.datetime.now()
ts = now.strftime('%Y-%m-%d %H:%M')
rec = E('# 版本号: V2.6.161             修改时间: %s (V2.6.161记录: 第14轮零预设独立审计收尾(用户要求推荐问题全部直接修完)。'
        '① 投资金额突破上限(审计点名项): buy_stock 动态手数分支补双帽兜底, 与固定量回退分支同口径 —— '
        'want_vol 上游虽已过 calc_size 的 n2(单票绝对额度)/n5(组合剩余额度), 但两者均按未含滑点的价格折算, '
        '实收价按动态滑点(低价股0.3%)成交时单票成本最高突破 MAX_POS_VALUE_ABS 约200元; '
        '同轮多笔买入时在途委托额度登记存在时序差, 也靠这两帽兜底。目标金额回退分支(固定量关闭且动态手数关闭时可达)'
        '原本两帽全无, 同样补上。只削不增, 帽内行为零变化。'
        '② 死代码清理(审计点名项): 整块删除 V2.6.146 内嵌的策略内自动排雷抓取(约360行: 5 个外部抓取函数/聚合类/'
        'HTTP 与 SSL 导入/_RISK_* 系列常量), 原位留墓碑注释 —— 该块自 V2.6.160 起零调用点, 且其经东方财富/新浪的外部抓取'
        '正是触发 QMT「非法IP」安全拦截强退事故的根因; 排雷清单改为仅本地 JSON 后永无恢复必要。删除项均为下划线前缀, 参数指纹零漂移。'
        '③ 文案说谎修复两处: V2.6.160 记录行自称版本指纹不变, 与实盘日志矛盾(8e420f90->62d57b40, 版本号计入版本指纹), '
        '已改为如实表述; 排雷提示 8 处引用的 download_risk_exclude.py 自 V2.6.83 起从未交付(V2.6.90/91/92 记录已承认'
        '脚本并不存在), 按提示重跑只会落空, 已全部改为描述真实的本地清单更新方式(schema=1/脚本同目录/在QMT外部生成后替换/'
        '每小时至多重读), 不再点名不存在的脚本。'
        '④ 交付门禁: 归一文件头唯一裸 LF 为 CRLF, 裸 LF=0。'
        '⑤ 复核无需改动项: 下单方向常量(买23/卖24/按股1101/限价11, 与文件头文档一致)、心跳双实例(每实例账号+PID 心跳文件+'
        '世代文件+陈旧检测, 实盘 PID=21884 已生效)、重复下单四重防护(在途委托快照/当日codes/rebuy_blocked/T0规则)、'
        '主循环跳过已持仓股票(加仓走独立通道且自带帽子)、情绪累积池跨代恢复、abs_cap_left 价格无效保守返0。'
        '交易参数一行未改(参数指纹仍为efb96534), 铁律口径不变。)\r\n')
old = E('# 版本号: V2.6.160')
raw = sub_once(raw, old, rec + old, 'R1-记录行')

# ---------- 落盘前自检 ----------
assert raw[:3] != b'\xef\xbb\xbf', 'BOM appeared'
n_lf = raw.count(b'\n')
n_crlf = raw.count(b'\r\n')
if n_lf != n_crlf:
    print('FATAL: bare LF = %d' % (n_lf - n_crlf))
    sys.exit(1)
raw.decode('gbk')  # 编码往返
assert raw.count(E("VERSION = 'V2.6.161'")) == 1
assert raw.count(E('def _auto_risk_exclude')) == 0, 'dead fn definition still present'
assert raw.count(E('download_risk_exclude')) == 7, 'historical 6 + new record 1 expected, got %d' % raw.count(E('download_risk_exclude'))
assert raw.count(E('def risk_excluded(s):')) == 1
assert raw.count(E('    if want_vol and want_vol >= _lot:')) == 1

# ---------- 备份 -> 原子写 ----------
bak = '.bak-' + now.strftime('%Y%m%d-%H%M')
shutil.copy2(MASTER, bak)
tmp = MASTER + '.tmp'
with open(tmp, 'wb') as f:
    f.write(raw)
    f.flush()
    os.fsync(f.fileno())
os.replace(tmp, MASTER)
print('OK backup=%s  %d -> %d bytes  (+%d)' % (bak, orig_len, len(raw), len(raw) - orig_len))
print('record timestamp: %s' % ts)
