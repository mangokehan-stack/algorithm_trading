# -*- coding: utf-8 -*-
"""P2-8/P2-9 功能单测: 从 GBK 母版中抽出目标函数做行为验证"""
import ast, datetime, math, time, sys

src = open('zt_shrink_strategy_gbk.py', encoding='gbk', newline='').read()
tree = ast.parse(src)
want = {'_bars_to_dict', '_df_to_rows', '_f'}
mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want],
                 type_ignores=[])
ns = {'datetime': datetime, 'math': math, 'time': time}
exec(compile(mod, '<test>', 'exec'), ns)
_bars_to_dict = ns['_bars_to_dict']

# _is_bar_fresh 含 try/except, 需 TICK_STALE_MAX_SEC; 抽出后单独 exec
src_lines = src.split('\r\n')
i0 = next(i for i, ln in enumerate(src_lines) if ln.startswith('def _is_bar_fresh'))
i1 = next(i for i in range(i0 + 1, len(src_lines))
          if src_lines[i].startswith('def ') and not src_lines[i].startswith('def _is_bar_fresh'))
fn_src = '\n'.join(src_lines[i0:i1])
ns2 = {'datetime': datetime, 'math': math, 'time': time, 'TICK_STALE_MAX_SEC': 30}
exec(compile(fn_src, '<test2>', 'exec'), ns2)
_is_bar_fresh = ns2['_is_bar_fresh']

fails = []

def chk(name, got, exp):
    ok = got == exp
    print('%-46s got=%r exp=%r %s' % (name, got, exp, 'PASS' if ok else 'FAIL'))
    if not ok:
        fails.append(name)

# ---- P2-8: _bars_to_dict 各类键 ----
now_ts = time.time()
today_dt = datetime.datetime.fromtimestamp(now_ts)
today_s = today_dt.strftime('%Y%m%d')
old_ts = now_ts - 86400 * 3
d = {
    today_s: {'close': 10.0},                                  # 8位数字键(原行为)
    int(old_ts): {'close': 9.0},                               # int64 epoch 秒
    int(old_ts * 1000): {'close': 8.0},                        # epoch 毫秒
    float(today_ts if False else int(old_ts)): {'close': 7.0}, # float epoch 秒
    today_dt: {'close': 6.0},                                  # datetime 对象
    str(today_dt): {'close': 5.0},                             # 'YYYY-MM-DD HH:MM:SS'
}
out = _bars_to_dict(d)
exp_keys = {today_s,
            datetime.datetime.fromtimestamp(int(old_ts)).strftime('%Y%m%d'),
            datetime.datetime.fromtimestamp(int(old_ts * 1000) // 1000).strftime('%Y%m%d'),
            datetime.datetime.fromtimestamp(int(old_ts)).strftime('%Y%m%d'),
            today_s, today_s}
chk('P2-8 keys', sorted(out.keys()), sorted(exp_keys))
# 同日期键碰撞时后写覆盖(标准 dict 语义): 20261019->5.0, 20261016->8.0
chk('P2-8 values', sorted(v['close'] for v in out.values()), [5.0, 8.0])
chk('P2-8 no 8-digit-trash', all(len(k) == 8 and k.isdigit() for k in out), True)

# 8位 YYYYMMDD 键必须原样保留(不被误判 epoch)
chk('P2-8 plain8 keep', _bars_to_dict({20261013: {'close': 1.0}}).get('20261013'), {'close': 1.0})
# float 8位+尾巴
chk('P2-8 float8 keep', _bars_to_dict({20261013.0: {'close': 2.0}}).get('20261013'), {'close': 2.0})
# None 输入
chk('P2-8 none', _bars_to_dict(None), {})

# ---- P2-9: _is_bar_fresh 时间戳下界(注意: 容差是第3个位置参数) ----
chk('P2-9 fresh now', _is_bar_fresh(int(time.time()), None, 30), True)
chk('P2-9 stale old', _is_bar_fresh(int(time.time()) - 600, None, 30), False)
chk('P2-9 future sec', _is_bar_fresh(int(time.time()) + 600, None, 30), False)
chk('P2-9 future ms', _is_bar_fresh(int((time.time() + 600) * 1000), None, 30), False)
chk('P2-9 future str14', _is_bar_fresh(
    (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime('%Y%m%d%H%M%S'), None, 30), False)
chk('P2-9 future str12', _is_bar_fresh(
    (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime('%Y%m%d%H%M'), None, 30), False)
chk('P2-9 str fresh', _is_bar_fresh(
    datetime.datetime.now().strftime('%Y%m%d%H%M%S'), None, 3600), True)
chk('P2-9 garbage', _is_bar_fresh('abc', None, 30), False)

print()
if fails:
    print('FAILED:', fails)
    sys.exit(1)
print('ALL FUNCTIONAL TESTS PASS')
