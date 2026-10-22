# -*- coding: utf-8 -*-
"""V2.6.162 补丁: 心跳文件自动清理(用户点修项1) + 升版两处 + 文件头记录行。
纪律: 二进制读写 / sub_once 唯一锚点 / 先内存后落盘 / 原子替换 / 时间戳现场取时并回验 mtime。
"""
import os, sys, time, hashlib, shutil, py_compile, ast

P = 'zt_shrink_strategy_gbk.py'


def die(msg):
    print('FATAL:', msg)
    sys.exit(1)


def sub_once(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        die('%s 锚点 count=%d (要求1)' % (tag, n))
    return text.replace(old, new, 1)


# ---------- 0. 前置门禁 ----------
raw = open(P, 'rb').read()
if raw[:3] == b'\xef\xbb\xbf':
    die('补丁前就有 BOM')
if raw.count(b'\n') - raw.count(b'\r\n') != 0:
    die('补丁前裸 LF 不为 0: %d' % (raw.count(b'\n') - raw.count(b'\r\n')))
t = raw.decode('gbk')
print('补丁前: %d 字节 / md5=%s' % (len(raw), hashlib.md5(raw).hexdigest()))

# ---------- R1: 同伴枚举里加超期残留心跳清理 ----------
OLD1 = (
    "        _peers = []\r\n"
    "        try:\r\n"
    "            for _fn in os.listdir(_base):\r\n"
    "                if not (_fn.startswith(_pre) and _fn.endswith(_ext)):\r\n"
    "                    continue\r\n"
    "                _p = os.path.join(_base, _fn)\r\n"
    "                if os.path.normpath(_p) == os.path.normpath(_me):\r\n"
    "                    continue\r\n"
    "                try:\r\n"
    "                    with open(_p, 'r', encoding='utf-8') as _fh:\r\n"
)
NEW1 = (
    "        _peers = []\r\n"
    "        _hb_rm = 0\r\n"
    "        _hb_keep_days = 7.0\r\n"
    "        try:\r\n"
    "            for _fn in os.listdir(_base):\r\n"
    "                if not (_fn.startswith(_pre) and _fn.endswith(_ext)):\r\n"
    "                    continue\r\n"
    "                _p = os.path.join(_base, _fn)\r\n"
    "                if os.path.normpath(_p) == os.path.normpath(_me):\r\n"
    "                    continue\r\n"
    "                # V2.6.162(用户点修-心跳文件堆积): 超期残留心跳自动清理。\r\n"
    "                #   实证(2026-10-22 07:08 启动复核): bin.x64 目录堆了18个历史实例心跳文件\r\n"
    "                #   (最早10-19), 每次重启留一个、从不清理。功能本无害(双实例检测只认\r\n"
    "                #   HEARTBEAT_STALE_SEC=120秒内活跃的同伴, 陈旧文件被静默跳过), 但目录\r\n"
    "                #   越积越乱, 人工翻查时分不清哪个是当代。\r\n"
    "                #   口径: ① 前缀 _pre 已含账号后缀, 只清本账号自己的历史实例; ② 自己的\r\n"
    "                #   文件在上面已 continue 跳过, 绝不会误删当代心跳; ③ 只删文件修改时间早于\r\n"
    "                #   7个自然日的 —— 一周内的证据(「疑似残留心跳」提示)全保留; ④ 删除失败\r\n"
    "                #   静默跳过, 下轮重试, 不因清理影响检测主业。\r\n"
    "                #   阈值用局部变量, 不新增大写常量, 参数指纹不受影响。\r\n"
    "                try:\r\n"
    "                    if (time.time() - os.path.getmtime(_p)) > _hb_keep_days * 86400.0:\r\n"
    "                        os.remove(_p)\r\n"
    "                        _hb_rm += 1\r\n"
    "                        continue\r\n"
    "                except Exception:\r\n"
    "                    pass\r\n"
    "                try:\r\n"
    "                    with open(_p, 'r', encoding='utf-8') as _fh:\r\n"
)
t = sub_once(t, OLD1, NEW1, 'R1')

# ---------- R2: 清理结果日志行 ----------
OLD2 = (
    "            log('[安全][提示] 双实例探测异常(本轮跳过, 下轮重试): %s' % _exc_text(_e))\r\n"
    "        if not _peers:\r\n"
)
NEW2 = (
    "            log('[安全][提示] 双实例探测异常(本轮跳过, 下轮重试): %s' % _exc_text(_e))\r\n"
    "        if _hb_rm > 0:\r\n"
    "            log('[安全] 心跳文件自动清理: 删除%d个修改时间超过%.0f天的残留心跳文件'\r\n"
    "                '(不影响双实例检测, 该检测只认%d秒内活跃的同伴)'\r\n"
    "                % (_hb_rm, _hb_keep_days, HEARTBEAT_STALE_SEC))\r\n"
    "        if not _peers:\r\n"
)
t = sub_once(t, OLD2, NEW2, 'R2')

# ---------- R3: VERSION 常量(等长替换) ----------
t = sub_once(t, "VERSION = 'V2.6.161'", "VERSION = 'V2.6.162'", 'R3')

# ---------- R4: 文件头记录行(现场取时, 与备份名同一时钟读数) ----------
now_ep = time.time()
ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(now_ep))
body = (
    "V2.6.162: 用户点修两项。"
    "① 心跳文件自动清理(唯一代码改动): 双实例检测的同伴枚举里顺带删除文件修改时间早于7个自然日的残留心跳 —— "
    "实证2026-10-22 07:08 启动复核, bin.x64 目录堆了18个历史实例心跳文件(最早10-19), 每次重启留一个、从不清理; "
    "功能本无害(检测只认120秒内活跃同伴, 陈旧文件被静默跳过), 但目录越积越乱、人工翻查时分不清当代。"
    "口径: 前缀已含账号后缀只清本账号; 自己的文件在枚举开头即continue跳过, 绝不会误删当代心跳; "
    "只删超7天的, 一周内证据(疑似残留心跳提示)全保留; 删除失败静默跳过下轮重试。"
    "阈值用局部变量, 无新增模块级大写常量, 参数指纹仍为efb96534。"
    "② 无代码改动: 随附部署操作单_V26162 要求整篇重贴终版母版, 同时了结\"编辑器文本可能是01:09中间态\"的字节级疑问 —— "
    "已探明QMT侧pyc是10-16陈旧缓存(源大小526307, 不含任何V2.6.16x字串), XtPersistData的.ldb只存引用不存源码, "
    "磁盘artifacts证明不了当代部署文本, 整篇重贴是唯一可靠路径; 重贴后版本指纹换新值, 与2762ac8f明确区分。"
    "交易参数一行未改, 铁律口径不变。"
)
lines = t.split('\r\n')
idx = next((i for i, l in enumerate(lines) if l.startswith('# 版本号: V2.6.161')), -1)
if idx < 0:
    die('找不到 V2.6.161 记录行')
