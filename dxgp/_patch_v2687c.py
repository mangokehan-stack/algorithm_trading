# -*- coding: utf-8 -*-
"""V2.6.87 补丁c: 取数早期失败也要把覆盖标记为 0, 否则"行情全空"不会走沿用分支"""
P = 'zt_shrink_strategy_gbk.py'
t = open(P, 'rb').read().decode('gbk')


def rep(old, new, tag):
    global t
    old = old.replace('\r\n', '\n').replace('\n', '\r\n')
    new = new.replace('\r\n', '\n').replace('\n', '\r\n')
    n = t.count(old)
    assert n == 1, '[%s] 匹配 %d 次' % (tag, n)
    t = t.replace(old, new, 1)
    print('OK %s' % tag)


# 1) G.C 不可用
rep(
    """    C = getattr(G, 'C', None)
    if C is None:
        _sent_wlog('G.C 不可用(非QMT内置环境), 情绪数据跳过(中性)')
        return None""",
    """    C = getattr(G, 'C', None)
    if C is None:
        # V2.6.87: 取数通道整个不可用 -> 覆盖率记 0, 让上游走"沿用上次成功信号"
        #   (旧版直接 return None, 上游只当"数据不可用"降级中性, 与覆盖率不足是两套处置)
        SENT_STATE['cover'] = {'req': 0, 'ok': 0, 'fail': 0, 'retry': 0,
                               'ratio': 0.0, 'samples': ['G.C 不可用'], 'fields_all': False}
        _sent_wlog('G.C 不可用(非QMT内置环境), 情绪数据跳过(中性)')
        return None""",
    'C不可用置覆盖率0')

# 2) 股票列表为空
rep(
    """        if not _stocks:
            _sent_wlog('未取到A股股票列表(内置C接口), 情绪数据跳过(中性)')
            return None""",
    """        if not _stocks:
            SENT_STATE['cover'] = {'req': 0, 'ok': 0, 'fail': 0, 'retry': 0,
                                   'ratio': 0.0, 'samples': ['股票列表为空'],
                                   'fields_all': False}
            _sent_wlog('未取到A股股票列表(内置C接口), 情绪数据跳过(中性)')
            return None""",
    '股票列表空置覆盖率0')

# 3) 外层异常
rep(
    """    except Exception as _e:
        _sent_wlog('情绪取数异常(内置通道), 数据跳过(中性): %s' % _e)
        return None""",
    """    except Exception as _e:
        SENT_STATE['cover'] = {'req': 0, 'ok': 0, 'fail': 0, 'retry': 0,
                               'ratio': 0.0, 'samples': [_exc_text(_e)],
                               'fields_all': False}
        _sent_wlog('情绪取数异常(内置通道), 数据跳过(中性): %s' % _exc_text(_e))
        return None""",
    '取数异常置覆盖率0')

open(P, 'wb').write(t.encode('gbk'))
compile(t, P, 'exec')
print('WROTE %d bytes' % len(t.encode('gbk')))
