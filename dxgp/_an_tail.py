# -*- coding: utf-8 -*-
"""读磁盘日志末尾 —— 按行判编码(前段 GBK / 后段 UTF-8)
本轮 V2.6.134 首轮: 21:19:32 启动, 关注取数线程进度
"""
import time

P = r'C:\广发证券QMT量化交易系统 - 交易端\bin.x64\zt_shrink_run.log'


def dec(b):
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('gbk', 'replace')


raw = open(P, 'rb').read()
print('文件 %d 字节 / mtime=%s'
      % (len(raw), time.strftime('%H:%M:%S', time.localtime(int(__import__('os').path.getmtime(P))))))

lines = [dec(x) for x in raw.split(b'\n') if x.strip()]
print('总行数 %d' % len(lines))
print('\n=== 末尾 25 行 ===')
for l in lines[-25:]:
    print(l[:230])

print('\n=== 本轮(21:19:32 起)关键行 ===')
st = None
for i, l in enumerate(lines):
    if '21:19:32' in l and '启动' in l:
        st = i
        break
if st is not None:
    for l in lines[st:]:
        if any(k in l for k in ['情绪', '累积池', '耗时', '转dict', '解析', '落盘',
                                '批内', '覆盖', '探针', '对照', '截断']):
            print(l[:230])
else:
    print('未定位到本轮启动行')
