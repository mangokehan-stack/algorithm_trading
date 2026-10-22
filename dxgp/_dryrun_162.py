# -*- coding: utf-8 -*-
"""V2.6.162 干跑: 心跳文件自动清理边界测试(真实 import + 临时目录重定向, 不注桩业务)。"""
import os, sys, json, time, types, tempfile

P = r'E:\桌面\666666\dxgp\zt_shrink_strategy_gbk.py'
SRC = open(P, 'rb').read().decode('gbk').replace('\r\n', '\n')
TMP = tempfile.mkdtemp(prefix='dry162_')
os.chdir(TMP)
M = types.ModuleType('strat')
exec(compile(SRC, '<strat>', 'exec'), M.__dict__)
LOGS = []
M.log = lambda *a, **k: LOGS.append(' '.join(str(x) for x in a))
# 文件基址重定向到临时目录(心跳写入/枚举/世代/状态全部走这里)
M.file_base_dir = lambda: TMP
M._join_base = lambda name: os.path.join(TMP, os.path.basename(name))
M.G.accid = '8973786'

suf = M._account_suffix()
stem, ext = M._split_name(M.HEARTBEAT_FILE)


def hb(pid, days_ago, ts_age_sec, valid=True):
    fn = '%s%s_%d%s' % (stem, suf, pid, ext)
    p = os.path.join(TMP, fn)
    if valid:
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump({'pid': pid, 'ts': time.time() - ts_age_sec,
                       'acc': '8973786', 'ver': 'V2.6.161', 'boot': 0.0}, fh)
    else:
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write('{corrupt')
    old = time.time() - days_ago * 86400.0
    os.utime(p, (old, old))
    return fn


# 场景: 旧有效(10天) / 旧损坏(8天) / 活跃同伴(14分钟) / 7天内陈旧(2天) / 世代文件(30天) / 状态文件(30天)
f_old_ok = hb(90001, 10, 3600)
f_old_bad = hb(90002, 8, 3600, valid=False)
f_peer = hb(90003, 0.01, 30)
f_recent_stale = hb(90004, 2, 7200)
gen = M.gen_path()
with open(gen, 'w', encoding='utf-8') as fh:
    json.dump({'gen': time.time(), 'pid': 1}, fh)
old = time.time() - 30 * 86400.0
os.utime(gen, (old, old))
st = M.state_path()
with open(st, 'w', encoding='utf-8') as fh:
    fh.write('{}')
os.utime(st, (old, old))

M.heartbeat_tick(force=True)
time.sleep(0.05)
M.heartbeat_tick(force=True)   # 幂等性: 二跑不炸不误删

res = []
def ck(name, cond, extra=''):
    res.append((name, bool(cond), extra))

ck('R1 旧的有效心跳(10天)已删', not os.path.exists(os.path.join(TMP, f_old_ok)))
ck('R2 旧的损坏心跳(8天)已删(按mtime, 不依赖JSON可读)',
   not os.path.exists(os.path.join(TMP, f_old_bad)))
ck('R3 活跃同伴心跳(14分钟)保留', os.path.exists(os.path.join(TMP, f_peer)))
ck('R4 7天内的陈旧心跳(2天)保留', os.path.exists(os.path.join(TMP, f_recent_stale)))
ck('R5 世代文件(30天)未删', os.path.exists(gen))
ck('R6 状态文件(30天)未删', os.path.exists(st))
ck('R7 自己的心跳文件已写且未删', os.path.exists(M.heartbeat_path()))
cl = [l for l in LOGS if '心跳文件自动清理' in l]
ck('R8 清理日志恰好1条且计数=2', len(cl) == 1 and '删除2个' in cl[0], cl[0][:110] if cl else '')
ck('R9 清理日志含口径(超过7天/120秒)', cl and '超过7天' in cl[0] and '120秒' in cl[0])
ck('R10 同伴检测仍生效(90003被判活跃同伴)',
   any('90003' in l for l in LOGS), [l[:80] for l in LOGS if '90003' in l][:1])
ck('R11 二跑无重复清理日志(幂等)', len([l for l in LOGS if '心跳文件自动清理' in l]) == 1)
ck('R12 二跑后活跃同伴仍在', os.path.exists(os.path.join(TMP, f_peer)))

bad = [r for r in res if not r[1]]
for name, ok, extra in res:
    print('%-42s %s %s' % (name, 'PASS' if ok else 'FAIL', extra))
print('---')
print('TOTAL: %d/%d PASS' % (len(res) - len(bad), len(res)))
sys.exit(1 if bad else 0)
