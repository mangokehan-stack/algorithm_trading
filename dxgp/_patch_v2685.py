# -*- coding: utf-8 -*-
"""V2.6.85 三合一补丁(用户逐项确认 1/2/3 全改)

1) 情绪降级不锁日: last_fetch_date 从"进入汇总时"移到"信号真正算出后"
2) 拆双指纹: param_fingerprint 排除 VERSION(稳定, 供 verified_fp 比对)
             新增 code_fingerprint(参数+VERSION, 供"代码是否变更"提示)
3) 情绪覆写补中文释义: 把 overrides 的英文键翻译成"原名 旧值->新值(方向)"
"""
import sys

P = 'zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
text = raw.decode('gbk')          # strict: 解码失败即熔断
lines = text.split('\r\n')
N0 = len(lines)


def find(pred, desc, start=0, end=None):
    _end = len(lines) if end is None else end
    hits = [i for i in range(start, _end) if pred(lines[i])]
    if len(hits) != 1:
        print('FATAL: 锚点"%s"命中 %d 处 (需要 1 处)' % (desc, len(hits)))
        for h in hits[:6]:
            print('   L%d %s' % (h + 1, lines[h][:120]))
        sys.exit(1)
    return hits[0]


edits = []   # (a, b, new_lines)  b == a-1 表示"在 a 之前插入"


# ============ 改动 2-a: _FP_DENY 排除 VERSION ============
a_deny = find(lambda l: l.strip() == "'SENT_STATE',                                            # 运行时状态(非配置)",
              '_FP_DENY 末尾 SENT_STATE')
edits.append((a_deny, a_deny, [
    lines[a_deny],
    "    'VERSION',                                              # 版本号(非行为参数): 不参与参数指纹,",
    "                                                            #   改由 code_fingerprint 单独纳入, 见函数说明",
]))


# ============ 改动 2-b: 重写 param_fingerprint + 新增 code_fingerprint ============
a_pf = find(lambda l: l == 'def param_fingerprint():', 'param_fingerprint 定义')
b_pf = find(lambda l: l == "        return 'NA', ''", 'param_fingerprint 末尾 return',
            start=a_pf, end=a_pf + 40)

NEW_PF = [
    "def _fp_calc(keys):",
    "    # FNV-1a 32位: 返回 (8位十六进制, 原文); 原文用于人工比对哪个参数变了",
    "    _raw = '|'.join('%s=%s' % (k, globals().get(k)) for k in keys)",
    "    _h = 2166136261",
    "    for _c in _raw.encode('utf-8'):",
    "        _h = ((_h ^ _c) * 16777619) & 0xFFFFFFFF",
    "    return '%08x' % _h, _raw",
    "",
    "",
    "def param_fingerprint():",
    "    \"\"\"参数指纹(样本内外验证凭据): 只含行为参数, 【不含 VERSION】。",
    "    同指纹 = 同一套参数组合; 任何参数变更后必须在样本外区间复跑并记录结果,",
    "    严禁在全样本上反复调参(详见 README 的样本内外验证纪律)。",
    "    V2.6.85修复: 把 VERSION 从本指纹中剔除 —— V2.6.70 曾将 VERSION 纳入指纹以覆盖",
    "    \"不改参数只改代码\"的情形, 但副作用是每次升版指纹必变: 用户在状态文件记录",
    "    verified_fp 后, 下次纯文案升版立刻红标\"参数未经样本外验证\", 反复误报导致告警",
    "    疲劳, 真正改了参数时反而被忽略。现拆为两个指纹: 本函数(参数, 稳定) 供",
    "    verified_fp 比对; code_fingerprint(参数+VERSION) 供\"代码是否变更\"提示。\"\"\"",
    "    # P2-2修复(2026-10-19): 显式列表 -> 自动捕获(机制根治漏参)。原显式列表已三度漏参",
    "    # (V2.6.81 新加的 MARKET_CAP_MIN_YI/MAX_YI、SENT_REGIME_PANIC_LO、",
    "    # SENT_EVT_FRENZY_*/SENT_EVT_PANIC_* 等约40个行为参数未纳入), 指纹失真导致",
    "    # \"参数没变但行为变了\"无法被发现; 现自动收集全部 UPPER_CASE 模块级常量(标量/",
    "    # 容器), 仅排除与行为无关的路径/URL/编码/账户/展示映射/运行时状态(见 _FP_DENY)。",
    "    # 注意: 本函数只在启动时调用一次, 此时 globals() 已含全部常量(含文件后部 SENT_*)。",
    "    try:",
    "        return _fp_calc(sorted(_fp_keys()))",
    "    except Exception:",
    "        return 'NA', ''",
    "",
    "",
    "def code_fingerprint():",
    "    \"\"\"版本指纹 = 参数 + VERSION。",
    "    与 param_fingerprint 分开的意义:",
    "      * 参数指纹不变 + 版本指纹变  -> 只改了代码/文案, 参数本身没动(不红标, 只提示复核)",
    "      * 参数指纹变   + 版本指纹变  -> 参数确实改了(红标 verified_fp 不一致, 须样本外复跑)",
    "    旧版把两者合成一个数, 上述两种情形长得完全一样, 无法区分。\"\"\"",
    "    try:",
    "        return _fp_calc(sorted(list(_fp_keys()) + ['VERSION']))",
    "    except Exception:",
    "        return 'NA', ''",
]
edits.append((a_pf, b_pf, NEW_PF))


