# -*- coding: utf-8 -*-
"""V2.6.153 -> V2.6.154
只动「过户费口径」的 4 行注释/行尾注释，零逻辑、零参数、零 desc 改动
（FEE_PROFILE['stock']['desc'] 参与参数指纹，故意不动）。
V2.6.153 未单独上线，其退潮行文案改动已包含在本版内。
"""
import ast
import hashlib
import os
import re
import shutil
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

P = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
CRLF = "\r\n"

stamp = datetime.now().strftime("%Y%m%d-%H%M")
bak = P + ".bak-" + stamp
shutil.copy2(P, bak)
print("[备份] %s (%d 字节)" % (bak, os.path.getsize(bak)))

raw = open(P, "rb").read()
old_md5 = hashlib.md5(raw).hexdigest()
old_size = len(raw)
txt = raw.decode("gbk")
assert not raw.startswith(b"\xef\xbb\xbf")
assert txt.count("\n") == txt.count(CRLF)
print("[原态] MD5=%s 字节=%d 段数=%d" % (old_md5, old_size, len(txt.split(CRLF))))
assert len(txt.split(CRLF)) == 14628, len(txt.split(CRLF))

# ---- 4 处文本替换：每处必须唯一 ----
REPL = [
    # ① 注释块第 2 行：把「无从自证/保守口径」改成「用户已拍板按正常收」
    ("#   约万0.541)与过户费(万0.1)。V2.6.150 审计: 无从自证是否另收, 按【宁可多算费用】的保守口径把 FEE_TRANSFER_RATE 从 0 改为 0.00001(沪市双边各万0.1);",
     "#   约万0.541)与过户费(万0.1)。过户费口径已于 2026-10-21 由用户拍板【按正常标准收取】:"),
    # ② 注释块第 3 行：删掉「必须拿交割单验证」的待办口吻
    ("#   核对方法: 深市过户费并入佣金不单独显示, 必须用【沪市60/688】交割单验证 —— 栏内为0=券商全包,",
     "#   FEE_TRANSFER_RATE 长期保持 0.00001(沪市双边各万0.1, 买入收一次、卖出收一次), 不再回退为 0;"),
    # ③ 注释块第 4 行：删掉「则改回 0.0」这个危险指令
    ("#   则把 FEE_TRANSFER_RATE 改回 0.0; 栏内>0=确实另收, 保持现值 0.00001。影响量级: 1.2万仓位双边仅0.24元。",
     "#   深市(000/001/002/003/300/301)不收, 由 _transfer_rate_for 按代码分列。影响量级: 1.2万仓位双边仅0.24元。"),
    # ④ 常量行尾注释：去掉「若确认全包则改回0.0」，并补全 689 前缀
    ("FEE_TRANSFER_RATE = 0.00001      # 过户费(双边, 仅沪市600/601/603/605/688): V2.6.150 起保守计入万0.1; 交割单若确认全包则改回0.0",
     "FEE_TRANSFER_RATE = 0.00001      # 过户费(双边, 仅沪市600/601/603/605/688/689): 按正常标准收取万0.1, 买卖各一次; 长期保持不回退"),
]

for i, (o, n) in enumerate(REPL, 1):
    c = txt.count(o)
    assert c == 1, "第%d处锚点 count=%d" % (i, c)
    ln = txt[:txt.index(o)].count(CRLF) + 1
    txt = txt.replace(o, n)
    print("[替换%d] L%d 唯一命中" % (i, ln))

# ---- 升版 ----
assert txt.count("VERSION = 'V2.6.153'") == 1
txt = txt.replace("VERSION = 'V2.6.153'", "VERSION = 'V2.6.154'")

