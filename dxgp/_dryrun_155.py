# -*- coding: utf-8 -*-
"""V2.6.155 干跑: 从母版 AST 取状态行格式串, 按真实参数类型渲染, 验证输出可读。
不使用模块桩, 只取出该字符串常量做 % 渲染。"""
import sys, ast, re
sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
t = open(P, "rb").read().decode("gbk")
tree = ast.parse(t)

ok = fail = 0
def chk(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print("  [PASS] %s" % name)
    else:
        fail += 1
        print("  [FAIL] %s %s" % (name, extra))

# 找到状态行格式串
fmt = None
for n in ast.walk(tree):
    if isinstance(n, ast.Constant) and isinstance(n.value, str) \
            and n.value.startswith("策略状态更新 | 时段="):
        fmt = n.value
        break
chk("取到状态行格式串", fmt is not None)
if fmt is None:
    sys.exit(2)
print("\n格式串 =\n%s\n" % fmt)

# 占位符与真实参数(按类型喂)
ph = re.findall(r"%(?:\.\d+)?([sdf])", fmt)
print("占位符顺序 =", ph, "共", len(ph))
args = {
    "s": ["交易时段", "已完成", "就绪", "正常", "+81.00元 已实现+328.26元", ""],
    "d": [0, 2, 2, 0, 1],
    "f": [0.75],
}
si = di = fi = 0
vals = []
for p in ph:
    if p == "s":
        vals.append(args["s"][min(si, len(args["s"]) - 1)]); si += 1
    elif p == "d":
        vals.append(args["d"][min(di, len(args["d"]) - 1)]); di += 1
    else:
        vals.append(args["f"][min(fi, len(args["f"]) - 1)]); fi += 1

out = fmt % tuple(vals)
print("渲染结果 =\n%s\n" % out)

# 未渲染占位符必须为空(不能用 '%' not in out, 会因 %% 假失败)
chk("无未渲染占位符", re.findall(r"%(?:\.\d+)?[sdf]", out) == [],
    str(re.findall(r"%(?:\.\d+)?[sdf]", out)))
chk("含新标签 账本成交", "账本成交" in out)
chk("含 成交入账口径", "成交入账口径" in out)
chk("含 含手工卖出", "含手工卖出" in out)
chk("含 策略实发单另见[汇总]行", "策略实发单另见[汇总]行" in out)
chk("旧裸标签已消失", "| 买入0笔 卖出1笔" not in out, out[-60:])
chk("笔数数值正确", "买入0笔/卖出1笔" in out)
chk("无 _ds 时以口径括注收尾", out.endswith("策略实发单另见[汇总]行)"), out[-20:])
# 排除控制台长行折行导致的"插入空格"假象: 直接对字符串做精确子串断言
chk("账号与状态文件之间无异常空格", "状态文件=正常" in out and "状态文 件" not in out)
chk("口径括注内只有一个空格", "口径, 含手工" in out and "口径,  含手工" not in out)

# 另一场景: 有财务数据缺失提示 + 有成交
out2 = fmt % ("交易时段", "已完成", 0, "就绪", "正常", 1, 2,
              "+100.00元", 1, 2, " | 财务数据=【不可用】")
print("带 _ds 渲染 =\n%s\n" % out2)
chk("_ds 拼接位置在笔数之后", "行) | 财务数据=【不可用】" in out2, out2[-40:])

# 反向: 源文件里旧标签不应再出现于状态行
chk("源文件不含旧状态行标签", "| 买入%d笔 卖出%d笔%s" not in t)
# [汇总] 行必须保留(校验脚本 L218 依赖)
chk("[汇总] 行保留", "'[汇总] 本次运行买入%d笔 卖出%d笔" in t)

print("\n结果: %d PASS / %d FAIL" % (ok, fail))
with open(r"E:\桌面\666666\dxgp\_dryrun_155_out.txt", "w", encoding="utf-8") as f:
    f.write(u"len(out)=%d\nOUT1=%r\n\nlen(out2)=%d\nOUT2=%r\n" % (len(out), out, len(out2), out2))
sys.exit(0 if fail == 0 else 2)
