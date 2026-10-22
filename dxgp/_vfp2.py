t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for i in range(3030,3080):
    print(i+1, lines[i])
