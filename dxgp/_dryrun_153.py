# -*- coding: utf-8 -*-
"""V2.6.153 干跑 v2：修掉两处测试自身错误
  ① '无残留占位符' 不能用 '%' not in out —— 字面 %% 会假失败（第 4 次踩）
     正确判据：正则搜未渲染的 %s/%d/%f
  ② 守卫窗口 L-6 框不到 if tide:  → 扩大到 if/else 整段
"""
import ast
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
src = open(P, "rb").read().decode("gbk")
tree = ast.parse(src)
lines = src.split("\r\n")

cand = [n for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and n.value.startswith("[退潮判断] 数据有效")]

ok = True
def ck(name, cond, detail=""):
    global ok
    print("{:<4} {:<40} {}".format("PASS" if cond else "FAIL", name, detail))
    if not cond:
        ok = False

ck("格式串唯一", len(cand) == 1, "count=%d" % len(cand))
tpl, ln = cand[0].value, cand[0].lineno
print("     L%d 模板: %r" % (ln, tpl))

spec = re.findall(r"%(?:\.\d+)?([sdf])", tpl)
ck("占位符 s,d,f,f", spec == ["s", "d", "f", "f"], str(spec))

out = tpl % ("000001.SH", 3, 0.75, 3.0)
print("\n     渲染: " + out + "\n")

# ① 正确的残留判定
left = re.findall(r"%(?:\.\d+)?[sdf]", out)
ck("无未渲染占位符(正则判定)", not left, "残留=%r" % left)
n_pct = out.count("%")
ck("字面百分号应为 2 个", n_pct == 2, "实际=%d" % n_pct)

# 内容
for frag in ["000001.SH", "近3日跌幅0.75%", "未达退潮阈值3%",
             ", 退潮层通过(仍须过情绪等其它闸门)"]:
    ck("含 " + frag, frag in out)
ck("旧尾句已无", "正常开仓" not in out)

# ② 守卫：整段 if tide:/else: 上下文
lo = max(0, ln - 12)
seg = "\r\n".join(lines[lo:ln + 4])
ck("在 if tide: ... else: 结构内", "if tide:" in seg and "else:" in seg)
ck("有 tide_ok_note_date 去重", "tide_ok_note_date" in seg)
ck("去重后置今日日期", "G.tide_ok_note_date = G.today" in seg)
ck("分支末端 return tide", "return tide" in "\r\n".join(lines[ln - 1:ln + 5]))
ck("是 log() 调用", lines[ln - 1].strip().startswith("log("), lines[ln - 1].strip()[:35])

# ③ 参数个数与格式串匹配（4 个）
ck("参数个数=4", len(re.findall(r"%[^%]", tpl.replace("%%", ""))) == 4,
   str(len(re.findall(r"%[^%]", tpl.replace("%%", "")))))

print("=" * 62)
print("结果: %s" % ("干跑全部通过" if ok else "仍有 FAIL"))
sys.exit(0 if ok else 1)
