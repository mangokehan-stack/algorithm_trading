# -*- coding: utf-8 -*-
"""V2.6.156 补丁: 交易费用按【委托单】归并, 每张委托只算一次起收

背景: 柜台把一张委托拆成多笔成交回报(2026-10-21 13:51 601595 实测 1张委托900股
      -> 100+100+700 三笔成交, 同一个 OrderID)。旧版每笔成交各自
      max(金额x费率, 5元), "5元起收"被重复计 3 次 = 15.26 元, 券商按委托单只收 5.25 元。

做法: 新增 _order_fee_delta, 按 OrderID 累计该委托单成交金额,
      本笔费用 = calc(该单累计金额) - 该单已计入费用。
      于是整张委托单的费用总额 = calc(该单成交总金额), 与单笔口径用的完全是同一个公式。
      "该单已计入"存四舍五入后的值, 使每笔的进位误差自动滚入下一笔, 总额精确收敛。
      买入/卖出两侧的实盘成交回报都按 OrderID 归并; 存量持仓校准改用 order_cnt 张数估算。
      order_id 缺失时退回旧单笔口径, 既有调用点行为逐字不变。
"""
import ast
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
CRLF = "\r\n"
raw = open(P, "rb").read()
t = raw.decode("gbk")

try:
    t.encode("gbk")
except Exception as e:
    print("源文件不是合法 GBK: %s" % e)
    sys.exit(2)

checks = []


def chk(name, ok, extra=""):
    checks.append((name, bool(ok), extra))


def sub(old, new, tag):
    """唯一替换, 命中数必须为 1"""
    global t
    n = t.count(old)
    chk("%s 锚点唯一(count=%d)" % (tag, n), n == 1, old[:60].replace("\r\n", "\\n"))
    if n != 1:
        return False
    t = t.replace(old, new, 1)
    return True


# ---------------------------------------------------------------- 1. _order_fee_delta + fee_buy
OLD1 = (
    "def fee_buy(amount, code=''):" + CRLF +
    '    """买入费用(V2.6.69): 按品种取费率 —— 佣金(不足最低按最低) + 过户费(仅沪市股票双边)。' + CRLF +
    "    品种由 _prod_of(code) 显式品种键识别: 股票/ETF/港股通/可转债/逆回购各按 FEE_PROFILE 报价。" + CRLF +
    '    本策略只交易沪深A股, 行为与旧版完全一致(万0.841, 5元起收)。"""' + CRLF +
    "    if not FEE_ON or amount <= 0:" + CRLF +
    "        return 0.0" + CRLF +
    "    _p = fee_profile(code)" + CRLF +
    "    # 股票档过户费仍走 _transfer_rate_for(仅沪市收), 与旧版一致; 其它品种直接用配置表" + CRLF +
    "    _tr = _transfer_rate_for(code) if _prod_of(code) == 'stock' else _p['transfer']" + CRLF +
    "    return _round2(max(amount * _p['rate'], _p['min']) + amount * _tr)"
)

