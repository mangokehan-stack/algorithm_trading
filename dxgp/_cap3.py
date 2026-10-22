t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for a,b in ((9130,9200),(9280,9330),(9480,9520)):
    print("=== %d-%d ==="%(a,b))
    for i in range(a,b):
        print(i, lines[i-1])
