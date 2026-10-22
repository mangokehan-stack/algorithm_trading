# -*- coding: utf-8 -*-
"""V2.6.157 -> V2.6.158 补丁: 审计问题 1/2/3/4/6 五项修复。
全程二进制读写, 母版保持 GBK + CRLF。锚点一律写 \r\n。
"""
import io, os, sys, hashlib, datetime, ast

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
src = raw.decode('gbk')
assert src.encode('gbk') == raw, 'GBK 往返失败'
print('原文件 %d 字节, %d 字符' % (len(raw), len(src)))

OLD_VER = 'V2.6.157'
NEW_VER = 'V2.6.158'
assert src.count("VERSION = '" + OLD_VER + "'") == 1, 'VERSION 行定位失败'
assert src.count('# 版本号: ' + OLD_VER) == 1, '文件头版本行定位失败'

_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
_old = datetime.datetime(2026, 10, 21, 14, 30)
if _now <= _old.strftime('%Y-%m-%d %H:%M'):
    sys.exit('时间戳异常: 机器时间 %s 不晚于上一版 2026-10-21 14:30' % _now)
print('本次落盘时间 = %s' % _now)

EDITS = []


def add(name, old, new):
    EDITS.append((name, old, new))


def _crlf(s):
    """把任意换行统一成 CRLF: 先把已有 CRLF 换成占位符, 再转裸 LF, 最后还原。"""
    return s.replace('\r\n', '\x00').replace('\n', '\r\n').replace('\x00', '\r\n')


# ---------- ① L5674 排雷装载调用传了函数不接收的参数 ----------
add('1-排雷装载调用',
    "        except Exception as _e146:\r\n"
    "            log('[排雷] 自动抓取异常: %r (后续用旧清单)' % repr(_e146)[:120])\r\n"
    "        load_risk_exclude(force=True)\r\n",
    "        except Exception as _e146:\r\n"
    "            log('[排雷] 自动抓取异常: %r (后续用旧清单)' % repr(_e146)[:120])\r\n"
    "        # V2.6.158: 旧版此处多写了一个 force=True, 而装载函数并不接收任何参数 ——\r\n"
    "        #   一调用就报错, 且这一行不在上面的异常保护范围内, 报错会直接冲出本段:\r\n"
    "        #   后面的加载日线、选股、初始化日期全部被跳过, 排雷清单没抓到的日子整天零候选。\r\n"
    "        try:\r\n"
    "            load_risk_exclude()\r\n"
    "        except Exception as _e158:\r\n"
    "            log('[排雷] 清单装载异常: %r (后续用旧清单)' % repr(_e158)[:120])\r\n")

# ---------- ② L1326-1329 写盘成功无条件解除人工冻结 ----------
add('2-冻结解除',
    "            if G.save_fail_n > 0 or G.state_broken:\r\n"
    "                log('[状态] 状态文件落盘已恢复(此前连续失败%d次), 解除交易禁用' % G.save_fail_n)\r\n"
    "            G.save_fail_n = 0\r\n"
    "            G.state_broken = False\r\n"
    "            return True\r\n",
    "            # V2.6.158: 冻结分两类。写盘失败这一类, 写盘成功即恢复; 但\"持仓容器损坏 /\r\n"
    "            #   状态文件读不出且无备份 / 参数未样本外验证\"这三类原因写着需人工核对,\r\n"
    "            #   写盘成功只证明磁盘可写, 不证明持仓已核对清楚 —— 旧版一律自动解除,\r\n"
    "            #   等于\"停止开新仓 + 推手机告警\"亮三十秒就自己灭掉, 持仓全丢照样开新仓。\r\n"
    "            #   现用 state_broken_lock 单独标记, 写盘成功只清失败计数, 不解冻。\r\n"
    "            if bool(getattr(G, 'state_broken_lock', False)):\r\n"
    "                if G.save_fail_n > 0:\r\n"
    "                    log('[状态] 状态文件落盘已恢复(此前连续失败%d次); '\r\n"
    "                        '但下单冻结仍在, 原因需人工核对后重启策略解除' % G.save_fail_n)\r\n"
    "                G.save_fail_n = 0\r\n"
    "                G.state_broken = True\r\n"
    "                return True\r\n"
    "            if G.save_fail_n > 0 or G.state_broken:\r\n"
    "                log('[状态] 状态文件落盘已恢复(此前连续失败%d次), 解除交易禁用' % G.save_fail_n)\r\n"
    "            G.save_fail_n = 0\r\n"
    "            G.state_broken = False\r\n"
    "            return True\r\n")

