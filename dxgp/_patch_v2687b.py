# -*- coding: utf-8 -*-
"""V2.6.87 修复: 心跳扫描里循环变量 _f 遮蔽模块级 _f, 导致 UnboundLocalError 被吞"""
P = 'zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')

OLD = (
    "        # 2) 找同伴(同账号、非自己、心跳仍新鲜)\n"
    "        _peers = []\n"
    "        try:\n"
    "            for _f in os.listdir(_base):\n"
    "                if not (_f.startswith(_pre) and _f.endswith(_ext)):\n"
    "                    continue\n"
    "                _p = os.path.join(_base, _f)\n"
    "                if os.path.normpath(_p) == os.path.normpath(_me):\n"
    "                    continue\n"
    "                try:\n"
    "                    with open(_p, 'r', encoding='utf-8') as _fh:\n"
    "                        _d = json.load(_fh)\n"
    "                except Exception:\n"
    "                    continue\n"
    "                if not isinstance(_d, dict):\n"
    "                    continue\n"
    "                _ts = _f(_d.get('ts') or 0.0)\n"
    "                if (_now - _ts) <= HEARTBEAT_STALE_SEC:\n"
    "                    _peers.append((int(_f(_d.get('pid') or 0)), _ts,\n"
    "                                   str(_d.get('ver') or '?'), _f))\n"
    "        except Exception:\n"
    "            pass\n"
)

NEW = (
    "        # 2) 找同伴(同账号、非自己、心跳仍新鲜)\n"
    "        #    注意: 循环变量绝不能叫 _f —— 模块级 _f 是 float 转换函数, 同名会把 _f 变成\n"
    "        #    局部变量, 下方 _f(_d.get('ts')) 直接 UnboundLocalError, 又被 except 静默吞掉,\n"
    "        #    结果是\"看起来在检测、实际永远检测不到同伴\"(V2.6.87 自查实测踩到)。\n"
    "        _peers = []\n"
    "        try:\n"
    "            for _fn in os.listdir(_base):\n"
    "                if not (_fn.startswith(_pre) and _fn.endswith(_ext)):\n"
    "                    continue\n"
    "                _p = os.path.join(_base, _fn)\n"
    "                if os.path.normpath(_p) == os.path.normpath(_me):\n"
    "                    continue\n"
    "                try:\n"
    "                    with open(_p, 'r', encoding='utf-8') as _fh:\n"
    "                        _d = json.load(_fh)\n"
    "                except Exception:\n"
    "                    continue\n"
    "                if not isinstance(_d, dict):\n"
    "                    continue\n"
    "                _ts = _f(_d.get('ts') or 0.0)\n"
    "                if (_now - _ts) <= HEARTBEAT_STALE_SEC:\n"
    "                    _peers.append((int(_f(_d.get('pid') or 0)), _ts,\n"
    "                                   str(_d.get('ver') or '?'), _fn))\n"
    "        except Exception as _e:\n"
    "            # 不再静默: 探测本身出错要说出来, 否则\"检测不到同伴\"和\"检测功能坏了\"分不清\n"
    "            log('[安全][提示] 双实例探测异常(本轮跳过, 下轮重试): %s' % _exc_text(_e))\n"
)

OLD = OLD.replace('\n', '\r\n')
NEW = NEW.replace('\n', '\r\n')
n = t.count(OLD)
assert n == 1, '锚点匹配 %d 次' % n
t = t.replace(OLD, NEW, 1)
open(P, 'wb').write(t.encode('gbk'))
compile(t, P, 'exec')
print('OK 心跳扫描变量名已修 _.f -> _fn, compile 通过')
