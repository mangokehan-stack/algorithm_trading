# -*- coding: utf-8 -*-
"""V2.6.161 实盘启动日志复核探针(只读, 不写任何文件)。"""
import os, json, subprocess, time, hashlib

QMT = r'C:\广发证券QMT量化交易系统 - 交易端\bin.x64'
ACC = '8973786'
NOW = time.strftime('%Y-%m-%d %H:%M:%S')

print('=== 1. 进程检查(21884=旧实例, 7796=当前实例) ===')
cmd = ('Get-Process -Id 21884,7796 -ErrorAction SilentlyContinue | '
       'Select-Object Id,ProcessName | ConvertTo-Csv -NoTypeInformation')
r = subprocess.run(['powershell', '-NoProfile', '-Command', cmd],
                   capture_output=True, text=True, errors='replace')
print(r.stdout.strip() or '(两个 PID 都不在运行)')
print('now =', NOW)

print()
print('=== 2. 心跳文件(含大小与修改时间) ===')
for f in sorted(os.listdir(QMT)):
    if 'heartbeat' in f.lower():
        p = os.path.join(QMT, f)
        print('%-56s %8d  %s' % (f, os.path.getsize(p),
              time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p)))))

print()
print('=== 3. 状态文件 ===')
sp = os.path.join(QMT, 'zt_shrink_state_%s.json' % ACC)
print('mtime =', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(sp))),
      '| size =', os.path.getsize(sp))
raw = open(sp, 'rb').read()
try:
    st = json.loads(raw.decode('utf-8'))
except Exception:
    st = json.loads(raw.decode('gbk'))
print('keys =', sorted(st.keys()))
print('orphans =', json.dumps(st.get('orphans'), ensure_ascii=False))
print('verified_fp =', json.dumps(st.get('verified_fp'), ensure_ascii=False))
for k, v in (st.get('hold') or {}).items():
    print('hold %s %s vol=%s px=%s fee=%s date=%s' % (
        k, v.get('name'), v.get('buy_vol'), v.get('buy_price'),
        v.get('fee'), v.get('buy_date')))

print()
print('=== 4. 运行日志尾部(按行混合解码, 最后40行) ===')
lp = os.path.join(QMT, 'zt_shrink_run.log')
with open(lp, 'rb') as fh:
    fh.seek(0, os.SEEK_END)
    sz = fh.tell()
    fh.seek(max(0, sz - 90000))
    buf = fh.read()
lines = [b for b in buf.split(b'\n') if b.strip()]
n = 0
for b in reversed(lines):
    try:
        s = b.decode('utf-8')
    except UnicodeDecodeError:
        s = b.decode('gbk', 'replace')
    print(s.rstrip('\r')[:230])
    n += 1
    if n >= 40:
        break

print()
print('=== 5. QMT 侧策略文档搜寻(含 V2.6.161 字样的可执行文本) ===')
t0 = time.time()
hits = []
skip_dirs = ('\\log', '\\data', '\\cache', '\\temp', '__pycache__', '\\drivers',
             '\\hicom', '\\download', '\\update', '\\backup')
for root in (QMT, os.path.dirname(QMT)):
    for dirpath, dirnames, filenames in os.walk(root):
        if time.time() - t0 > 25:
            print('(超时停止遍历)')
            dirnames[:] = []
            break
        rel = dirpath[len(root):].lower()
        if rel.count(os.sep) > 3:
            dirnames[:] = []
            continue
        if any(x in rel for x in skip_dirs):
            dirnames[:] = []
            continue
        for fn in filenames:
            if not fn.lower().endswith(('.py', '.rzrk', '.json', '.txt', '.sqlite', '.db')):
                continue
            p = os.path.join(dirpath, fn)
            try:
                szf = os.path.getsize(p)
                if szf < 5000 or szf > 3000000:
                    continue
                with open(p, 'rb') as fh:
                    head = fh.read(300000)
                if b'V2.6.161' in head and (b'zt_shrink' in head or b'passorder' in head):
                    hits.append((p, szf, os.path.getmtime(p)))
            except Exception:
                pass
for p, szf, mt in hits[:20]:
    try:
        md5 = hashlib.md5(open(p, 'rb').read()).hexdigest()
    except Exception:
        md5 = '?'
    print('%s | %d bytes | %s | md5=%s' % (p, szf,
          time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mt)), md5))
print('hits =', len(hits))
