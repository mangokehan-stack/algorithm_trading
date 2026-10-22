# -*- coding: utf-8 -*-
"""
V2.6.133 补丁：
  【对照实验】停掉 log_guard 的 10 秒注册（可一键恢复）
  【探针增强】相位统计增加「绝对秒数」分布，直接比对 log_guard 节拍

纪律：
  - 全部在内存完成替换，全部锚点通过后才写盘
  - 母版 GBK + CRLF，锚点必须写 \r\n
  - 不新增模块级大写常量（不污染参数指纹）
"""
import io
import hashlib
import sys

P = 'zt_shrink_strategy_gbk.py'
OLD_VER = 'V2.6.132'
NEW_VER = 'V2.6.133'

raw = open(P, 'rb').read()
text = raw.decode('gbk')          # 严格解码，不做 replace
orig_md5 = hashlib.md5(raw).hexdigest().upper()
print('BEFORE md5 =', orig_md5, 'size =', len(raw))

assert orig_md5 == 'E0A2B92F1268131B58B9E5627394BC85', 'MD5 与预期不符，拒绝继续'
assert text.count(OLD_VER) > 0, '找不到旧版本号'

reps = []   # (name, old, new)

# ---------------------------------------------------------------- 1. log_guard 注册加开关
old1 = (
    "        try:\r\n"
    "            ContextInfo.run_time('log_guard', '10nSecond', '2000-01-01 00:00:00')\r\n"
    "            log('日志看门狗: log_guard(每10秒空跑落盘)')\r\n"
    "        except Exception:\r\n"
    "            log('日志看门狗注册失败, 仅依赖轮次心跳落盘')\r\n"
)
new1 = (
    "        # V2.6.133 对照实验: log_guard 的 10 秒节拍被怀疑是解析期卡顿源。\r\n"
    "        #   证据(V2.6.132 相位探针): 5 轮「单次最长」= 10.0010/9.9969/\r\n"
    "        #   10.0002/9.9985/10.0007 秒, 均值 9.9995、标准差 1.54 毫秒;\r\n"
    "        #   且卡顿落点 4/4 全部落在 sec1, 集中度 100%。\r\n"
    "        #   全部代码里唯一的 10 秒节拍就是本函数(timer_poll 是 30 秒)。\r\n"
    "        #   但「相位吻合」只是相关性 —— 停掉它跑一轮, 看 10 秒刻度是否消失,\r\n"
    "        #   才是判据。故本版【默认停用】, 保留开关可一键恢复。\r\n"
    "        #   停用代价: 只有静默期(盘前/午休)日志可能滞留内存缓冲。\r\n"
    "        #     实测取数线程解析期间本来就一行不打(17:31/17:37 各静默 3 分钟),\r\n"
    "        #     且任何 log() 调用自身会触发 flush, 所以盘中不受影响。\r\n"
    "        #   开关写成函数内局部量, 不进参数指纹。\r\n"
    "        _lg_on = False      # V2.6.133 对照实验: False=停用, True=恢复旧行为\r\n"
    "        try:\r\n"
    "            if _lg_on:\r\n"
    "                ContextInfo.run_time('log_guard', '10nSecond', '2000-01-01 00:00:00')\r\n"
    "                log('日志看门狗: log_guard(每10秒空跑落盘)')\r\n"
    "            else:\r\n"
    "                log('[对照实验] 日志看门狗 log_guard 本轮【已停用】(V2.6.133): '\r\n"
    "                    '目的=验证解析期 10 秒卡顿是否由本定时器引起; '\r\n"
    "                    '若解析耗时明显下降则确证, 之后把 _lg_on 改回 True 即可恢复')\r\n"
    "        except Exception:\r\n"
    "            log('日志看门狗注册失败, 仅依赖轮次心跳落盘')\r\n"
)
reps.append(('log_guard 开关', old1, new1))

