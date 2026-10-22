t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
def show(a,b):
    for i in range(a,b+1):
        print(i, lines[i-1])
for i,l in enumerate(lines,1):
    if "_read_order_direction" in l or "def has_live_buy_order" in l or "方向字段自检" in l:
        print("HIT",i,l.strip()[:120])