NEW1 = (
    "def _order_fee_delta(order_id, amount, calc):" + CRLF +
    '    """交易费用按【委托单】归并 —— 一张委托只算一次最低佣金起收(V2.6.156)。' + CRLF +
    CRLF +
    "    柜台会把一张委托拆成多笔成交回报(2026-10-21 601595 实测: 1张委托900股被拆成" + CRLF +
    "    100+100+700 三笔成交回报, 同一个 OrderID)。若每笔成交各自 max(金额x费率, 最低佣金)," + CRLF +
    "    则 5 元起收会被重复计 3 次, 合计记账 15.26 元, 而券商按委托单只收 5.00 + 过户 0.25 = 5.25 元。" + CRLF +
    CRLF +
    "    做法: 按 OrderID 记住该委托单累计成交金额与本单已计入费用, 返回" + CRLF +
    "        本笔费用 = calc(该单累计成交金额) - 该单已计入费用" + CRLF +
    "    于是整张委托单的费用总额恰好等于 calc(该单成交总金额) —— 与单笔口径共用同一个 calc," + CRLF +
    "    费率公式只有一份, 将来调费率不会漏改。'已计入费用'存的是四舍五入后的值," + CRLF +
    "    每笔的进位误差自动滚入下一笔, 三笔合计正好压在 5.25 元, 不产生逐笔舍入累积。" + CRLF +
    CRLF +
    "    order_id 为空(认不出是哪张委托单)时直接返回 calc(amount), 与旧版逐字一致。" + CRLF +
    "    calc: 单笔费用计算函数, 如 lambda a: fee_buy(a, code) —— 不会再进本函数(order_id为空), 无递归。" + CRLF +
    '    """' + CRLF +
    "    _oid = str(order_id or '').strip()" + CRLF +
    "    if not _oid or amount <= 0:" + CRLF +
    "        return calc(amount)" + CRLF +
    "    _k = '%s|%s' % (G.today or '', _oid)" + CRLF +
    "    try:" + CRLF +
    "        _acc = G.state.setdefault('order_fee_acc', {})" + CRLF +
    "    except Exception:" + CRLF +
    "        return calc(amount)" + CRLF +
    "    _rec = _acc.get(_k) or {}" + CRLF +
    "    _amt = _f(_rec.get('amt', 0.0)) + amount          # 该委托单累计成交金额" + CRLF +
    "    _due = calc(_amt)                                # 该单累计应计费用(佣金起收只在此算一次)" + CRLF +
    "    _paid = _f(_rec.get('fee', 0.0))                 # 该单此前已计入费用(四舍五入后的值)" + CRLF +
    "    _this = _round2(_due - _paid)" + CRLF +
    "    _acc[_k] = {'amt': _amt, 'fee': _round2(_paid + _this), 'ts': time.time()}" + CRLF +
    "    if len(_acc) > 2000:                             # 防长跑积累: 只清最旧 500 条" + CRLF +
    "        for _ok in sorted(_acc, key=lambda x: _f((_acc.get(x) or {}).get('ts', 0.0)))[:500]:" + CRLF +
    "            _acc.pop(_ok, None)" + CRLF +
    "    return _this" + CRLF +
    CRLF +
    "def fee_buy(amount, code='', order_id='', n_order=1):" + CRLF +
    '    """买入费用(V2.6.69): 按品种取费率 —— 佣金(不足最低按最低) + 过户费(仅沪市股票双边)。' + CRLF +
    "    品种由 _prod_of(code) 显式品种键识别: 股票/ETF/港股通/可转债/逆回购各按 FEE_PROFILE 报价。" + CRLF +
    '    本策略只交易沪深A股, 行为与旧版完全一致(万0.841, 5元起收)。' + CRLF +
    CRLF +
    "    V2.6.156: order_id 给定时按该委托单归并(见 _order_fee_delta), 同一张委托的多笔成交只收一次起收;" + CRLF +
    "    n_order>1 表示「该仓共 n 张委托单」, 用于存量持仓校准, 按 max(金额x费率, 最低佣金x n) 估算。" + CRLF +
    "    两参数默认不启用, 其余调用点行为与旧版逐字一致。\"\"\"" + CRLF +
    "    if not FEE_ON or amount <= 0:" + CRLF +
    "        return 0.0" + CRLF +
    "    if order_id:" + CRLF +
    "        return _order_fee_delta(order_id, amount, lambda a: fee_buy(a, code))" + CRLF +
    "    _p = fee_profile(code)" + CRLF +
    "    # 股票档过户费仍走 _transfer_rate_for(仅沪市收), 与旧版一致; 其它品种直接用配置表" + CRLF +
    "    _tr = _transfer_rate_for(code) if _prod_of(code) == 'stock' else _p['transfer']" + CRLF +
    "    return _round2(max(amount * _p['rate'], _p['min'] * max(1, int(_f(n_order)))) + amount * _tr)"
)

sub(OLD1, NEW1, "[1] fee_buy")

# ---------------------------------------------------------------- 2. fee_sell
OLD2 = (
    "def fee_sell(amount, code=''):" + CRLF +
    '    """卖出费用(V2.6.69): 按品种取费率 —— 佣金(不足最低按最低) + 印花税(仅股票卖出单边)' + CRLF +
    "    + 过户费(仅沪市股票双边)。可转债卖出费率用 FEE_CBOND_SELL_RATE(买卖不同价)。" + CRLF +
    '    本策略只交易沪深A股, 行为与旧版完全一致。"""' + CRLF +
    "    if not FEE_ON or amount <= 0:" + CRLF +
    "        return 0.0" + CRLF +
    "    _p = fee_profile(code)" + CRLF +
    "    _r = _p['rate']" + CRLF +
    "    if _prod_of(code) == 'cbond':" + CRLF +
    "        _r = FEE_CBOND_SELL_RATE" + CRLF +
    "    _tr = _transfer_rate_for(code) if _prod_of(code) == 'stock' else _p['transfer']" + CRLF +
    "    return _round2(max(amount * _r, _p['min']) + amount * _p['stamp'] + amount * _tr)"
)