# ---------------------------------------------------------------- 2. 相位采集增加绝对秒数
old2 = (
    "                if _pb2_dt >= 1.0:\r\n"
    "                    # V2.6.132: 落点取【结束时刻】的秒内余数 —— 阻塞是在这段时间\r\n"
    "                    #   里被恢复的, 恢复点才贴着定时器节拍。\r\n"
    "                    _pb2_k = int(_pb2_t1) % 10\r\n"
    "                    _pb2_slow[_pb2_k] = _pb2_slow.get(_pb2_k, 0) + 1\r\n"
    "                    _pb2_slow_n += 1\r\n"
)
new2 = (
    "                if _pb2_dt >= 1.0:\r\n"
    "                    # V2.6.132: 落点取【结束时刻】的秒内余数 —— 阻塞是在这段时间\r\n"
    "                    #   里被恢复的, 恢复点才贴着定时器节拍。\r\n"
    "                    _pb2_k = int(_pb2_t1) % 10\r\n"
    "                    _pb2_slow[_pb2_k] = _pb2_slow.get(_pb2_k, 0) + 1\r\n"
    "                    _pb2_slow_n += 1\r\n"
    "                    # V2.6.133: 除「秒内余数」外, 再记 (起点秒, 结束秒, 耗时)。\r\n"
    "                    #   余数只能证明「周期是 10 的倍数」, 分不清 10/20/30 秒;\r\n"
    "                    #   记下起止绝对秒后, 可算出真实的【间隔序列】—— 若相邻两\r\n"
    "                    #   次卡顿的起点秒差恒为 10, 即确证 10 秒节拍; 若为 30 或\r\n"
    "                    #   不规则, 则 log_guard 被排除。\r\n"
    "                    _pb2_slow_seq.append([int(_pb2_t0), int(_pb2_t1),\r\n"
    "                                          round(_pb2_dt, 4)])\r\n"
)
reps.append(('相位绝对秒数', old2, new2))

# ---------------------------------------------------------------- 3. 相位序列初始化
old3 = (
    "        _pb2_slow = {}         # {秒内余数: 次数} 仅 >=1 秒的采样\r\n"
    "        _pb2_slow_n = 0        # >=1 秒采样总次数\r\n"
)
new3 = (
    "        _pb2_slow = {}         # {秒内余数: 次数} 仅 >=1 秒的采样\r\n"
    "        _pb2_slow_n = 0        # >=1 秒采样总次数\r\n"
    "        _pb2_slow_seq = []     # V2.6.133: [(起点秒, 结束秒, 耗时)] 供算真实间隔\r\n"
)
reps.append(('相位序列初始化', old3, new3))

# ---------------------------------------------------------------- 4. 相位日志增加间隔序列
old4 = (
    "                    _sent_wlog('[基准] 卡顿落点相位: 共%d次采样>=1秒, 最集中 %s | '\r\n"
    "                               '集中度%.1f%% (>80%%=确证固定周期源; <40%%=非单一定时器)'\r\n"
    "                               % (_pb2_slow_n, _pb2_desc, _pb2_conc))\r\n"
)
new4 = (
    "                    _sent_wlog('[基准] 卡顿落点相位: 共%d次采样>=1秒, 最集中 %s | '\r\n"
    "                               '集中度%.1f%% (>80%%=确证固定周期源; <40%%=非单一定时器)'\r\n"
    "                               % (_pb2_slow_n, _pb2_desc, _pb2_conc))\r\n"
    "                    # V2.6.133: 打印真实间隔。判据 —— 相邻两次卡顿【起点秒】之差\r\n"
    "                    #   若恒为 10, 就是 10 秒节拍(log_guard); 恒为 30 则是 timer_poll;\r\n"
    "                    #   参差不齐则说明是外部事件, 与两个定时器都无关。\r\n"
    "                    _pb2_gaps = []\r\n"
    "                    for _gi in range(1, len(_pb2_slow_seq)):\r\n"
    "                        _pb2_gaps.append(_pb2_slow_seq[_gi][0]\r\n"
    "                                         - _pb2_slow_seq[_gi - 1][0])\r\n"
    "                    _pb2_seq_txt = ' '.join(['s' + str(_sq[0] % 60) + '+' + str(_sq[2])\r\n"
    "                                             for _sq in _pb2_slow_seq[:6]])\r\n"
    "                    if _pb2_gaps:\r\n"
    "                        _sent_wlog('[基准] 卡顿时刻序列: %s | 起点间隔=%s '\r\n"
    "                                   '(相邻差恒为10=10秒节拍; 恒为30=timer_poll; '\r\n"
    "                                   '参差=外部事件, 与两个定时器都无关)'\r\n"
    "                                   % (_pb2_seq_txt,\r\n"
    "                                      ','.join([str(_g) for _g in _pb2_gaps])))\r\n"
    "                    else:\r\n"
    "                        _sent_wlog('[基准] 卡顿时刻序列: %s (只有1次, 无法算间隔)'\r\n"
    "                                   % _pb2_seq_txt)\r\n"
)
reps.append(('相位间隔序列', old4, new4))