# ---------- ② 三处人工冻结打标记 ----------
add('2a-持仓容器损坏',
    "                _bad.append('hold(容器损坏, 停止开新仓需人工核对)')\r\n"
    "                disk['hold'] = {}\r\n"
    "                G.state_broken = True\r\n",
    "                _bad.append('hold(容器损坏, 停止开新仓需人工核对)')\r\n"
    "                disk['hold'] = {}\r\n"
    "                G.state_broken = True\r\n"
    "                G.state_broken_lock = True      # V2.6.158: 人工核对型冻结, 写盘成功不解除\r\n")

add('2b-状态文件读不出',
    "        # 主文件存在但读不出来且无可用备份: 绝不静默退空状态\r\n"
    "        G.state_broken = True\r\n",
    "        # 主文件存在但读不出来且无可用备份: 绝不静默退空状态\r\n"
    "        G.state_broken = True\r\n"
    "        G.state_broken_lock = True          # V2.6.158: 人工核对型冻结, 写盘成功不解除\r\n")

add('2c-状态装载抛异常',
    "    try:\r\n"
    "        G.state = load_state()\r\n"
    "    except Exception:\r\n"
    "        traceback.print_exc()\r\n"
    "        G.state_broken = True\r\n",
    "    try:\r\n"
    "        G.state = load_state()\r\n"
    "    except Exception:\r\n"
    "        traceback.print_exc()\r\n"
    "        G.state_broken = True\r\n"
    "        G.state_broken_lock = True          # V2.6.158: 人工核对型冻结, 写盘成功不解除\r\n")

add('2d-参数指纹强制卡点',
    "                if PARAM_VERIFY_ENFORCE:\r\n"
    "                    G.state_broken = True\r\n",
    "                if PARAM_VERIFY_ENFORCE:\r\n"
    "                    G.state_broken = True\r\n"
    "                    G.state_broken_lock = True  # V2.6.158: 人工核对型冻结, 写盘成功不解除\r\n")

# ---------- ④ 排雷装载缺返回值 ----------
add('4-排雷返回',
    "            log('[排雷][待办] 今日仅依赖实时闸门(ST/财务亏损/仙股/退潮等), 无提前排雷(解禁/减持/立案/预亏)拦截;'\r\n"
    "                ' 请运行 download_risk_exclude.py 生成清单 —— 生成后自动装载, 无需重启策略')\r\n"
    "# -*- coding: utf-8 -*-\r\n",
    "            log('[排雷][待办] 今日仅依赖实时闸门(ST/财务亏损/仙股/退潮等), 无提前排雷(解禁/减持/立案/预亏)拦截;'\r\n"
    "                ' 请运行 download_risk_exclude.py 生成清单 —— 生成后自动装载, 无需重启策略')\r\n"
    "    # V2.6.158: 旧版走完这条真正的读盘分支后直接到函数结尾, 没有把读到的内容交回调用方 ——\r\n"
    "    #   调用方拿到空值, 一律判\"未命中\", 于是每个装载周期里第一只被检查的候选必然漏检。\r\n"
    "    return data if isinstance(data, dict) else {}\r\n"
    "# -*- coding: utf-8 -*-\r\n")

