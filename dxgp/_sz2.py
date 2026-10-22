t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for i in range(4043,4135):
    print(i, lines[i-1])
