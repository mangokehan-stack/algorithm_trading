# -*- coding: utf-8 -*-
"""
V2.6.102: ③ 到期分级(用户授权)
  首笔浮盈 -> 等待期延长 3 个交易日等回调(赢家给机会)
  浮亏     -> 到期立即放弃剩余计划, 且绕开 fill(输家不补仓)
铁律: 只决定"还等不等 / 补不补", 不碰卖出判据、不碰止损; 不新增模块级大写常量
"""
import io, hashlib, py_compile

SRC = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
NL = '\r\n'

t = io.open(SRC, 'r', encoding='gbk', newline='').read()
orig = len(t.encode('gbk'))
print('ORIG_BYTES=%d  CHARS=%d  CRLF=%d' % (orig, len(t), t.count(NL)))

def rep(old, new, tag):
    global t
    n = t.count(old)
    if n != 1:
        raise SystemExit('ANCHOR FAIL [%s]: count=%d' % (tag, n))
    t = t.replace(old, new, 1)
    print('OK [%s]' % tag)

# ---------------- 1) 文件头版本记录 ----------------
HDR = (
    '版本号: V2.6.102             修改时间: 2026-10-20 08:58 (V2.6.102记录: 用户授权做 ③ 到期分级, '
    '只动 run_pyramid_adds 的"超出最长等待"分支, 不碰卖出判据/止损, 参数指纹 8a4ab7e8 不变, 无新增模块级常量。'
    '【③到期分级: 赢家给机会, 输家不补仓】老毛病: 到期不分好坏一视同仁 —— 还在赚钱的票(只是这几天一直没回调到低位)'
    '被硬砍掉剩余仓位, 亏钱的票反而可能被 fill 一次性补齐(越亏越补, 仓位越重越难翻身, 还占用名额和资金)。'
    '改法: 到期时先算持仓成本(pos_cost/持仓股数, 含买入费用), 现价>成本=浮盈 -> 等待期在 PYRAMID_MAX_WAIT_TRDAYS(5)'
    '基础上 +3 个交易日(=8 个交易日), 多给它几次回调机会, 并打一条[等待延长]日志(每天限一条); '
    '现价<=成本=浮亏 -> 到期就作废剩余计划(plan_done=True), 并且绕开 EXPIRE_MODE=fill(绝不补仓, 不再往亏钱票上加钱)。'
    '真实例子: A 票成本 10.00, 第 6 天现价 10.40(浮盈, 这几天一直在高位没回调), 老代码今天就把剩下 0.3 仓砍掉; '
    '改后延到第 8 天, 多等 3 天回调再决定。B 票成本 10.00, 第 6 天现价 9.60(浮亏), 老代码若在 fill 模式下会把剩余仓位'
    '一次性补齐(越亏越补); 改后直接作废剩余计划, 一分钱不再加, 票继续持有等缩量反弹后的卖出机会(绝不止损)。'
    '注: MAX_HOLD_TRDAYS=33 天, 延长到 8 天不会与"持有到期卖出"打架; 该分级只管"补不补仓", 不影响任何卖出条件)'
    + NL + '版本号: V2.6.101'
)
rep('版本号: V2.6.101', HDR, 'hdr-version-note')

# ---------------- 2) VERSION 常量 ----------------
rep("VERSION = 'V2.6.101'", "VERSION = 'V2.6.102'", 'VERSION-const')

