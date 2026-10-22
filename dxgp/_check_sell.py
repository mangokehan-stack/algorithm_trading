# -*- coding: utf-8 -*-
"""从磁盘实盘日志核实 002232 启明信息 的卖出全过程
   日志混编码: 按行判 utf-8 / gbk
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

LOG = r"C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_run.log"
print("日志: %s" % LOG)
print("存在: %s  大小: %s 字节" % (os.path.exists(LOG),
                                format(os.path.getsize(LOG), ",") if os.path.exists(LOG) else "-"))

raw = open(LOG, "rb").read()
lines = []
for b in raw.split(b"\n"):
    if b.endswith(b"\r"):
        b = b[:-1]
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        s = b.decode("gbk", "replace")
    lines.append(s)

print("总行数: %d\n" % len(lines))

# 只取今天 13:2x / 13:3x 这段
PAT_TIME = re.compile(r"^2026-10-21 13:(2\d|3\d):")
seg = [(i + 1, l) for i, l in enumerate(lines) if PAT_TIME.match(l)]
print("13:20~13:39 区间行数: %d" % len(seg))

KEYS = ["002232", "卖出", "成交", "解套", "净利", "放量", "止盈", "止盈卖出", "委托"]
hits = [(n, l) for n, l in seg if any(k in l for k in KEYS)]
print("其中含卖出/成交关键词: %d 行\n" % len(hits))

print("=" * 100)
for n, l in hits:
    print("L%-6d %s" % (n, l[:230]))
