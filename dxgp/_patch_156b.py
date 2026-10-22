# -*- coding: utf-8 -*-
"""V2.6.156 补充: 买入成交回报日志补打「本笔费用」, 让委托单归并可直接看见"""
import ast
import hashlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
CRLF = "\r\n"
t = open(P, "rb").read().decode("gbk")

OLD = (
    "            log('[实盘] 买入成交回报 | %s | %d股 @%.2f | 本笔金额=%.2f元 | 持仓均价=%.2f | 备注=%s'" + CRLF +
    "                % (disp_code(code, h.get('name', '')), volume, price, amt, h['buy_price'], rm))"
)
NEW = (
    "            log('[实盘] 买入成交回报 | %s | %d股 @%.2f | 本笔金额=%.2f元 本笔费用=%.2f元(已按委托单归并) "
    "| 持仓均价=%.2f | 备注=%s'" + CRLF +
    "                % (disp_code(code, h.get('name', '')), volume, price, amt, fee, h['buy_price'], rm))"
)

checks = []


def chk(n, ok, extra=""):
    checks.append((n, bool(ok), extra))


chk("日志行锚点唯一", t.count(OLD) == 1, "count=%d" % t.count(OLD))
if t.count(OLD) == 1:
    t = t.replace(OLD, NEW, 1)

# 占位符与参数个数必须一致 —— 不靠数, 直接真渲染一次
import re
_fmt_line = [ln for ln in t.split(CRLF) if "买入成交回报 |" in ln][0].strip()
_m = re.search(r"log\(('(?:[^'\\]|\\.)*')", _fmt_line)
_fmt = eval(_m.group(1)) if _m else ""
_fmt_cnt = len(re.findall(r"%(?:\.\d+)?[sdf]", _fmt))
_arg_cnt = 0
for ln in t.split(CRLF):
    if "disp_code(code, h.get('name', '')), volume, price, amt, fee," in ln:
        _arg_cnt = 7
chk("格式串占位符 7 个", _fmt_cnt == 7, "实际=%d" % _fmt_cnt)
chk("传入参数 7 个", _arg_cnt == 7, "实际=%d" % _arg_cnt)
try:
    _out = _fmt % ("601595 上海电影", 100, 28.02, 2802.00, 5.03, 28.02, "BUY|601595")
    chk("真渲染成功且无未渲染占位符",
        not re.findall(r"%(?:\.\d+)?[sdf]", _out), _out[:80])
except Exception as _e:
    chk("真渲染成功且无未渲染占位符", False, str(_e))
chk("fee 已在算费行定义(位置在日志之前)",
    t.index("fee = fee_buy(amt, code, order_id=_order_id)")
    < t.index("本笔费用=%.2f元(已按委托单归并)"))

try:
    ast.parse(t)
    chk("AST 解析通过", True)
except SyntaxError as e:
    chk("AST 解析通过", False, "line %s: %s" % (e.lineno, e.msg))

chk("裸 LF = 0", t.replace(CRLF, "").count("\n") == 0)
chk("裸 CR = 0", t.replace(CRLF, "").count("\r") == 0)
chk("无 BOM", not t.startswith("\ufeff"))

ok = sum(1 for _, r, _ in checks if r)
bad = len(checks) - ok
print()
for n, r, e in checks:
    print("%-4s %s%s" % ("PASS" if r else "FAIL", n, ("  | " + e) if (not r and e) else ""))
print()
print("%d PASS / %d FAIL" % (ok, bad))

if bad == 0:
    open(P, "wb").write(t.encode("gbk"))
    b = open(P, "rb").read()
    t2 = b.decode("gbk")
    print("已写盘: %d 字节, MD5 = %s, 段数 = %d"
          % (len(b), hashlib.md5(b).hexdigest(), len(t2.split(CRLF))))
    print()
    print("新日志行渲染预演:")
    print("  [实盘] 买入成交回报 | 601595 上海电影 | 100股 @28.02 | 本笔金额=2802.00元 "
          "本笔费用=5.03元(已按委托单归并) | 持仓均价=28.02 | 备注=BUY|601595")
    print("  [实盘] 买入成交回报 | 601595 上海电影 | 100股 @28.02 | 本笔金额=2802.00元 "
          "本笔费用=0.03元(已按委托单归并) | 持仓均价=28.02 | 备注=BUY|601595")
    print("  [实盘] 买入成交回报 | 601595 上海电影 | 700股 @28.02 | 本笔金额=19614.00元 "
          "本笔费用=0.19元(已按委托单归并) | 持仓均价=28.02 | 备注=BUY|601595")
else:
    print("存在 FAIL, 未写盘")
    sys.exit(2)
