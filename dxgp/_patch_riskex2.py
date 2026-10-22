# -*- coding: utf-8 -*-
"""修复：排雷清单装载失败时不得锁定当日（否则先启策略、后跑工具的清单当天不生效）。"""
import sys

p = 'zt_shrink_strategy_gbk.py'
raw = open(p, 'rb').read()
text = raw.decode('gbk', errors='strict')
lines = text.split('\r\n')
base = len(lines)


def lineno(sub):
    hits = [i + 1 for i, ln in enumerate(lines) if sub in ln]
    if len(hits) != 1:
        print('ANCHOR FAIL %r -> %s' % (sub, hits))
        sys.exit(2)
    return hits[0]


edits = []

# 1) G 增加重试时间戳
a = lineno("G.risk_ex_date = ''             # V2.6.83: 排雷清单装载日(每日一次)")
edits.append((a + 1, a,
              ["G.risk_ex_try_ts = 0.0         # V2.6.83: 清单缺失时的上次尝试时间(60秒节流重试, 使当日补跑工具可即时生效)"],
              'risk try ts'))

# 2) 早退判断加节流
a = lineno("if G.risk_ex_date == G.today:")
edits.append((a, a - 1,
              ["    if not getattr(G, 'risk_ex', None) and \\",
               "            (time.time() - _f(getattr(G, 'risk_ex_try_ts', 0.0))) < 60.0:",
               "        return {}      # 清单尚未就绪: 60秒内不重复读盘(避免选股循环高频IO), 到点自动重试"],
              'risk throttle'))

# 3) 装载结果分支：成功才锁定当日
a = lineno("G.risk_ex = data")
# 该行后紧跟 G.risk_ex_date = G.today，替换两行
assert "G.risk_ex_date = G.today" in lines[a]
edits.append((a, a + 1,
              ["    G.risk_ex = data",
               "    if data:",
               "        G.risk_ex_date = G.today      # 只有真正装载到清单才锁定当日",
               "    else:",
               "        # V2.6.83: 装载失败不锁定当日 —— 实盘常见顺序是\"先启策略、后跑排雷工具\",",
               "        #   旧写法会把当日标记置上, 导致当天工具生成的清单要等次日才生效(空窗一整天)。",
               "        G.risk_ex_date = ''",
               "        G.risk_ex_try_ts = time.time()"],
              'risk lock only on success'))

for a, b, new, note in sorted(edits, key=lambda x: -x[0]):
    lines[a - 1:b] = new

out = '\r\n'.join(lines)
if out.count('\r\n') != len(lines) - 1:
    print('ABORT: CRLF mismatch')
    sys.exit(3)
compile(out, p, 'exec')
open(p, 'wb').write(out.encode('gbk', errors='strict'))
print('OK: %d edits, lines %d -> %d (delta %+d)' % (len(edits), base, len(lines), len(lines) - base))
