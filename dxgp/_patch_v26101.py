# -*- coding: utf-8 -*-
"""
V2.6.101 补丁: 加仓 <-> 卖出 互锁 (用户授权 "先做 ① + ②")
  ① 加仓前查卖出距离: 用卖出侧同一把尺子量一下"离放量止盈还差多少"
  ② 末批与止盈联动: 只剩最后一批时, 若已能赚钱卖出 -> 末批作废
铁律: 只动加仓侧, 不碰任何卖出逻辑/止损; 不新增模块级大写常量(保参数指纹 8a4ab7e8)
"""
import io, os, sys, hashlib

SRC = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
NL = '\r\n'

with io.open(SRC, 'rb') as f:
    raw = f.read()
txt = raw.decode('gbk')

orig_len = len(raw)
print('ORIG_BYTES=%d  ORIG_CHARS=%d' % (orig_len, len(txt)))
print('CRLF_COUNT=%d  LF_COUNT=%d' % (txt.count('\r\n'), txt.count('\n')))

def rep(old, new, tag):
    global txt
    n = txt.count(old)
    if n != 1:
        raise SystemExit('ANCHOR FAIL [%s]: count=%d' % (tag, n))
    txt = txt.replace(old, new, 1)
    print('OK  [%s] in' % tag)

# ---------------- 1) 文件头版本记录 ----------------
HDR_OLD = '版本号: V2.6.100'
HDR_NEW = (
    '版本号: V2.6.101             修改时间: 2026-10-20 08:30 (V2.6.101记录: 用户选"A"并授权"先做 ① + ②", '
    '只动加仓侧(run_pyramid_adds), 不碰任何卖出逻辑/止损, 参数指纹 8a4ab7e8 不变, 无新增模块级常量。'
    '【①加仓前查卖出距离】老毛病: 加仓和卖出各判各的, 会出现"刚按 0.3 仓加完第2/3批, 下一轮就放量止盈卖掉", '
    '白付一份佣金+过户费+印花税, 还把持仓成本抬高(成本抬高又反过来推迟止盈)。改法: 正常加仓段先用卖出侧同一把尺子量距离 '
    '(est=vol x 单位系数 / k 与卖出循环 L9855 完全同口径; base=base_vol; 线=EXPAND_SELL_RATIO x SELL_TOL, '
    '早盘再乘 EARLY_SELL_VOL_MULT), 预估全日量/基准 >= 线 x 0.85 (即离放量止盈只差 15%%) -> 今天不再加仓, '
    '只打一条[加仓暂缓]日志, plan_done 不动(明天量缩了照样能补), 绝不是止损、也不影响卖出。'
    '真实例子: 某票基准量 100 万股, 止盈线 1.9 倍 = 190 万股; 早盘已估到 162 万股(0.85 线)还在往上冲, '
    '老代码会照常买第 2 批, 下一轮量到 190 万直接卖, 这一笔白亏一趟来回费; 改后这一笔不买。'
    '【②末批与止盈联动】只剩最后一批(idx>=len(batches)-1)且现价已高于成本 x(1+最小净利阈值) 且 net_pnl_if_sell>0'
    '(扣完全部费用仍赚) -> 末批直接作废(plan_done=True), 不再补。真实例子: 3 批 0.4/0.3/0.3, 前两批已成交且已浮盈可卖, '
    '老代码还会把最后 0.3 仓买进去, 结果同一天就止盈卖出, 等于最后 30%% 仓位只贡献了一趟买卖手续费; 改后末批不买, 等止盈。'
    '【未做】③到期分级(用户明确留待后续))' + NL +
    '版本号: V2.6.100'
)
rep(HDR_OLD, HDR_NEW, 'hdr-version-note')

# ---------------- 2) VERSION 常量 ----------------
rep("VERSION = 'V2.6.100'", "VERSION = 'V2.6.101'", 'VERSION-const')

# ---------------- 3) run_pyramid_adds 互锁 ----------------
ANCHOR_OLD = (
    '        pos = day_pos(t, lp)' + NL +
    '        note = h.get(\'pyr_note_date\')' + NL +
    '        if in_high_zone(pos):' + NL
)

