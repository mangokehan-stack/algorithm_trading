# -*- coding: utf-8 -*-
"""V2.6.155 补丁: 状态行买卖笔数改标为「账本成交」并注明含手工卖出。
纯文案, 零逻辑, 零参数。二进制读写, 全程 GBK + CRLF。
"""
import sys, ast, datetime, hashlib
sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
raw = open(P, "rb").read()
t = raw.decode("gbk")
CRLF = "\r\n"
orig_len = len(t)

ok = fail = 0
def chk(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print("  [PASS] %s" % name)
    else:
        fail += 1
        print("  [FAIL] %s %s" % (name, extra))

now = datetime.datetime.now()
print("执行时间 =", now.strftime("%Y-%m-%d %H:%M:%S"))

# ---------- 1. 状态行文案 ----------
OLD = ("    log('策略状态更新 | 时段=%s | 数据阶段=%s(dl_phase=%d) | 账号=%s | 状态文件=%s"
       " | 持仓%d只 候选%d只 | %s | 买入%d笔 卖出%d笔%s'" + CRLF)
NEW = ("    log('策略状态更新 | 时段=%s | 数据阶段=%s(dl_phase=%d) | 账号=%s | 状态文件=%s"
       " | 持仓%d只 候选%d只 | %s | 账本成交 买入%d笔/卖出%d笔"
       "(成交入账口径, 含手工卖出; 策略实发单另见[汇总]行)%s'" + CRLF)
chk("状态行锚点唯一", t.count(OLD) == 1, "count=%d" % t.count(OLD))
t = t.replace(OLD, NEW, 1)
chk("状态行已替换", t.count(NEW) == 1 and t.count(OLD) == 0)

# ---------- 2. VERSION 常量 ----------
OV = "VERSION = 'V2.6.154'"
NV = "VERSION = 'V2.6.155'"
chk("VERSION 锚点唯一", t.count(OV) == 1, "count=%d" % t.count(OV))
chk("VERSION 等长", len(OV) == len(NV))
t = t.replace(OV, NV, 1)
chk("VERSION 已换", t.count(NV) == 1 and t.count(OV) == 0)

# ---------- 3. 文件头新记录行 ----------
HDR = (u"# 版本号: V2.6.155             修改时间: " + now.strftime("%Y-%m-%d %H:%M")
       + u" (V2.6.155: 纯文案一处, 零逻辑、零参数、零新增模块级大写常量, 参数指纹必仍为 efb96534。"
       u"改的是「策略状态更新」那一行里的买卖笔数标签: 该数字取自盈亏账本的成交入账记录, "
       u"其中包含在券商端或手机上手工卖出形成的条目, 而原标签只写买几笔卖几笔, "
       u"容易被读成策略自己发过这几笔单 —— 2026-10-21 13:28:40 那笔 002232 启明信息 600股@15.93 "
       u"经用户确认是手机手工卖出, 状态行却显示卖出1笔, 而策略当日实发卖单实为零笔。"
       u"现改为账本成交买几笔卖几笔, 并注明成交入账口径、含手工卖出, 同时指向启动收尾那行"
       u"进程内实发单计数, 便于两套口径互相对照。该行只打印, 不参与任何判定, 不改变任何买卖行为。)")
chk("文件头新行无裸换行", "\n" not in HDR and "\r" not in HDR)
chk("文件头新行不含禁用词", ("stop_order" not in HDR) and ("正常开仓" not in HDR)
    and ("跳开" not in HDR) and ("改回 0.0" not in HDR))
lines = t.split(CRLF)
chk("文件头首行结构", lines[0] == "#coding:gbk", lines[0])
chk("第5行是上一版记录", lines[4].startswith("# 版本号: V2.6.154"), lines[4][:40])
lines.insert(4, HDR)
t = CRLF.join(lines)
chk("插入后新行就位", t.split(CRLF)[4].startswith("# 版本号: V2.6.155"))

# ---------- 4. 落盘前校验 ----------
chk("GBK 可编码", True)
try:
    out = t.encode("gbk")
    chk("GBK 编码成功", True)
except Exception as e:
    chk("GBK 编码成功", False, str(e))
    raise SystemExit(1)
chk("无裸 LF", t.replace(CRLF, "").count("\n") == 0,
    "bare=%d" % t.replace(CRLF, "").count("\n"))
chk("无裸 CR", t.replace(CRLF, "").count("\r") == 0)
chk("无 BOM", not out.startswith(b"\xef\xbb\xbf"))
chk("GBK 往返一致", out.decode("gbk") == t)
chk("增量合理", 0 < len(t) - orig_len < 3000, "delta=%d" % (len(t) - orig_len))

tree = ast.parse(t)
chk("AST 可解析", True)
n_stop = sum(1 for n in ast.walk(tree)
             if isinstance(n, ast.Name) and getattr(n, "id", "") == "stop" + "_order")
chk("禁词 AST 节点为 0", n_stop == 0, "n=%d" % n_stop)

hv = [l for l in t.split(CRLF) if l.startswith("# 版本号:")]
chk("文件头首版号 = V2.6.155", hv[0].startswith("# 版本号: V2.6.155"), hv[0][:22])
chk("版本记录条数 +1", len(hv) >= 2)

open(P, "wb").write(out)
print()
print("已写盘: %d 字节  MD5=%s" % (len(out), hashlib.md5(out).hexdigest()))
print("结果: %d PASS / %d FAIL" % (ok, fail))
sys.exit(0 if fail == 0 else 2)
