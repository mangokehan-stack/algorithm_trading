# -*- coding: utf-8 -*-
"""从磁盘日志抽取 13:38~13:56 之间与买入相关的行(逐行判编码, 防混编码截断)"""
import sys, os, re
sys.stdout.reconfigure(encoding="utf-8")

LOG = r"C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_run.log"
print("日志文件 =", LOG, "存在 =", os.path.exists(LOG))
if not os.path.exists(LOG):
    sys.exit(1)
raw = open(LOG, "rb").read()
lines = raw.split(b"\n")
print("总行数 =", len(lines), " 字节 =", len(raw))
print()

def dec(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("gbk", "replace")

KEYS = ("买", "成交", "分批", "手工", "委托", "passorder", "下单", "回报", "601595", "额度", "闸门", "拦截")
out = []
for b in lines:
    s = dec(b).rstrip("\r")
    if not s:
        continue
    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", s.strip())
    if not m:
        continue
    hm = m.group(1)[11:16]
    if not ("13:38" <= hm <= "13:56"):
        continue
    if any(k in s for k in KEYS):
        out.append(s)

print("命中 %d 行:" % len(out))
print("=" * 100)
for s in out:
    print(s[:300])
