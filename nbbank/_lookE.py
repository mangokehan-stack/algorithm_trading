t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i,l in enumerate(lines,1):
    if l.startswith("def _lock_and_write") or l.startswith("def account_diag"):
        print(">>>", i, l)
        for j in range(i, i+55):
            print(j, lines[j-1])
        print("======")