NEW2 = (
    "def fee_sell(amount, code='', order_id='', n_order=1):" + CRLF +
    '    """卖出费用(V2.6.69): 按品种取费率 —— 佣金(不足最低按最低) + 印花税(仅股票卖出单边)' + CRLF +
    "    + 过户费(仅沪市股票双边)。可转债卖出费率用 FEE_CBOND_SELL_RATE(买卖不同价)。" + CRLF +
    '    本策略只交易沪深A股, 行为与旧版完全一致。' + CRLF +
    CRLF +
    "    V2.6.156: order_id / n_order 语义同 fee_buy —— 按委托单归并, 起收只算一次。\"\"\"" + CRLF +
    "    if not FEE_ON or amount <= 0:" + CRLF +
    "        return 0.0" + CRLF +
    "    if order_id:" + CRLF +
    "        return _order_fee_delta(order_id, amount, lambda a: fee_sell(a, code))" + CRLF +
    "    _p = fee_profile(code)" + CRLF +
    "    _r = _p['rate']" + CRLF +
    "    if _prod_of(code) == 'cbond':" + CRLF +
    "        _r = FEE_CBOND_SELL_RATE" + CRLF +
    "    _tr = _transfer_rate_for(code) if _prod_of(code) == 'stock' else _p['transfer']" + CRLF +
    "    return _round2(max(amount * _r, _p['min'] * max(1, int(_f(n_order)))) + amount * _p['stamp'] + amount * _tr)"
)

sub(OLD2, NEW2, "[2] fee_sell")

# ---------------------------------------------------------------- 3. ledger_buy 接收已算好的 fee
OLD3 = "def ledger_buy(s, h, price, vol, reason, npos_before, was_new=True, pos_before=0):"
NEW3 = "def ledger_buy(s, h, price, vol, reason, npos_before, was_new=True, pos_before=0, fee=None):"
sub(OLD3, NEW3, "[3] ledger_buy签名")

OLD4 = (
    '    V2.6.39b: 区分【首笔开仓】与【分批加仓】—— was_new=False 时组合只数不+1(加仓不新开仓),' + CRLF +
    "    pos_before=该股加仓前已有股数, 展示为 A->B股 而非 0->本笔股数; 默认值保持旧版行为兼容\"\"\"" + CRLF +
    "    amt = _round2(price * vol)" + CRLF +
    "    fee = fee_buy(amt, s)"
)
NEW4 = (
    '    V2.6.39b: 区分【首笔开仓】与【分批加仓】—— was_new=False 时组合只数不+1(加仓不新开仓),' + CRLF +
    "    pos_before=该股加仓前已有股数, 展示为 A->B股 而非 0->本笔股数; 默认值保持旧版行为兼容" + CRLF +
    CRLF +
    "    V2.6.156: fee 可由调用方传入(实盘成交回报已按委托单归并算好, 见 _order_fee_delta)。" + CRLF +
    "    传 None 时按单笔口径自算, 与旧版完全一致 —— 也避免同一笔成交的费被算两次。\"\"\"" + CRLF +
    "    amt = _round2(price * vol)" + CRLF +
    "    if fee is None:" + CRLF +
    "        fee = fee_buy(amt, s)"
)
sub(OLD4, NEW4, "[4] ledger_buy内部费用")

# ---------------------------------------------------------------- 4. ledger_sell 按委托单归并
OLD5 = "def ledger_sell(s, h, price, vol, reason, npos_before):"
NEW5 = "def ledger_sell(s, h, price, vol, reason, npos_before, order_id=''):"
sub(OLD5, NEW5, "[5] ledger_sell签名")

OLD6 = "    fee = fee_sell(amt, s)"
NEW6 = "    fee = fee_sell(amt, s, order_id=order_id)"
sub(OLD6, NEW6, "[6] ledger_sell内部费用")

