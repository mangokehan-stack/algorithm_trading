t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i in range(5545,5660):
    print(i, lines[i-1])
