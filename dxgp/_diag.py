import hashlib, os, re

src = r'e:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
qmt = r'C:\广发证券QMT量化交易系统 - 交易端\python\1缩量买放量卖.py'

with open(src, 'rb') as f:
    sd = f.read()
with open(qmt, 'rb') as f:
    qd = f.read()

print(f'源码: {len(sd)} bytes, MD5={hashlib.md5(sd).hexdigest()}')
print(f'QMT:  {len(qd)} bytes, MD5={hashlib.md5(qd).hexdigest()}')
print(f'QMT 文件头: {qd[:16]}')

def check(name, needle, in_s, in_q):
    print(f'  [{name}] src={in_s}  qmt={in_q}  {"BOTH OK" if in_s and in_q else "MISSING!"}')

m = re.search(rb"VERSION = 'V([\d\.]+)'", sd)
print(f'\n源码 VERSION: V{m.group(1).decode() if m else "NF"}')
m2 = re.search(rb"VERSION = 'V([\d\.]+)'", qd)
print(f'QMT VERSION: V{m2.group(1).decode() if m2 else "NF"}')

print('\n--- 内嵌代码检查 ---')
check('_auto_risk_exclude def', b'def _auto_risk_exclude()', b'def _auto_risk_exclude()' in sd, b'def _auto_risk_exclude()' in qd)
check('_fetch_st_risk', b'def _fetch_st_risk', b'def _fetch_st_risk' in sd, b'def _fetch_st_risk' in qd)
check('_fetch_ann_risk', b'def _fetch_ann_risk', b'def _fetch_ann_risk' in sd, b'def _fetch_ann_risk' in qd)
check('_BagExcl class', b'class _BagExcl', b'class _BagExcl' in sd, b'class _BagExcl' in qd)
check('_http_risk', b'def _http_risk', b'def _http_risk' in sd, b'def _http_risk' in qd)
check('Phase2 gate', b'risk_ex_date != G.today', b'risk_ex_date != G.today' in sd, b'risk_ex_date != G.today' in qd)
gbk_prefix = '[排雷]'.encode('gbk')
check('[排雷] 日志', gbk_prefix, gbk_prefix in sd, gbk_prefix in qd)

print('\n--- QMT 文件格式 ---')
print('明文?', qd[:4] != b'D7hL')
print('加密壳?', qd[:4] == b'D7hL')

# 看源码里 Phase2 闸门周围
idx = sd.find(b'risk_ex_date != G.today')
if idx >= 0:
    ctx = sd[idx-100:idx+200].decode('gbk', errors='replace')
    print(f'\n--- Phase2 闸门上下文 (offset {idx}) ---')
    print(ctx)
else:
    print('\nPhase2 闸门 NOT FOUND in 源码!')