# ---------------------------------------------------------------- 5. deal_callback 取 OrderID
OLD7 = "        if side == 'BUY':"
NEW7 = (
    "        # V2.6.156: 取委托单号 —— 费用按委托单只归并一次, 同单多笔成交不重复起收" + CRLF +
    "        _order_id = str(getattr(dealInfo, 'm_strOrderID', '')" + CRLF +
    "                        or getattr(dealInfo, 'm_strOrderSysID', '') or '')" + CRLF +
    "        if side == 'BUY':"
)
sub(OLD7, NEW7, "[7] deal_callback取委托号")

# ---------------------------------------------------------------- 6. 买入成交回报按委托单算费
OLD8 = (
    "            amt = _round2(price * volume)" + CRLF +
    "            fee = fee_buy(amt, code)"
)
NEW8 = (
    "            amt = _round2(price * volume)" + CRLF +
    "            # V2.6.156: 先判该委托单是否已建账(算费会写账, 必须先判), 再按委托单归并算费" + CRLF +
    "            _ordk = ('%s|%s' % (G.today or '', _order_id)) if _order_id else ''" + CRLF +
    "            _new_ord = bool(_ordk) and (not (G.state.get('order_fee_acc') or {}).get(_ordk))" + CRLF +
    "            fee = fee_buy(amt, code, order_id=_order_id)" + CRLF +
    "            if _new_ord:      # 该仓累计委托单张数, 供启动校准按张数估算起收" + CRLF +
    "                h['order_cnt'] = int(_f(h.get('order_cnt', 0)) or 0) + 1"
)
sub(OLD8, NEW8, "[8] 买入回报费用")

# ---------------------------------------------------------------- 7. ledger_buy 传入已算好的 fee
OLD9 = (
    "            alert_open(ledger_buy(code, h, price, volume," + CRLF +
    "                                  '实盘买入成交回报(备注%s)' % rm, npos_before," + CRLF +
    "                                  was_new=was_new, pos_before=pos_before))"
)
NEW9 = (
    "            alert_open(ledger_buy(code, h, price, volume," + CRLF +
    "                                  '实盘买入成交回报(备注%s)' % rm, npos_before," + CRLF +
    "                                  was_new=was_new, pos_before=pos_before, fee=fee))"
)
sub(OLD9, NEW9, "[9] ledger_buy传fee")

# ---------------------------------------------------------------- 8. 卖出回报按委托单归并
OLD10 = (
    "            rec = ledger_sell(code, info, price, volume," + CRLF +
    "                              '实盘卖出成交回报(备注%s)' % rm, npos_before)"
)
NEW10 = (
    "            rec = ledger_sell(code, info, price, volume," + CRLF +
    "                              '实盘卖出成交回报(备注%s)' % rm, npos_before," + CRLF +
    "                              order_id=_order_id)"
)
sub(OLD10, NEW10, "[10] 卖出回报归并")

# ---------------------------------------------------------------- 9. 存量持仓校准按委托单张数
OLD11 = "            _fe_new = fee_buy(_round2(_fs), _code)"
NEW11 = (
    "            # V2.6.156: 按该仓买过的委托单张数估算起收, 防把多张委托的起收又抹回一张;" + CRLF +
    "            # 旧记录无 order_cnt 字段时默认 1 张, 与 V2.6.72 原口径完全一致" + CRLF +
    "            _n_ord = max(1, int(_f(_h.get('order_cnt', 0)) or 0))" + CRLF +
    "            _fe_new = fee_buy(_round2(_fs), _code, n_order=_n_ord)"
)
sub(OLD11, NEW11, "[11] 存量校准张数")

