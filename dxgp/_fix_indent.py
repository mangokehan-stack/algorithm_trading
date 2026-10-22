"""修复 _patch_p1.py E7 缩进丢失 + E9 续行对齐"""
import io

PATH = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
with io.open(PATH, "r", encoding="gbk", newline="") as f:
    text = f.read()
lines = text.split("\r\n")

fixes = []

# 1) 漏斗第二行 log( 丢 4 空格缩进
for i, l in enumerate(lines):
    if l.startswith("log('           -> 换手率不符%d(字段缺失%d)"):
        lines[i] = "    " + l
        fixes.append("L%d log indent" % (i + 1))
        break
else:
    raise SystemExit("funnel log line not found")

# 2) 参数行 % ( 丢 8 空格缩进
for i, l in enumerate(lines):
    if l.startswith("% (st_turnover, st_turnover_missing,"):
        lines[i] = "        " + l
        fixes.append("L%d args indent" % (i + 1))
        break
else:
    raise SystemExit("funnel args line not found")

# 3) E9 续行 16->15 空格(与 log( 对齐, 纯美观)
for i, l in enumerate(lines):
    if l == "                st_mcap_miss, st_mcap_degrade))":
        lines[i] = "               st_mcap_miss, st_mcap_degrade))"
        fixes.append("L%d cont indent" % (i + 1))
        break

out = "\r\n".join(lines)
with io.open(PATH, "w", encoding="gbk", newline="") as f:
    f.write(out)

with io.open(PATH, "r", encoding="gbk", newline="") as f:
    chk = f.read()
compile(chk, PATH, "exec")
print("FIXED: %s" % ", ".join(fixes))
print("compile OK, lines=%d" % len(chk.split("\r\n")))
