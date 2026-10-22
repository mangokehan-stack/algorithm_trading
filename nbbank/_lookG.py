t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
import re
for i,l in enumerate(lines,1):
    if re.search(r'_PENDING_TTL_FORCE|_PENDING_TTL\s*=|_PENDING_TTL\b', l):
        print(i, l.strip()[:140])