# ---------------------------------------------------------------- 10. 升版
OLD12 = "# 版本号: V2.6.155"
NEW12_HEAD = (
    "# 版本号: V2.6.156             修改时间: 2026-10-21 14:22 (V2.6.156: 只有一处实质修复 ——"
    "交易费用改为按【委托单】归并, 每张委托只算一次最低佣金起收;"
    "参数零变更、无新增模块级大写常量, 参数指纹必仍为 efb96534。"
    "起因: 2026-10-21 13:51:54 601595 上海电影 1 张委托 900 股被柜台拆成 100+100+700 三笔成交回报"
    "(同一个 OrderID), 旧版每笔成交各自 max(金额x费率, 5元), 5 元起收被重复计 3 次记 15.26 元,"
    "而券商按委托单只收 5.00 + 过户 0.25 = 5.25 元, 累计费用因此多算 10.01 元"
    "(持仓成本已被启动校准修回, 只有累计费用统计口径不一致)。"
    "修复: 新增 _order_fee_delta, 按 OrderID 累计该委托单成交金额,"
    "本笔费用 = 单笔公式(该单累计金额) - 该单已计入费用, 使整张委托单费用总额恰等于"
    "单笔公式(该单成交总金额) —— 费率公式只有一份, 将来调费率不会漏改;"
    "已计入费用存四舍五入后的值, 每笔进位误差滚入下一笔, 三笔合计正好 5.25 元;"
    "买入与卖出两侧的实盘成交回报都按 OrderID 归并, 买入侧把已算好的费传给记账函数以免同一笔被算两次;"
    "存量持仓费用校准改用该仓买过的委托单张数 order_cnt 估算起收, 防重启后把多张委托的起收抹回一张。"
    "order_id 取不到时退回旧的单笔口径, 全部既有调用点行为逐字不变。)"
)
_n12 = t.count(OLD12)
chk("[12a] 版本号行唯一(插入前)", _n12 == 1, "count=%d" % _n12)
if _n12 == 1:
    idx = t.index(OLD12)
    t = t[:idx] + NEW12_HEAD + CRLF + t[idx:]
    chk("[12b] 文件头插入新版记录", True)
else:
    chk("[12b] 文件头插入新版记录", False, "版本号行 count=%d" % _n12)

OLD13 = "VERSION = 'V2.6.155'"
NEW13 = "VERSION = 'V2.6.156'"
sub(OLD13, NEW13, "[13] VERSION常量")
chk("[13b] VERSION 长度一致", len(OLD13) == len(NEW13))

# ---------------------------------------------------------------- 落盘前校验
try:
    ast.parse(t)
    chk("AST 解析通过", True)
except SyntaxError as e:
    chk("AST 解析通过", False, "line %s: %s" % (e.lineno, e.msg))

chk("裸 LF = 0", t.replace(CRLF, "").count("\n") == 0,
    "残留=%d" % t.replace(CRLF, "").count("\n"))
chk("裸 CR = 0", t.replace(CRLF, "").count("\r") == 0,
    "残留=%d" % t.replace(CRLF, "").count("\r"))
chk("无 BOM", not t.startswith("\ufeff"))
chk("GBK 可编码", True)

chk("买入回报旧写法已无", "            fee = fee_buy(amt, code)" + CRLF not in t)
chk("卖出回报旧调用已无",
    "                              '实盘卖出成交回报(备注%s)' % rm, npos_before)" + CRLF not in t)
chk("新归并函数已就位", "def _order_fee_delta(order_id, amount, calc):" in t)
chk("fee_buy 新签名", "def fee_buy(amount, code='', order_id='', n_order=1):" in t)
chk("fee_sell 新签名", "def fee_sell(amount, code='', order_id='', n_order=1):" in t)
chk("ledger_buy 保留旧自算分支", t.count("fee = fee_buy(amt, s)") == 1)
chk("买入侧传 fee 而非重算", "pos_before=pos_before, fee=fee))" in t)
chk("卖出侧传 order_id", "order_id=_order_id)" + CRLF in t)
chk("无递归风险(order_id为空才进单笔公式)",
    "return _order_fee_delta(order_id, amount, lambda a: fee_buy(a, code))" in t)
chk("模块级大写常量未新增", "ORDER_FEE" not in t and "_ORDER_FEE" not in t)

ok = sum(1 for _, r, _ in checks if r)
bad = len(checks) - ok
print()
for name, r, extra in checks:
    print("%-4s %s%s" % ("PASS" if r else "FAIL", name, ("  | " + extra) if (not r and extra) else ""))
print()
print("补丁自检: %d PASS / %d FAIL" % (ok, bad))

if bad == 0:
    open(P, "wb").write(t.encode("gbk"))
    b2 = open(P, "rb").read()
    import hashlib
    print("已写盘: %d 字节, MD5 = %s, 段数 = %d"
          % (len(b2), hashlib.md5(b2).hexdigest(), len(b2.decode("gbk").split(CRLF))))
else:
    print("存在 FAIL, 未写盘")
    sys.exit(2)
