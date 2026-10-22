t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
import re
for i,l in enumerate(lines,1):
    if re.search(r'def .*version_fp|VERSION_FP|版本指纹', l):
        print(i, l.strip()[:150])
