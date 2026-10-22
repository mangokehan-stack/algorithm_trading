t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i,l in enumerate(lines,1):
    if l.startswith("def save_state"):
        for j in range(i-30, i+80):
            print(j, lines[j-1])
        break
