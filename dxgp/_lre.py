t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for i,l in enumerate(lines,1):
    if l.startswith("def load_risk_exclude") or l.startswith("def risk_exclude_path"):
        print(">>>", i, l.strip())
        for j in range(i, i+55):
            print(j, lines[j-1])
        print("-----")
