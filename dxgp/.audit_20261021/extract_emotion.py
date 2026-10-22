# -*- coding: utf-8 -*-
"""按行号从 GBK 源码抽取片段为 UTF-8（带原行号），供细读审计。只读。"""
import os

BASE = r"E:\桌面\666666\dxgp"
SRC = os.path.join(BASE, "zt_shrink_strategy_gbk.py")
OUTDIR = os.path.join(BASE, ".audit_20261021", "segments")
os.makedirs(OUTDIR, exist_ok=True)

raw = open(SRC, "rb").read()
lines = raw.decode("gbk").splitlines()

SEGMENTS = [
    # (label, start, end)
    ("emotion_core_1", 12185, 12625),   # BEGIN/常量/累积池定义
    ("emotion_core_2", 12626, 12900),   # 缓存/指纹/取数主函数
    ("emotion_core_3", 12901, 13265),   # 覆写/缓存/最后一好/应用/降级/worker
    ("emotion_sync", 13266, 14210),     # _sent_fetch_sync 主线(942行)
    ("emotion_compute", 14211, 14514),  # 计算/新鲜/引导/日刷新/挂载
]

for label, s, e in SEGMENTS:
    out = os.path.join(OUTDIR, label + ".txt")
    with open(out, "w", encoding="utf-8") as f:
        for i in range(s, min(e, len(lines)) + 1):
            f.write("L%05d| %s\n" % (i, lines[i - 1]))
    print(label, os.path.getsize(out), "bytes")

print("done")