anchor = lines[idx]
head = anchor.split('修改时间:')[0]
if not head.endswith(' ') or 'V2.6.161' not in head:
    die('记录行前缀形态异常: %r' % head[-40:])
head_new = head.replace('V2.6.161', 'V2.6.162')
rec_line = head_new + '修改时间: ' + ts + ' (' + body + ')'
t = sub_once(t, anchor, rec_line + '\r\n' + anchor, 'R4')

# ---------- 1. 落盘前门禁 ----------
new_raw = t.encode('gbk')
if new_raw[:3] == b'\xef\xbb\xbf':
    die('编码后出现 BOM')
if new_raw.count(b'\n') - new_raw.count(b'\r\n') != 0:
    die('补丁后裸 LF 不为 0: %d' % (new_raw.count(b'\n') - new_raw.count(b'\r\n')))
if new_raw.decode('gbk').encode('gbk') != new_raw:
    die('GBK 往返失败')
try:
    compile(t, P, 'exec')
    ast.parse(t)
    print('compile/AST = OK')
except SyntaxError as e:
    die('语法错误: %s' % e)

# 参数指纹预检: 写临时文件调 _fp_calc_150.py 本体(官方口径含 TYPES 标量过滤,
# 内联复刻会漏容器常量 -- 实测内联283 vs 官方261, 禁止复刻)
import subprocess
pre = P + '.pre162'
with open(pre, 'wb') as fh:
    fh.write(new_raw)
r = subprocess.run([sys.executable, '_fp_calc_150.py', pre],
                   capture_output=True, text=True, errors='replace')
out = (r.stdout or '') + (r.stderr or '')
print(out.strip()[-500:])
os.remove(pre)
if '参与指纹的常量 261 个' not in out:
    die('预检失败: 指纹口径常量数不是261(官方口径)')
if '参数指纹 = efb96534' not in out:
    die('预检失败: 参数指纹漂移(官方口径)')
print('落盘前官方口径预检: 261个常量 / 参数指纹 efb96534 = OK')

# ---------- 2. 备份(与记录行同一时钟读数) ----------
bak = P + '.bak-' + time.strftime('%Y%m%d-%H%M', time.localtime(now_ep))
shutil.copy2(P, bak)
print('备份 ->', bak)

# ---------- 3. 原子落盘 ----------
tmp = P + '.tmp162'
with open(tmp, 'wb') as fh:
    fh.write(new_raw)
os.replace(tmp, P)

# ---------- 4. 落盘后回验 ----------
raw2 = open(P, 'rb').read()
mt = os.path.getmtime(P)
drift = mt - now_ep
print('落盘后: %d 字节 / md5=%s' % (len(raw2), hashlib.md5(raw2).hexdigest()))
print('记录行时间=%s | 文件mtime=%s | 偏差=%.1f秒' % (
    ts, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mt)), drift))
if len(raw2) != len(new_raw) or hashlib.md5(raw2).hexdigest() != hashlib.md5(new_raw).hexdigest():
    die('落盘内容与内存不一致')
if not (-5 <= drift <= 180):
    die('记录行时间与落盘时间偏差超窗: %.1f 秒(记录行必须贴近真实落盘时间)' % drift)
if raw2.count(b'\n') - raw2.count(b'\r\n') != 0 or raw2[:3] == b'\xef\xbb\xbf':
    die('落盘后门禁失败')
print('ALL IN-SCRIPT CHECKS PASS')
