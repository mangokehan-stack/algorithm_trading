t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i,l in enumerate(lines,1):
    if l.startswith("def load_state") or l.startswith("def save_m3") or l.startswith("def _notify_risk"):
        print(">>>", i, l)
