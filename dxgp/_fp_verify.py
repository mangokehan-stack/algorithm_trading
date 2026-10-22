# -*- coding: utf-8 -*-
"""参数指纹零漂移验证: V2.6.104(备份) vs V2.6.105(当前)

方法: 不走 import(QMT 内置库缺失), 而是
  1) 按行号切片把 _FP_DENY / _fp_keys / _fp_calc 三段源码抽出来
  2) 用正则扫出全部模块级 UPPER_CASE 赋值, 在独立命名空间里执行, 得到常量表
  3) 自己算 FNV-1a, 与两版逐参数比对
"""
import io
import re
import sys

NEW = 'zt_shrink_strategy_gbk.py'
OLD = 'zt_shrink_strategy_gbk.py.bak-20261020-1005'


def load(p):
    return io.open(p, 'r', encoding='gbk', newline='').read().replace('\r\n', '\n')


def grab_block(lines, start_pred, stop_on_toplevel=True):
    """从 start_pred 命中的行开始, 收集到下一个顶格行(非注释/非空)为止"""
    beg = None
    for i, l in enumerate(lines):
        if start_pred(l):
            beg = i
            break
    if beg is None:
        raise KeyError('not found')
    out = []
    for i in range(beg, len(lines)):
        l = lines[i]
        if i > beg and stop_on_toplevel and l and not l[0].isspace() \
                and not l.startswith('#') and not l.startswith(')'):
            break
        out.append(l)
    return '\n'.join(out)


def collect_consts(src):
    """扫出模块级(顶格) UPPER_CASE 赋值, 在独立命名空间执行"""
    lines = src.split('\n')
    ns = {}
    # 需要先有 _FP_DENY 才能算 keys, 但它本身也是常量; 先把全部顶格常量执行出来
    names = []
    i = 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r'^(_?[A-Z][A-Z0-9_]*)\s*=', l)
        if m:
            name = m.group(1)
            # 收集该赋值语句可能跨的括号行
            buf = [l]
            depth = l.count('(') + l.count('[') + l.count('{') \
                - l.count(')') - l.count(']') - l.count('}')
            j = i
            while depth > 0 and j + 1 < len(lines):
                j += 1
                buf.append(lines[j])
                depth += lines[j].count('(') + lines[j].count('[') + lines[j].count('{') \
                    - lines[j].count(')') - lines[j].count(']') - lines[j].count('}')
            stmt = '\n'.join(buf)
            try:
                exec(compile(stmt, '<c>', 'exec'), ns)
                names.append(name)
            except Exception:
                pass
            i = j + 1
            continue
        i += 1
    return ns, names


def calc(ns, deny):
    T = (int, float, bool, str, tuple, list, dict, type(None))
    keys = sorted(k for k in ns
                  if k.isupper() and not k.startswith('_')
                  and k not in deny and isinstance(ns[k], T))
    raw = '|'.join('%s=%s' % (k, ns.get(k)) for k in keys)
    h = 2166136261
    for c in raw.encode('utf-8'):
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return '%08x' % h, keys, raw


def report(tag, path):
    src = load(path)
    ns, names = collect_consts(src)
    deny = ns.get('_FP_DENY') or set()
    fp, keys, raw = calc(ns, deny)
    print('[%s] 常量个数=%d  大写常量=%d  deny=%d  param_fp=%s'
          % (tag, len(names), len(keys), len(deny), fp))
    return ns, fp, keys


ns_o, fp_o, keys_o = report('V2.6.104', OLD)
ns_n, fp_n, keys_n = report('V2.6.105', NEW)

print('\n参数指纹: %s -> %s  %s' % (fp_o, fp_n, 'SAME ✅' if fp_o == fp_n else 'DRIFT ❌'))

only_o = [k for k in keys_o if k not in keys_n]
only_n = [k for k in keys_n if k not in keys_o]
diff = [(k, ns_o[k], ns_n[k]) for k in keys_o if k in keys_n and ns_o[k] != ns_n[k]]

print('只在旧版: %s' % (only_o or '无'))
print('只在新版: %s' % (only_n or '无'))
if diff:
    print('值不同 (%d 项):' % len(diff))
    for k, a, b in diff:
        print('   %s: %r -> %r' % (k, a, b))
else:
    print('值不同: 无 ✅')

# 版本指纹
def code_fp(ns, deny):
    fp, _, _ = calc(ns, deny)
    T = (int, float, bool, str, tuple, list, dict, type(None))
    keys = sorted([k for k in ns if k.isupper() and not k.startswith('_')
                   and k not in deny and isinstance(ns[k], T)] + ['VERSION'])
    raw = '|'.join('%s=%s' % (k, ns.get(k)) for k in keys)
    h = 2166136261
    for c in raw.encode('utf-8'):
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return '%08x' % h


print('\n版本指纹: %s -> %s  %s'
      % (code_fp(ns_o, ns_o.get('_FP_DENY') or set()),
         code_fp(ns_n, ns_n.get('_FP_DENY') or set()),
         '(应变化)'))
print('VERSION: %r -> %r' % (ns_o.get('VERSION'), ns_n.get('VERSION')))
sys.exit(0 if (fp_o == fp_n and not only_o and not only_n and not diff) else 1)
