t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for key in ("def abs_cap_left","def used_capital"):
    for i,l in enumerate(lines,1):
        if l.startswith(key):
            print(">>>", i, l.strip())
            for j in range(i, i+40):
                print(j, lines[j-1])
            print("-----")
