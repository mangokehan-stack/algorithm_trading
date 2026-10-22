import re, sys, io
p = r"E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py"
txt = open(p, "rb").read().decode("gbk")
lines = txt.split("\n")
print("TOTAL_LINES", len(lines), "CHARS", len(txt))

out = []
i = 0
# 1) docstring / header block end
for i,l in enumerate(lines):
    if l.strip() == '"""' and i > 10:
        break
print("HEADER_BLOCK_ENDS", i+1)

# 2) top-level def / class with line numbers
pat_def = re.compile(r'^(def|class)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(')
pat_assign = re.compile(r'^([A-Z][A-Z0-9_]*)\s*=')
defs=[]; classes=[]; consts=[]
for n,l in enumerate(lines,1):
    m=pat_def.match(l)
    if m and m.group(1)=="def": defs.append((n,l.strip()))
    m2 = re.match(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)', l)
    if m2: classes.append((n, m2.group(1), l.strip()))
    m3 = pat_assign.match(l)
    if m3: consts.append((n, m3.group(1), l.strip()[:110]))

print("FUNCS", len(defs), "CLASSES", len(classes), "UPPER_CONSTS", len(consts))

with io.open(r"E:\桌面\666666\dxgp\.box-agent-scratch\skeleton.txt","w",encoding="utf-8") as f:
    f.write("=== HEADER END LINE ===\n%d\n" % (i+1))
    f.write("\n=== CLASSES ===\n")
    for n,c,l in classes: f.write("%6d  %s\n" % (n, l))
    f.write("\n=== FUNCTIONS (%d) ===\n" % len(defs))
    for n,l in defs: f.write("%6d  %s\n" % (n, l))
    f.write("\n=== UPPER_CONSTS (%d) ===\n" % len(consts))
    for n,c,l in consts: f.write("%6d  %s\n" % (n, l))
print("wrote skeleton.txt")
