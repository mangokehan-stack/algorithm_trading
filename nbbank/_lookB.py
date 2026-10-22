t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
import re
for i,l in enumerate(lines,1):
    if re.search(r'\b(48|49)\b', l) and ('买' in l or '卖' in l or 'Offset' in l or 'Direction' in l):
        print(i, l.strip()[:160])