# ---------- ③ 买入费用预填 + 成交回报重复累加 ----------
add('3a-预填打标记',
    "         'fee': _init_fee, 'cost_total': _round2(px * vol + _init_fee), 'last_px': lp,\r\n",
    "         'fee': _init_fee, 'cost_total': _round2(px * vol + _init_fee), 'last_px': lp,\r\n"
    "         # V2.6.158: 预填值只用于\"发单到成交回报\"这段窗口内的闸门口径, 必须留标记,\r\n"
    "         #   否则成交回报会把真实费用叠加在预填值上, 一笔买入的费用被记两遍。\r\n"
    "         'fee_pre': _init_fee,\r\n")

add('3b-首笔成交清预填',
    "            was_new = int(_f(h.get('fill_vol', 0) or 0)) <= 0   # 本笔是否该股首笔成交(分批第2/3批不是新开仓)\r\n"
    "            h['fill_sum'] += price * volume\r\n",
    "            was_new = int(_f(h.get('fill_vol', 0) or 0)) <= 0   # 本笔是否该股首笔成交(分批第2/3批不是新开仓)\r\n"
    "            if _f(h.get('fee_pre', 0.0)) > 0:\r\n"
    "                # V2.6.158: 首笔成交回报到达时先清掉发单占位预填的估算费用, 再按真实费用重算。\r\n"
    "                #   旧版从不重置, 回报又累加一次 —— 实测一张 900 股委托真实 5.25 元记成 10.50 元,\r\n"
    "                #   成本虚高一倍, 会抬高\"扣完全部费用真赚钱才卖\"这道门槛, 变成该卖不卖。\r\n"
    "                #   非首笔却仍带标记属异常路径: 保留原值不清(宁可偏高), 只清标记防残留。\r\n"
    "                if was_new:\r\n"
    "                    h['fee'] = 0.0\r\n"
    "                    h['cost_total'] = 0.0\r\n"
    "                h.pop('fee_pre', None)\r\n"
    "            h['fill_sum'] += price * volume\r\n")

# ---------- ⑥ 8 位年月日被当成 1970 年起的秒数 ----------
add('6-财务日期',
    "    try:\r\n"
    "        if isinstance(t, str) and t.strip().isdigit():\r\n"
    "            t = int(t.strip())\r\n"
    "        if isinstance(t, (int, float)):\r\n"
    "            ts = t / 1000.0 if t > 10 ** 12 else float(t)   # 毫秒 vs 秒\r\n",
    "    try:\r\n"
    "        if isinstance(t, str) and t.strip().isdigit():\r\n"
    "            t = int(t.strip())\r\n"
    "        if isinstance(t, (int, float)) and not isinstance(t, bool):\r\n"
    "            # V2.6.158: 八位整数形态(19000101~29991231)本身就是年月日, 不是 1970 年起的秒数。\r\n"
    "            #   旧版一律按秒换算, 20260930 会被解成 1970 年 8 月 23 日, 报告期被判严重滞后,\r\n"
    "            #   财务数据被整批过滤掉且日志只写过滤正常。\r\n"
    "            if 19000101 <= t <= 29991231 and float(t) == int(t):\r\n"
    "                return str(int(t))\r\n"
    "            ts = t / 1000.0 if t > 10 ** 12 else float(t)   # 毫秒 vs 秒\r\n")

