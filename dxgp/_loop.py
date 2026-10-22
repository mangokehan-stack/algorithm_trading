t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for i in range(11060,11145):
    print(i, lines[i-1])
