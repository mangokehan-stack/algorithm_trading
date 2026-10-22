t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for i,l in enumerate(lines,1):
    if "_auto_risk_exclude" in l and "def " in l:
        print(">>>", i, l.strip())
        for j in range(i, i+45):
            print(j, lines[j-1])
        print("-----")