# ---------------- 3a) 到期分级主体 ----------------
A_OLD = (
    '        # ---- \u5230\u671f\u5904\u7406: \u8d85\u8fc7\u7b49\u5f85\u5468\u671f ----' + NL +
    '        waited = held_trd_days(h.get(\'plan_date\', \'\'))' + NL +
    '        if PYRAMID_MAX_WAIT_TRDAYS > 0 and waited > PYRAMID_MAX_WAIT_TRDAYS:' + NL +
    '            if PYRAMID_EXPIRE_MODE == \'fill\' and remain >= 100:' + NL
)
A_NEW = (
    '        # ---- \u5230\u671f\u5904\u7406: \u8d85\u51fa\u6700\u957f\u7b49\u5f85 ----' + NL +
    '        waited = held_trd_days(h.get(\'plan_date\', \'\'))' + NL +
    '        # ---- [2026-10-20 V2.6.102] \u5230\u671f\u5206\u7ea7: \u8d62\u5bb6\u7ed9\u673a\u4f1a(\u5ef6\u957f\u7b49\u5f85), \u8f93\u5bb6\u4e0d\u8865\u4ed3 ----' + NL +
    '        #  \u8001\u6bdb\u75c5: \u5230\u671f\u4e0d\u5206\u597d\u574f\u4e00\u89c6\u540c\u4ec1 \u2014\u2014 \u8fd8\u5728\u8d5a\u94b1\u7684\u7968(\u53ea\u662f\u8fd9\u51e0\u5929\u4e00\u76f4\u6ca1\u56de\u8c03\u5230\u4f4e\u4f4d)' + NL +
    '        #  \u88ab\u786c\u780d\u6389\u5269\u4f59\u4ed3\u4f4d, \u4e8f\u94b1\u7684\u7968\u53cd\u800c\u53ef\u80fd\u88ab fill \u4e00\u6b21\u6027\u8865\u9f50(\u8d8a\u4e8f\u8d8a\u8865, \u4ed3\u4f4d\u8d8a\u91cd\u8d8a\u96be\u7ffb\u8eab)' + NL +
    '        #  \u6539\u6cd5: \u6d6e\u76c8(\u73b0\u4ef7 > \u6301\u4ed3\u6210\u672c) -> \u7b49\u5f85\u671f +3 \u4e2a\u4ea4\u6613\u65e5, \u591a\u7ed9\u51e0\u6b21\u56de\u8c03\u673a\u4f1a;' + NL +
    '        #          \u6d6e\u4e8f(\u73b0\u4ef7 <= \u6301\u4ed3\u6210\u672c) -> \u5230\u671f\u5c31\u4f5c\u5e9f\u5269\u4f59\u8ba1\u5212, \u4e14\u7ed5\u5f00 fill(\u7edd\u4e0d\u8865\u4ed3)\u3002' + NL +
    '        #  \u53ea\u51b3\u5b9a"\u8fd8\u7b49\u4e0d\u7b49 / \u8865\u4e0d\u8865", \u4e0d\u78b0\u5356\u51fa\u5224\u636e\u3001\u4e0d\u78b0\u6b62\u635f\u3002' + NL +
    '        _ex_cvol = pos_vol(h)' + NL +
    '        _ex_cost = (pos_cost(h) / _ex_cvol) if _ex_cvol > 0 else _f(h.get(\'buy_price\', 0) or 0)' + NL +
    '        _ex_win = _ex_cost > 0 and lp > _ex_cost' + NL +
    '        _ex_wait = (PYRAMID_MAX_WAIT_TRDAYS + 3) if _ex_win else PYRAMID_MAX_WAIT_TRDAYS' + NL +
    '        if PYRAMID_MAX_WAIT_TRDAYS > 0 and waited > _ex_wait:' + NL +
    '            if not _ex_win:' + NL +
    '                # \u8f93\u5bb6: \u5230\u671f\u7acb\u5373\u653e\u5f03, \u4e0d\u8865\u4ed3(fill \u8def\u7ebf\u4e5f\u7ed5\u5f00)' + NL +
    '                if h.get(\'pyr_note_date\') != G.today:' + NL +
    '                    h[\'pyr_note_date\'] = G.today' + NL +
    '                    log(disp(s), \'\u52a0\u4ed3\u5230\u671f\u653e\u5f03(\u8f93\u5bb6): \u5df2\u7b49%d\u4e2a\u4ea4\u6613\u65e5, \u73b0\u4ef7%.2f<=\u6210\u672c%.2f(\u6d6e\u4e8f), \'' + NL +
    '                           \'\u5269\u4f59%d\u80a1\u4e0d\u518d\u8865\u4ed3, \u5269\u4f59\u8ba1\u5212\u4f5c\u5e9f(\u7968\u7ee7\u7eed\u6301\u6709, \u7edd\u4e0d\u6b62\u635f)\'' + NL +
    '                           % (waited, lp, _ex_cost, int(remain)))' + NL +
    '                h[\'plan_done\'] = True' + NL +
    '                continue' + NL +
    '            if PYRAMID_EXPIRE_MODE == \'fill\' and remain >= 100:' + NL
)
rep(A_OLD, A_NEW, 'expire-tier-main')

