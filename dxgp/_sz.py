t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
import re
for i,l in enumerate(lines,1):
    if re.search(r'SINGLE_MAX|PER_STOCK|单票|CASH_CAP|PORTFOLIO_CAP|max_above|组合市值', l):
        print(i, l.strip()[:150])
