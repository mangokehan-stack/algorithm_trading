t=open(r"zt_shrink_strategy_gbk.py","rb").read().decode("gb18030")
lines=t.split("\r\n")
for i,l in enumerate(lines,1):
    if "abs_cap_left(" in l or "used_capital()" in l:
        print(i, l.strip()[:150])
