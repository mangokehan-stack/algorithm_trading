import re
t=open(r"gf_qmt_native_multi_gbk.py","rb").read().decode("gb18030")
lines=t.split("\n")
for i,l in enumerate(lines,1):
    if "情绪模块自检" in l or "SENTIMENT_CFG = {" in l or "SENTIMENT_ENABLED" in l:
        print(i, l)
