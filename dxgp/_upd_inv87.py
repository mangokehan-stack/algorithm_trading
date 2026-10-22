# -*- coding: utf-8 -*-
"""更新 _check_inv.py 到 V2.6.87"""
P = '_check_inv.py'
lines = open(P, 'rb').read().decode('utf-8').split('\n')

assert lines[17].startswith('chk("行数=11648"'), lines[17]
lines[17] = 'chk("行数=11988", len(lines) == 11988, "actual=%d" % len(lines))'

assert lines[71].startswith('# 6 版本头(V2.6.86'), lines[71]
assert lines[78].startswith('chk("文件头V2.6.85历史行保留"'), lines[78]
lines[71:79] = [
    '# 6 版本头(V2.6.87 已升版: 取数层覆盖率/沿用信号/心跳/入参保护)',
    'm = re.search(r"VERSION\\s*=\\s*\'([^\']+)\'", text)',
    'chk("VERSION=V2.6.87", m and m.group(1) == "V2.6.87", m.group(1) if m else "?")',
    'chk("文件头V2.6.87记录", "版本号: V2.6.87" in text)',
    'chk("文件头V2.6.86历史行保留", "版本号: V2.6.86" in text)',
    'chk("文件头V2.6.85历史行保留", "版本号: V2.6.85" in text)',
]

NEW = r'''# 6g V2.6.87 六项(取数覆盖率/沿用信号/分量标注/ready三态/双实例心跳/入参保护)
chk("V2.6.87 覆盖率常量", "SENT_COVERAGE_MIN = 0.90" in text)
chk("V2.6.87 缓存文件常量", "SENT_CACHE_FILE = 'zt_shrink_sent_cache.json'" in text)
chk("V2.6.87 心跳常量齐备",
    "HEARTBEAT_FILE = 'zt_shrink_heartbeat.json'" in text
    and "HEARTBEAT_STALE_SEC = 120" in text
    and "HEARTBEAT_ALERT_SEC = 300" in text)
chk("V2.6.87 批量拆分函数", "def _sent_fetch_md_batch(" in text)
chk("V2.6.87 拆分档位 300->100->30",
    "_sz = 100 if depth <= 0 else 30" in text and "depth >= 2" in text)
chk("V2.6.87 异常文本带类型与repr兜底",
    "def _exc_text(e):" in text and "无异常消息" in text)
chk("V2.6.87 失败样本入日志", "取数失败样本(最多3条)" in text)
chk("V2.6.87 完成日志如实写覆盖率",
    "请求%d只 成功%d只(覆盖率%.1f%%)" in text and "失败%d只 拆分重试%d次" in text)
chk("V2.6.87 完成日志不再用股票池长度冒充取到数",
    "内置通道取数完成: 标的%d只(预下载%d只)" not in text)
chk("V2.6.87 沿用函数定义", "def _sent_use_last_good(why):" in text)
chk("V2.6.87 沿用不写 last_fetch_date",
    "绝不写 last_fetch_date" in text)
chk("V2.6.87 覆盖率分支优先于 rows 判空",
    text.index("if _ratio is not None and _ratio < SENT_COVERAGE_MIN:")
    < text.index("if not rows:\r\n            _sent_degrade_alert('数据不可用')"))
chk("V2.6.87 信号分量标注", "def _sent_comp_note(sig):" in text
    and "信号分量: %s" in text)
chk("V2.6.87 compute 返回分量字段",
    "'comp_have': _have_k" in text and "'comp_miss': _miss_k" in text
    and "'comp_total': len(_all_k)" in text)
chk("V2.6.87 fetching 置位与复位",
    "SENT_STATE['fetching'] = True" in text
    and "SENT_STATE['fetching'] = False" in text)
chk("V2.6.87 ready 三态文案", "取数中(后台线程" in text and "尚未发起取数" in text)
chk("V2.6.87 心跳文件名带账号+PID", "def heartbeat_path():" in text
    and "%s%s_%d%s" in text)
chk("V2.6.87 心跳循环变量不用 _f(防遮蔽模块级函数)",
    "for _fn in os.listdir(_base):" in text
    and "for _f in os.listdir(_base):" not in text)
chk("V2.6.87 心跳只告警不阻断", "本策略只告警, 不阻断下单" in text)
chk("V2.6.87 心跳接入 after_init + timer_poll",
    text.count("heartbeat_tick(") == 3)
chk("V2.6.87 buy_stock lp<=0 保护", "if _f(lp) <= 0:" in text
    and "无有效价格(lp=%.3f)" in text)
chk("V2.6.87 lp 保护早于除零点",
    text.index("无有效价格(lp=%.3f)") < text.index("int(amount / lp")
    if "int(amount / lp" in text else False)

# 7 MD5'''

assert lines.count('# 7 MD5') == 1
_idx = lines.index('# 7 MD5')
lines[_idx] = NEW

t = '\n'.join(lines)
open(P, 'wb').write(t.encode('utf-8'))
compile(t, P, 'exec')
print('OK _check_inv.py 已更新, 行数 %d' % len(lines))
