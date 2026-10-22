# -*- coding: utf-8 -*-
"""V2.6.147: 换行符归一 (83 处裸 LF -> CRLF), 内容零变化; 同步版本号

只在内存完成全部校验才写盘。
"""
import ast
import hashlib
import re

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
t = raw.decode('gbk')

# ---------- 前置断言 ----------
assert raw[:3] != b'\xef\xbb\xbf', '存在 BOM'
n_crlf0 = t.count('\r\n')
n_lf0 = len(re.findall(r'(?<!\r)\n', t))
print('改前: CRLF=%d 裸LF=%d bytes=%d' % (n_crlf0, n_lf0, len(raw)))
assert n_crlf0 == 14431 and n_lf0 == 83, '改前行尾统计与预期不符'
assert t.count('# 版本号: V2.6.146') == 1
assert t.count("VERSION = 'V2.6.146'") == 1

# ---------- 1. 换行归一 ----------
t1 = re.sub(r'(?<!\r)\n', '\r\n', t)
assert len(re.findall(r'(?<!\r)\n', t1)) == 0, '仍有裸 LF'
assert t1.count('\r\n') == n_crlf0 + n_lf0, 'CRLF 数不等于两者之和'
# 内容等价: 统一成 \n 后逐字节相同
assert t1.replace('\r\n', '\n') == t.replace('\r\n', '\n'), '归一化改变了内容'
print('归一后: CRLF=%d 裸LF=0' % t1.count('\r\n'))

# ---------- 2. 版本号 ----------
t2 = t1.replace('# 版本号: V2.6.146', '# 版本号: V2.6.147', 1)
t2 = t2.replace("VERSION = 'V2.6.147'", "VERSION = 'V2.6.147'", 1)
t2 = t2.replace("VERSION = 'V2.6.146'", "VERSION = 'V2.6.147'", 1)
assert t2.count('# 版本号: V2.6.147') == 1
assert t2.count("VERSION = 'V2.6.147'") == 1
assert "VERSION = 'V2.6.146'" not in t2

# 修改时间注释
old_ts = '修改时间: 2026-10-21 11:11 (V2.6.145:'
new_ts = '修改时间: 2026-10-21 11:50 (V2.6.147: 换行符归一, 83处裸LF->CRLF, 内容零变化; V2.6.145:'
assert t2.count(old_ts) == 1, '修改时间锚点未命中: %d' % t2.count(old_ts)
t2 = t2.replace(old_ts, new_ts, 1)

# ---------- 3. 写盘前校验 ----------
out = t2.encode('gbk')
assert out[:3] != b'\xef\xbb\xbf'
assert out.decode('gbk').encode('gbk') == out, 'GBK 往返失败'
compile(t2, P, 'exec')
tree = ast.parse(t2.replace('\r\n', '\n'))
n_stop = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == 'stop_order')
assert n_stop == 0, '铁律: stop_order 引用 %d' % n_stop
consts = {tg.id for n in tree.body if isinstance(n, ast.Assign)
          for tg in n.targets if isinstance(tg, ast.Name)
          and re.match(r'^[A-Z][A-Z0-9_]*$', tg.id)}
assert len(consts) == 284, '模块级大写常量 %d (应 284)' % len(consts)
assert len(re.findall(r'(?<!\r)\n', t2)) == 0

open(P, 'wb').write(out)
print('已写盘: bytes=%d md5=%s' % (len(out), hashlib.md5(out).hexdigest()[:8]))
print('段数(split CRLF)=%d 真实行数=%d' % (len(t2.split('\r\n')), t2.count('\r\n')))
print('常量=%d stop_order=%d 版本=%s' % (len(consts), n_stop, 'V2.6.147'))