BLOCK = (
    '        pos = day_pos(t, lp)' + NL +
    '        note = h.get(\'pyr_note_date\')' + NL +
    '        # ---- [2026-10-20 V2.6.101] 加仓 <-> 卖出 互锁: 加仓前先看离"卖出"还有多远 ----' + NL +
    '        #  老毛病: 加仓只看"价格位置/追高/间隔", 卖出只看"放量/换手/到期", 两边互不通气,' + NL +
    '        #  于是会出现"刚加完一批, 下一轮就被放量止盈卖掉": 白付一趟佣金+过户费+印花税,' + NL +
    '        #  还把成本抬高(成本一高, 止盈线又跟着抬高, 反而更难卖)。此处用卖出侧同一把尺子' + NL +
    '        #  (与卖出循环 est = vol * _tick_to_daily_scale() / k 完全同口径) 先量一次距离。' + NL +
    '        #  只做两件事: 离卖出太近 -> 今天不加(明天量缩还能加); 已经能赚钱卖 -> 末批作废。' + NL +
    '        #  绝不触发任何卖出、也绝不是止损(NEVER_STOP_LOSS / stop_order=0 未动)。' + NL +
    '        _il_vol = _f(t.get(\'volume\'))' + NL +
    '        _il_k = _proj_vol_ratio(float(_day_min))' + NL +
    '        _il_est = (_il_vol * _tick_to_daily_scale() / _il_k) if _il_k > 0 else 0.0' + NL +
    '        _il_base = _f(h.get(\'base_vol\', 0) or 0)' + NL +
    '        _il_line = sent_param(\'EXPAND_SELL_RATIO\', EXPAND_SELL_RATIO) * SELL_TOL * (' + NL +
    '            EARLY_SELL_VOL_MULT if _day_min < EARLY_SELL_END_MIN else 1.0)' + NL +
    '        _il_ratio = (_il_est / _il_base) if _il_base > 0 else 0.0' + NL +
    '        # ① 离放量止盈只差 15%% 以内(=线 x 0.85, 早盘同理乘 1.5) -> 今天不再加仓' + NL +
    '        if (_il_base > 0 and _day_min >= EARLY_SELL_BLOCK_MIN' + NL +
    '                and _il_ratio >= _il_line * 0.85):' + NL +
    '            if note != G.today:' + NL +
    '                h[\'pyr_note_date\'] = G.today' + NL +
    '                log(disp(s), \'加仓%d/%d批暂缓: 预估全日量已达基准%.2f倍(放量止盈线%.2f倍, 已到%.0f%%), \'' + NL +
    '                       \'离卖出很近, 今天不再加仓(非止损, 量缩后可再补)\'' + NL +
    '                       % (idx + 1, len(batches), _il_ratio, _il_line,' + NL +
    '                          (_il_ratio / _il_line * 100) if _il_line > 0 else 0.0))' + NL +
    '            continue' + NL +
    '        # ② 末批与止盈联动: 只剩最后一批时, 若已能扣费净赚卖出 -> 末批作废, 不再补' + NL +
    '        _il_cvol = pos_vol(h)' + NL +
    '        _il_cost = (pos_cost(h) / _il_cvol) if _il_cvol > 0 else _f(h.get(\'buy_price\', 0) or 0)' + NL +
    '        if (len(batches) >= 2 and idx >= len(batches) - 1 and _il_cost > 0' + NL +
    '                and lp > _il_cost * (1 + min_profit_pct(h, s))' + NL +
    '                and net_pnl_if_sell(h, lp, s) > 0):' + NL +
    '            if note != G.today:' + NL +
    '                h[\'pyr_note_date\'] = G.today' + NL +
    '                log(disp(s), \'加仓末批(第%d/%d批)取消: 现价%.2f已高于成本%.2f且扣费后仍净赚, \'' + NL +
    '                       \'随时可能止盈, 剩余计划作废(不再补仓)\'' + NL +
    '                       % (idx + 1, len(batches), lp, _il_cost))' + NL +
    '            h[\'plan_done\'] = True' + NL +
    '            continue' + NL +
    '        if in_high_zone(pos):' + NL
)
rep(ANCHOR_OLD, BLOCK, 'pyramid-interlock')

# ---------------- 自检 ----------------
out = txt.encode('gbk')
with io.open(SRC, 'wb') as f:
    f.write(out)

print('NEW_BYTES=%d  DELTA=%d' % (len(out), len(out) - orig_len))
print('CRLF_AFTER=%d' % txt.count('\r\n'))

# 锚点完整性: 关键函数仍然存在
for fn in ['def run_pyramid_adds', 'def run_round', 'def pyramid_add', 'def sell_stock',
           'def buy_stock', 'def day_pos', 'def in_high_zone', 'def min_profit_pct',
           'def net_pnl_if_sell', 'def pos_cost', 'def _proj_vol_ratio', 'def _tick_to_daily_scale']:
    if fn not in txt:
        raise SystemExit('LOST FUNC: %s' % fn)
print('ALL_FUNC_ANCHORS_OK')

import py_compile
py_compile.compile(SRC, doraise=True)
print('PY_COMPILE_OK')
print('MD5=%s' % hashlib.md5(out).hexdigest().upper())
