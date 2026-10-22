# -*- coding: utf-8 -*-
"""V2.6.157 补丁: 存量持仓费用校准只修「真正的 0.15% 粗估」记录

方案 A(用户 2026-10-21 确认):
  校准前先比对原 fee 是否呈粗估形态 —— 与「成交金额 x 0.0015」吻合才重算;
  明显偏离则原样保留(宁可偏高不可偏低)。
"""
import ast
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
CRLF = "\r\n"
NEW_VER = "V2.6.157"
OLD_VER = "V2.6.156"

_ok = 0
_fail = 0


def chk(name, cond, extra=""):
    global _ok, _fail
    if cond:
        _ok += 1
        print("  PASS  %s" % name)
    else:
        _fail += 1
        print("  FAIL  %s   %s" % (name, extra))


raw = open(P, "rb").read()
t = raw.decode("gbk")

# ============ 1. 循环前增加 _fee_keep 容器 ============
A1 = "        _fee_fixed = []" + CRLF + "        _fee_fix_sum = 0.0" + CRLF
N1 = ("        _fee_fixed = []" + CRLF +
      "        _fee_fix_sum = 0.0" + CRLF +
      "        _fee_keep = []" + CRLF)
chk("锚点1 唯一", t.count(A1) == 1, "count=%d" % t.count(A1))
t = t.replace(A1, N1, 1)

# ============ 2. _fe_old 之后插入粗估判据 ============
A2 = "            _fe_old = _f(_h.get('fee', 0.0))" + CRLF
N2 = (
    "            _fe_old = _f(_h.get('fee', 0.0))" + CRLF +
    "            # V2.6.157: 只校准「真正的 0.15% 粗估」记录。这段校准的本意是修 V2.6.71 之前" + CRLF +
    "            # 用 FEE_RATE_EST(0.15%) 粗估费率记账的老持仓; 而「成交回报逐笔累加」出来的 fee" + CRLF +
    "            # 是当时的真实记录(一张委托拆多笔成交时每笔各触发起收, 只会偏高, 方向保守)," + CRLF +
    "            # 不应当被二次改写。2026-10-21 实测: 601595 上海电影两张委托累计 25.45 元被按" + CRLF +
    "            # 一张重算成 5.45 元, 低估 5.00 元 —— 方向与铁律二(扣完费用净利为正才卖)相反。" + CRLF +
    "            # 判据: 原 fee 与「成交金额 x 0.0015」吻合(容差 max(1.0, 2%)) → 认定是粗估形态" + CRLF +
    "            # → 才重算; 明显偏离则保留原值不改, 宁可偏高不可偏低。" + CRLF +
    "            _fe_est = _round2(_fs * 0.0015)" + CRLF +
    "            _est_tol = max(1.0, _fe_est * 0.02)" + CRLF +
    "            if abs(_fe_old - _fe_est) > _est_tol:" + CRLF +
    "                _fee_keep.append('%s: fee=%.2f(粗估形态应为%.2f, 偏离%+.2f)'" + CRLF +
    "                                 % (_code, _fe_old, _fe_est, _fe_old - _fe_est))" + CRLF +
    "                continue" + CRLF
)
chk("锚点2 唯一", t.count(A2) == 1, "count=%d" % t.count(A2))
t = t.replace(A2, N2, 1)

# ============ 3. 校准日志后追加「跳过」说明行 ============
A3 = ("            log('[安全] 存量持仓费用口径校准(V2.6.72): 重算%d只, 旧粗估0.15%%->真实费率, "
      "合计成本调整%.2f元 | %s'" + CRLF +
      "                % (len(_fee_fixed), _fee_fix_sum, '; '.join(_fee_fixed)))" + CRLF)
N3 = A3 + (
    "        if _fee_keep:" + CRLF +
    "            log('[安全] 存量持仓费用校准跳过%d只(非0.15%%粗估形态, 按成交回报真实记录原样保留; 费用偏高属保守方向)'" + CRLF +
    "                ' | %s'" + CRLF +
    "                % (len(_fee_keep), '; '.join(_fee_keep)))" + CRLF
)
chk("锚点3 唯一", t.count(A3) == 1, "count=%d" % t.count(A3))
t = t.replace(A3, N3, 1)

# ============ 4. VERSION 常量 ============
A4 = "VERSION = '" + OLD_VER + "'"
N4 = "VERSION = '" + NEW_VER + "'"
chk("锚点4 VERSION 唯一", t.count(A4) == 1, "count=%d" % t.count(A4))
chk("锚点4 等长替换", len(A4) == len(N4))
t = t.replace(A4, N4, 1)