# ---------------- 3b) 赢家延长提示(每日限一条) ----------------
B_OLD = (
    '            h[\'plan_done\'] = True' + NL +
    '            continue' + NL +
    '        # ---- \u5e38\u89c4\u6279\u6b21: \u4ef7\u683c\u4f4d\u7f6e + \u8ffd\u9ad8 + \u95f4\u9694 + \u5f53\u65e5\u6279\u6b21 + \u73b0\u91d1 ----' + NL
)
B_NEW = (
    '            h[\'plan_done\'] = True' + NL +
    '            continue' + NL +
    '        elif (PYRAMID_MAX_WAIT_TRDAYS > 0 and _ex_win and waited > PYRAMID_MAX_WAIT_TRDAYS' + NL +
    '              and h.get(\'pyr_ext_note_date\') != G.today):' + NL +
    '            # \u8d62\u5bb6: \u5df2\u8fc7\u539f\u7b49\u5f85\u671f\u4f46\u5c1a\u5728\u5ef6\u957f\u671f\u5185, \u6bcf\u5929\u63d0\u9192\u4e00\u6b21' + NL +
    '            h[\'pyr_ext_note_date\'] = G.today' + NL +
    '            log(disp(s), \'\u52a0\u4ed3\u7b49\u5f85\u5ef6\u957f(\u8d62\u5bb6): \u5df2\u7b49%d\u4e2a\u4ea4\u6613\u65e5, \u73b0\u4ef7%.2f>\u6210\u672c%.2f(\u6d6e\u76c8), \'' + NL +
    '                   \'\u7b49\u5f85\u671f\u5ef6\u81f3%d\u4e2a\u4ea4\u6613\u65e5\u7ee7\u7eed\u7b49\u56de\u8c03(\u672a\u56de\u8c03\u5219\u4e0d\u8865\u4ed3)\'' + NL +
    '                   % (waited, lp, _ex_cost, _ex_wait))' + NL +
    '        # ---- \u5e38\u89c4\u6279\u6b21: \u4ef7\u683c\u4f4d\u7f6e + \u8ffd\u9ad8 + \u95f4\u9694 + \u5f53\u65e5\u6279\u6b21 + \u73b0\u91d1 ----' + NL
)
rep(B_OLD, B_NEW, 'expire-tier-extend-note')

out = t.encode('gbk')
io.open(SRC, 'wb').write(out)
print('NEW_BYTES=%d DELTA=%d  CRLF=%d  LINES=%d' % (
    len(out), len(out) - orig, t.count(NL), len(t.split(NL))))

for fn in ['def run_pyramid_adds', 'def run_round', 'def pyramid_add', 'def sell_stock',
           'def buy_stock', 'def pos_cost', 'def held_trd_days', 'def pyramid_remain']:
    if fn not in t:
        raise SystemExit('LOST FUNC: %s' % fn)
print('ALL_FUNC_ANCHORS_OK')
py_compile.compile(SRC, doraise=True)
print('PY_COMPILE_OK  MD5=%s' % hashlib.md5(out).hexdigest().upper())
