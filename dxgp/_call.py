t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for i,l in enumerate(lines,1):
    if "_auto_risk_exclude" in l:
        print(i, l.strip()[:160])
