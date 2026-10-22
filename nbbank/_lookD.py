t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i in range(4637,4740):
    print(i, lines[i-1])
