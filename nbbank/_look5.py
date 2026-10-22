t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i in range(5735,5790):
    print(i, lines[i-1])
print("=== 变更记录块 ===")
for i,l in enumerate(lines,1):
    if l.startswith("── v1.2.") or "── v1.2." in l[:20]:
        print(i, l[:100])