# ---------------------------------------------------------------- 5. 版本号（文件头 + VERSION 常量）
# 文件头首次出现
hdr_old = '版本号: ' + OLD_VER
assert text.count(hdr_old) >= 1, '文件头版本号找不到'
idx_hdr = text.find(hdr_old)
text = text[:idx_hdr] + '版本号: ' + NEW_VER + text[idx_hdr + len(hdr_old):]

const_old = "VERSION = '" + OLD_VER + "'"
assert text.count(const_old) == 1, 'VERSION 常量出现次数 != 1，实际 %d' % text.count(const_old)
assert len(OLD_VER) == len(NEW_VER)
idx_const = text.find(const_old)
text = (text[:idx_const] + "VERSION = '" + NEW_VER + "'"
        + text[idx_const + len(const_old):])

# ---------------------------------------------------------------- 应用替换
for name, old, new in reps:
    cnt = text.count(old)
    if cnt != 1:
        print('[FAIL] %s 锚点命中 %d 次(应为1)' % (name, cnt))
        sys.exit(1)
    if old == new:
        print('[FAIL] %s old==new' % name)
        sys.exit(1)
    text = text.replace(old, new, 1)
    print('[OK] %s' % name)

# ---------------------------------------------------------------- 写盘前校验
# 注意: OLD_VER 在【历史注释】里仍会保留多处(版本记录/改动说明), 那是应当保留的。
#   只断言两个【权威位置】已更新: 文件头第一行 + VERSION 常量。
assert ('版本号: ' + NEW_VER) in text, '文件头版本号未更新'
assert ("VERSION = '" + NEW_VER + "'") in text, 'VERSION 常量未更新'
assert ("VERSION = '" + OLD_VER + "'") not in text, 'VERSION 常量仍为旧值'
# 文件头: 第一处 "版本号: " 必须是新版本
_first_hdr = text[text.find('版本号: '):text.find('版本号: ') + 30]
assert NEW_VER in _first_hdr, '文件头首个版本号不是新版，实际 %r' % _first_hdr
assert '\n' not in text.replace('\r\n', ''), '存在裸 LF'

out = text.encode('gbk')          # 严格编码，失败即抛
compile(text, P, 'exec')
print('[OK] GBK 编码 + compile 通过')

# 不变量：绝不止损
import ast
tree = ast.parse(text)
n_stop = 0
for node in ast.walk(tree):
    if isinstance(node, ast.Attribute) and node.attr == 'stop_order':
        n_stop += 1
    if isinstance(node, ast.Name) and node.id == 'stop_order':
        n_stop += 1
assert n_stop == 0, 'stop_order 代码体引用 %d 次(必须0)' % n_stop
assert 'NEVER_STOP_LOSS = True' in text, 'NEVER_STOP_LOSS 被改动'
print('[OK] stop_order AST = 0, NEVER_STOP_LOSS 未动')

open(P, 'wb').write(out)
new_md5 = hashlib.md5(out).hexdigest().upper()
print('AFTER md5 =', new_md5, 'size =', len(out))
print('DONE ->', NEW_VER)