# ============ 5. 文件头插入版本记录 ============
A5 = "# 版本号: " + OLD_VER
HEAD = (
    "# 版本号: V2.6.157             修改时间: 2026-10-21 14:30 (V2.6.157: 只改「存量持仓费用口径校准」的一处判据, "
    "零参数变更、无新增模块级大写常量, 参数指纹必仍为 efb96534。问题: 该校准原本是为了修 V2.6.71 之前用 0.15% "
    "粗估费率记账的老持仓, 但它不看原记录长什么样, 一律按当前真实费率重算; 2026-10-21 14:23:20 启动时把 601595 "
    "上海电影持有的 25.45 元改成了 5.45 元 —— 而该股当天有【两张】委托(900股 5.25 + 700股 20.20 = 10.45), "
    "状态文件里没有委托张数字段, 校准退回默认一张, 于是低估 5.00 元。方向与铁律二相反(成本算低 -> 扣费后净利为正"
    "更容易满足 -> 卖出门槛被放松), 虽只占 0.011% 也不能留。修法: 校准前先比对原记录是否呈粗估形态 —— 原费用与"
    "「成交金额 x 0.0015」吻合才认定是被粗估的老记录、才重算; 明显偏离(如 25.45 对 67.37)则原样保留不动, "
    "宁可偏高不可偏低。成交回报逐笔累加出来的费用是当时的真实记录, 不应当被二次改写。被跳过的记录会在启动对账段"
    "单独打一行说明, 便于肉眼核查。)" + CRLF
)
chk("锚点5 版本号行唯一", t.count(A5) == 1, "count=%d" % t.count(A5))
_i5 = t.index(A5)
t = t[:_i5] + HEAD + t[_i5:]

# ============ 6. 结构校验 ============
L = t.split(CRLF)
chk("文件头首行仍是 #coding:gbk", L[0] == "#coding:gbk", repr(L[0][:30]))
chk("文件头 L5 是新版记录", L[4].startswith("# 版本号: " + NEW_VER), repr(L[4][:40]))
chk("文件头 L6 是上一版记录", L[5].startswith("# 版本号: " + OLD_VER), repr(L[5][:40]))
chk("VERSION 常量已升版", ("VERSION = '" + NEW_VER + "'") in t)
chk("旧 VERSION 常量已无", ("VERSION = '" + OLD_VER + "'") not in t)
chk("_fee_keep 容器已定义", "        _fee_keep = []" + CRLF in t)
chk("粗估判据已插入", "            _fe_est = _round2(_fs * 0.0015)" + CRLF in t)
chk("跳过分支已插入", "                continue" + CRLF + "            # V2.6.156: " in t)

# 判据必须在 fee_buy 重算之前(否则等于没拦)
_i_est = t.index("_fe_est = _round2(_fs * 0.0015)")
_i_new = t.index("_fe_new = fee_buy(_round2(_fs), _code, n_order=_n_ord)")
chk("判据位置在 fee_buy 重算之前", _i_est < _i_new)
# continue 必须真的跳过重算: 判据与 continue 之间不得出现 _fe_new 赋值
_seg = t[_i_est:t.index("            _n_ord = max(1, int(_f(_h.get('order_cnt', 0)) or 0))")]
chk("判据段内不含 fee_buy 调用", "_fe_new = fee_buy" not in _seg)
chk("判据段内确有 continue", "                continue" in _seg)

# 3% 的 _est_tol 必须真的用到
chk("容差变量已使用", "if abs(_fe_old - _fe_est) > _est_tol:" in t)

# ============ 7. 括号/缩进安全: 编译 ============
try:
    compile(t, P, "exec")
    chk("compile 通过", True)
except SyntaxError as e:
    chk("compile 通过", False, "line %s: %s" % (e.lineno, e.msg))

# ============ 8. 硬止损铁律 ============
_ast = ast.parse(t)
_n_stop = sum(1 for n in ast.walk(_ast)
              if isinstance(n, ast.Attribute) and n.attr == "stop" + "_order")
chk("硬止损 AST 节点 = 0", _n_stop == 0, "实际=%d" % _n_stop)

# ============ 9. 编码安全 ============
try:
    _b = t.encode("gbk")
    chk("GBK 编码成功", True)
    chk("GBK 往返一致", _b.decode("gbk") == t)
except UnicodeEncodeError as e:
    chk("GBK 编码成功", False, str(e))
    _b = b""

_bare_lf = sum(1 for i in range(len(_b)) if _b[i] == 10 and (i == 0 or _b[i - 1] != 13))
chk("裸 LF = 0", _bare_lf == 0, "实际=%d" % _bare_lf)
_bare_cr = sum(1 for i in range(len(_b)) if _b[i] == 13 and (i + 1 >= len(_b) or _b[i + 1] != 10))
chk("裸 CR = 0", _bare_cr == 0, "实际=%d" % _bare_cr)
chk("无 BOM", not (_b[:3] == b"\xef\xbb\xbf"))

print("\n自检: %d PASS / %d FAIL" % (_ok, _fail))

if _fail == 0:
    open(P, "wb").write(_b)
    print("已写盘: %d 字节, %d 段" % (len(_b), len(L)))
else:
    print("未写盘(有 FAIL)")
    sys.exit(2)