# ============ 改动 2-c: 启动输出两行指纹 ============
a_out = find(lambda l: l.strip() == '_fp, _raw = param_fingerprint()', '指纹取值')
edits.append((a_out, a_out, [
    '            _fp, _raw = param_fingerprint()',
    '            _cfp, _craw = code_fingerprint()',
]))

a_log1 = find(lambda l: "'区间复跑并记录结果, 严禁在全样本上反复调参(详见README)' % _fp)" in l,
              '参数指纹日志尾')
edits.append((a_log1, a_log1, [
    lines[a_log1],
    "            log('[版本指纹] %s | 当前版本=%s; 版本变更表示代码可能改动, 参数指纹不变'",
    "                '则参数本身未变(如需复核请比对改动点)' % (_cfp, VERSION))",
]))


# ============ 改动 1: 情绪成功写日的时机 ============
a_drop = find(lambda l: l.strip() == "SENT_STATE['last_fetch_date'] = _t", 'last_fetch_date 写入')
edits.append((a_drop, a_drop, []))          # 删除该行

a_ok = find(lambda l: l.strip().startswith("SENT_STATE['degrade_days'] = 0"),
            '成功后清零降级计数')
edits.append((a_ok, a_ok, [
    lines[a_ok],
    "        # V2.6.85修复: \"今日已刷新\"只在信号真正算出后才锁定。旧版在函数入口就写",
    "        #   last_fetch_date, 之后 4 个降级分支(无昨日数据/数据陈旧/信号算不出/异常)",
    "        #   直接 return 却已写死标记 -> sent_daily_refresh 当天不再重试, 情绪全天中性",
    "        #   (L1闸门/L3覆写/L4缩仓全部失效), 日志只有一行\"降级中性\", 极难察觉。",
    "        SENT_STATE['last_fetch_date'] = _t",
]))


# ============ 改动 3: 覆写中文释义 ============
a_def = find(lambda l: l == 'def _sent_apply_rows(rows):', '_sent_apply_rows 定义')
NEW_NOTE = [
    "def _sent_override_note(ovs):",
    "    # V2.6.85: 把 L3 档位覆写翻译成人话(原名 旧值->新值(方向)), 供日志使用。",
    "    #   旧版只打 overrides=BUY_MIN_ELAPSED_MIN=45;SHRINK_BUY_RATIO=0.3, 全是英文键和",
    "    #   裸数字, 看不出\"买点窗口被推后15分钟\"; 且启动行打印的是原始参数, 与实际生效值",
    "    #   不一致, 用户无法判断今天到底按哪套跑。未知键按原样输出, 不隐藏。",
    "    if not isinstance(ovs, dict) or not ovs:",
    "        return ''",
    "    _meta = {",
    "        'SHRINK_BUY_RATIO': ('缩量阈值', '越低越严: 要求当日量能更小才算缩量到位'),",
    "        'BUY_MIN_ELAPSED_MIN': ('开盘等待分钟', '越长越晚: 开盘后要等更久才允许买入'),",
    "        'EXPAND_SELL_RATIO': ('放量止盈倍数', '越低越易卖: 达到更小的量能倍数即止盈'),",
    "    }",
    "    _out = []",
    "    for _k in sorted(ovs.keys()):",
    "        _nm, _dir = _meta.get(_k, (_k, '未收录的键, 按原值使用'))",
    "        _old = globals().get(_k, None)",
    "        try:",
    "            _os = ('%.2f' % float(_old)).rstrip('0').rstrip('.')",
    "        except Exception:",
    "            _os = str(_old)",
    "        try:",
    "            _ns = ('%.2f' % float(ovs[_k])).rstrip('0').rstrip('.')",
    "        except Exception:",
    "            _ns = str(ovs[_k])",
    "        _out.append('%s %s->%s (%s)' % (_nm, _os, _ns, _dir))",
    "    return ' | '.join(_out)",
    "",
    "",
]
edits.append((a_def, a_def - 1, NEW_NOTE))   # 插在 def 之前

a_sig = find(lambda l: "                      sig['size_mult'], _ovs))" in l, '信号刷新日志尾')
edits.append((a_sig, a_sig, [
    lines[a_sig],
    "        _ov_note = _sent_override_note(sig['overrides'])",
    "        if _ov_note:",
    "            _sent_wlog('参数覆写(%s档)已生效: %s' % (sig['regime'], _ov_note))",
]))


# ============ 倒序应用 ============
edits.sort(key=lambda e: e[0], reverse=True)
for a, b, new in edits:
    lines[a:b + 1] = new

out = '\r\n'.join(lines)
if out.count('\r\n') != len(lines) - 1:
    print('FATAL: CRLF 数量不一致, 拒绝写入')
    sys.exit(1)
try:
    compile(out, P, 'exec')
except SyntaxError as e:
    print('FATAL: 语法错误 L%s: %s' % (e.lineno, e.msg))
    sys.exit(1)

open(P, 'wb').write(out.encode('gbk'))
print('OK: %d edits, lines %d -> %d (delta %+d)' % (len(edits), N0, len(lines), len(lines) - N0))
