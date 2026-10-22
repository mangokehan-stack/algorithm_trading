t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for key in ("def _win32_read_bytes","def _subproc_read_bytes"):
    for i,l in enumerate(lines,1):
        if key in l:
            for j in range(i, i+35):
                print(j, lines[j-1])
            print("-----")
            break
