t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i,l in enumerate(lines,1):
    if "def _read_file_bytes" in l:
        for j in range(i, i+40):
            print(j, lines[j-1])
        break