now = datetime.now().strftime("%Y-%m-%d %H:%M")
HEAD = (
    "# 版本号: V2.6.154             修改时间: " + now + " "
    "(V2.6.154: 只动过户费口径的 4 行说明, 零逻辑、零参数, 无新增模块级大写常量, 参数指纹必仍为 "
    "efb96534。★ 本版已包含 V2.6.153 的全部改动(V2.6.153 未单独上线, 以本版为准): "
    "① 退潮判断通过那一行原文写 \"正常开仓\", 属拿局部结论冒充全局结论 —— 退潮只是买入前置闸门的一层, "
    "其后还有情绪 L1 闸门、风险过滤、分批节奏; 2026-10-21 13:25:02 实盘日志里它与紧随其后的 "
    "\"暂不开新仓: 情绪数据未就绪\" 出现在同一秒, 自相矛盾; 现改为 \"退潮层通过(仍须过情绪等其它闸门)\"。 "
    "② 过户费口径定论: 用户 2026-10-21 拍板【按正常标准收取】, FEE_TRANSFER_RATE 长期保持 0.00001"
    "(沪市双边各万0.1, 买入收一次、卖出收一次), 不再回退为 0; 原注释里 \"拿沪市交割单验证, 若为 0 就改回 "
    "0.0\" 的待办指令已删除 —— 留着一个可能导致少算费用的后续指令比多算 0.24 元危险得多。 "
    "③ FEE_PROFILE 里 stock 档的 desc 字段【故意未动】: 它参与参数指纹, 改措辞会误报 \"参数变更\"。 "
    "本策略只交易沪深A股, 股票档以外品种的费率未触碰。)"
)

lines = txt.split(CRLF)
assert lines[4].startswith("# 版本号: V2.6.153"), repr(lines[4][:40])
lines.insert(4, HEAD)
txt = CRLF.join(lines)
print("[文件头] 已插入 V2.6.154 记录行, 段数 -> %d" % len(lines))

out = txt.encode("gbk")
open(P, "wb").write(out)

# ---- 复核 ----
raw2 = open(P, "rb").read()
txt2 = raw2.decode("gbk")
L2 = txt2.split(CRLF)
res = []
def ck(n, c, d=""):
    res.append((n, bool(c), d))

ck("GBK 往返一致", txt2.encode("gbk") == raw2)
ck("无 BOM", not raw2.startswith(b"\xef\xbb\xbf"))
ck("裸 LF == 0", txt2.count("\n") == txt2.count(CRLF), "%d/%d" % (txt2.count("\n"), txt2.count(CRLF)))
ck("段数 14629", len(L2) == 14629, str(len(L2)))
ck("危险指令已删", "改回 0.0" not in txt2 and "改回0.0" not in txt2)
ck("无残留「无从自证」", "无从自证" not in txt2)
ck("新口径在位", "按正常标准收取" in txt2)
ck("买卖各一次已写明", "买入收一次、卖出收一次" in txt2)
ck("V2.6.153 退潮文案仍在", txt2.count("退潮层通过(仍须过情绪等其它闸门)") >= 2)
ck("VERSION = V2.6.154", txt2.count("VERSION = 'V2.6.154'") == 1)
ck("文件头首行 = V2.6.154", re.search(r"# 版本号: (V[\d.]+)", txt2).group(1) == "V2.6.154")
ck("费率数值未变", txt2.count("FEE_TRANSFER_RATE = 0.00001") == 1 and txt2.count("FEE_COMMISSION_RATE = 0.0000841") == 1)
ck("desc 未动", txt2.count("过户费沪市双边万0.1(保守计入)") == 1)

try:
    compile(txt2, P, "exec")
    ck("compile", True)
except SyntaxError as e:
    ck("compile", False, str(e))

tree = ast.parse(txt2)
nm = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "stop_order"]
at = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "stop_order"]
ck("铁律: 硬止损 AST = 0", not nm and not at, "Name=%d Attr=%d" % (len(nm), len(at)))

print("\n" + "=" * 66)
bad = 0
for n, ok, d in res:
    print("%-4s %-26s %s" % ("PASS" if ok else "FAIL", n, d))
    bad += 0 if ok else 1
print("=" * 66)
print("MD5=%s 字节=%d (原 %s / %d, %+d)" % (
    hashlib.md5(raw2).hexdigest(), len(raw2), old_md5, old_size, len(raw2) - old_size))
print("结果: %d/%d PASS" % (len(res) - bad, len(res)))
sys.exit(1 if bad else 0)
