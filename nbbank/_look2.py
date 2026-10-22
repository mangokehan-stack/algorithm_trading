t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i,l in enumerate(lines,1):
    if "账号快照" in l or "manual_shares" in l:
        print(i, l.strip()[:150])