# ---------- 版本号两处 + 文件头记录 ----------
HEAD = (
    "# 版本号: " + NEW_VER + "             修改时间: " + _now + " ("
    + NEW_VER + ": 零预设重查后确认的 5 项缺陷全部修复, 交易参数一个未动, "
    "无新增模块级大写常量, 参数指纹必仍为 efb96534。三项会直接造成损失: "
    "① 每日启动自动排雷那一段, 装载清单的调用多写了一个函数并不接收的参数, 程序当场报错, "
    "而这一行恰好不在紧邻的异常保护范围内 —— 排雷清单没抓到的日子, 后面的加载日线、选股、"
    "初始化日期全被跳过, 一整天候选池为空、一笔不买, 日志只有一串报错没有一句说明是什么原因; "
    "现改为不带参数调用, 并单独包一层保护。 "
    "② 状态文件损坏时会挂起下单并要求人工核对, 但旧版任何一次写盘成功都会把这个挂起自动解除, "
    "告警亮三十秒就自己灭掉, 持仓全丢的情况下照样开新仓; 现改为这类原因单独打标记, "
    "写盘成功只清失败计数、不解冻, 只有人工核对后重启策略才解除。 "
    "③ 发单那一刻先按估算费率预填了一笔费用, 成交回报又把真实费用累加上去, 全文件没有任何一处"
    "把预填值清掉 —— 一笔 900 股、真实费用 5.25 元的委托账面记成 10.50 元, 成本虚高一倍; "
    "成本虚高会抬高\"扣完全部费用要真赚钱才卖\"这道门槛, 结果该卖不卖; "
    "现改为首笔成交回报到达时先把预填值清零再按真实费用重算, 费用只认成交回报。 "
    "另两项会让排雷与财务判断静默失效: "
    "④ 装排雷清单的函数走完真正的读盘分支后没有把内容交回调用方, 调用方一律当成没命中, "
    "每个装载周期里第一只被检查的候选必然漏检; 现补上返回值。 "
    "⑤ 把财务日期转成八位年月日的小函数, 遇到数据源直接给八位数字(如 20260930)会当成 1970 年"
    "起的秒数换算, 结果变成 1970 年 8 月 23 日, 报告期被判严重滞后, 财务数据被整批过滤掉; "
    "现先判是不是八位年月日形态, 是就直接用。 "
    "本次未处理(等用户拍板再动): 止盈三个条件同时成立才卖的口径、情绪两条取数通道的涨停口径"
    "不一致、委托号表按股票只存一条、若干处走不到的代码。)"
)

add('ver-const', "VERSION = '" + OLD_VER + "'", "VERSION = '" + NEW_VER + "'")

# ---------- 执行 ----------
out = src
for name, old, new in EDITS:
    o = _crlf(old)
    n = _crlf(new)
    c = out.count(o)
    if c != 1:
        print('[FAIL] %-16s 锚点命中 %d 次(应为1)' % (name, c))
        sys.exit(1)
    out = out.replace(o, n, 1)
    print('[OK] %-16s 锚点命中 1 次' % name)

# 文件头版本记录: 按定位插入(不依赖空格数)
_pos = out.index('# 版本号: ' + OLD_VER)
out = out[:_pos] + _crlf(HEAD) + '\r\n' + out[_pos:]
print('[OK] %-16s 已插入版本记录' % 'ver-head')

# 校验: 版本号等长
assert len(NEW_VER) == len(OLD_VER)
assert out.count("VERSION = '" + NEW_VER + "'") == 1
assert out.count('# 版本号: ' + NEW_VER) == 1
assert out.count('# 版本号: ' + OLD_VER) == 1

# 编码回 GBK
enc = out.encode('gbk')
assert enc.decode('gbk') == out, 'GBK 往返失败'

# 语法校验(用原始 \r\n 文本)
ast.parse(out)

# 换行校验
nseg = out.count('\r\n')
bare_lf = out.count('\n') - nseg
bare_cr = out.count('\r') - nseg
print('段数(含末空段) = %d, 裸LF = %d, 裸CR = %d' % (len(out.split('\r\n')), bare_lf, bare_cr))
if bare_lf or bare_cr:
    sys.exit('换行不干净, 已中止')

tmp = P + '.tmp'
with open(tmp, 'wb') as f:
    f.write(enc)
os.replace(tmp, P)

data = open(P, 'rb').read()
print('落盘 %d 字节  MD5=%s' % (len(data), hashlib.md5(data).hexdigest()[:8]))
