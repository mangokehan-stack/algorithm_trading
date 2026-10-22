# -*- coding: utf-8 -*-
"""V2.6.90 三项情绪取数加固补丁

1) 取数总预算 180 秒: 主循环每批开始前检查, 超预算带已取到的部分收尾
2) 整体不可用熔断: 连续 3 批全失败且零成功 -> 立即停止拆批与第二轮全字段重试
3) 跳过日志带已运行时长: 区分"慢"与"卡死"

严格约束: 不新增任何模块级大写常量 —— _fp_keys() 用 globals() 收集全部
UPPER_CASE 常量, 新增一个就会改变参数指纹, 让 verified_fp 无端失效。
预算值以函数内局部常量形式存在(不进 globals)。
"""
import io

P = 'zt_shrink_strategy_gbk.py'
raw = open(P, 'rb').read()
t = raw.decode('gbk')
assert t.count('\r\n') == t.count('\n'), '换行不是纯 CRLF'
t = t.replace('\r\n', '\n')
n_edit = 0


def rep(old, new, tag):
    global t, n_edit
    c = t.count(old)
    assert c == 1, '[%s] 锚点出现 %d 次(应为1)' % (tag, c)
    t = t.replace(old, new, 1)
    n_edit += 1
    print('  OK %s' % tag)


# ---------------------------------------------------------------- A1 跳过日志带时长
A1_OLD = """    _lock = _SENT_FETCH_LOCK
    if _lock is None or not _lock.acquire(False):
        _sent_wlog('情绪取数线程已在运行或锁不可用, 本轮跳过(中性, 不阻塞交易)')
        return None
"""
A1_NEW = """    _lock = _SENT_FETCH_LOCK
    if _lock is None or not _lock.acquire(False):
        # V2.6.90(3): 跳过日志带上"已运行多少秒"。
        #   旧版只有一句"已在运行", 而实测同一句话可能对应 42 秒正常收尾, 也可能对应
        #   323 秒还没结束(2026-10-19 22:43:12 发起 -> 22:48:35 仍在跑)。两种情形在日志里
        #   长得一模一样, 人无法判断是该等还是该重启, 等于把判断成本转嫁给运维。
        try:
            _age = time.time() - float(SENT_STATE.get('fetch_start_ts') or 0.0)
        except Exception:
            _age = 0.0
        if _age < 0:
            _age = 0.0
        if _lock is None:
            # 锁对象本身创建失败(极罕见): 与"有线程在跑"是两回事, 不能混在一句话里
            _sent_wlog('情绪取数锁不可用(无法并发保护), 本轮跳过(中性, 不阻塞交易)')
        else:
            _txt = ('情绪取数线程已在运行(已运行%d秒), 本轮跳过(中性, 不阻塞交易)'
                    % int(_age))
            if _age > 360.0:
                # 预算 180 秒的 2 倍: 连"慢"都解释不了了, 必须明说是卡死
                _txt += (' —— 已超过取数总预算(180秒)的2倍, 疑似卡死; '
                         '情绪模块将全天中性, 建议重启策略(重启不影响持仓与状态文件)')
            _sent_wlog(_txt)
        return None
"""
rep(A1_OLD, A1_NEW, 'A1 跳过日志带时长')

# ---------------------------------------------------------------- A2 记录开始时刻
A2_OLD = """        SENT_STATE['fetching'] = True   # V2.6.87(4): 供启动横幅区分"取数中"与"未发起"
"""
A2_NEW = """        SENT_STATE['fetching'] = True   # V2.6.87(4): 供启动横幅区分"取数中"与"未发起"
        # V2.6.90(3): 本轮取数起点, 供下轮"跳过"分支算已运行时长; 仅运行时字典, 不落盘
        SENT_STATE['fetch_start_ts'] = time.time()
"""
rep(A2_OLD, A2_NEW, 'A2 记录取数起点')

# ---------------------------------------------------------------- B1 预算起点
B1_OLD = """def _sent_fetch_sync():
    # V2.6.76(第十二轮审计问题2): 后台线程专用取数实现 —— 本函数即原 sent_fetch_all_data 的
    #   取数主体, 逻辑一行未改, 仅改由后台守护线程调用, 主线程绝不直接调用。
    C = getattr(G, 'C', None)
"""
B1_NEW = """def _sent_fetch_sync():
    # V2.6.76(第十二轮审计问题2): 后台线程专用取数实现 —— 本函数即原 sent_fetch_all_data 的
    #   取数主体, 逻辑一行未改, 仅改由后台守护线程调用, 主线程绝不直接调用。
    # V2.6.90(1): 取数总预算起点。旧版只有预下载那 5 秒有预算, 主循环(拆批重试 x 2 轮,
    #   最坏 576 次接口调用)完全没有上限 —— 接口越不可用, 重试越多, 单轮可达十分钟。
    #   注意: 预算值刻意写成函数内局部常量, 不放模块级 —— _fp_keys() 会用 globals() 收集
    #   全部 UPPER_CASE 常量, 新增一个模块级常量就会改变参数指纹, 使 verified_fp 比对失效。
    _t_beg = time.time()
    _BUDGET_SEC = 180.0
    C = getattr(G, 'C', None)
"""
rep(B1_OLD, B1_NEW, 'B1 预算起点')

# ---------------------------------------------------------------- B2 熔断/预算标志
B2_OLD = """        _cov = {'req': len(_stocks), 'ok': 0, 'fail': 0, 'retry': 0,
                'ratio': None, 'samples': [], 'fields_all': False}
        for _attempt in (0, 1):   # 第2轮改用全字段(兼容个别客户端不认preClose字段名)
            _stats = {}
            _box = [0, 0, 0, []]        # [成功只数, 失败只数, 拆分重试次数, 失败样本]
            for _i in range(0, len(_stocks), 300):
                _batch = _stocks[_i:_i + 300]
                _md = _sent_fetch_md_batch(C, _batch, _fields, _start, _cnt, _box, 0)
                for _s, _raw in _md.items():
"""
B2_NEW = """        _cov = {'req': len(_stocks), 'ok': 0, 'fail': 0, 'retry': 0,
                'ratio': None, 'samples': [], 'fields_all': False}
        _abort = False          # V2.6.90(2): 接口整体不可用 -> 已触发熔断
        _budget_hit = False     # V2.6.90(1): 已耗尽总预算, 带已取到的部分收尾
        for _attempt in (0, 1):   # 第2轮改用全字段(兼容个别客户端不认preClose字段名)
            _stats = {}
            _box = [0, 0, 0, []]        # [成功只数, 失败只数, 拆分重试次数, 失败样本]
            _fail_streak = 0            # V2.6.90(2): 连续"整批零成功"的批次数
            for _i in range(0, len(_stocks), 300):
                if time.time() - _t_beg >= _BUDGET_SEC:
                    _budget_hit = True
                    break
                _batch = _stocks[_i:_i + 300]
                _ok_before = _box[0]
                _md = _sent_fetch_md_batch(C, _batch, _fields, _start, _cnt, _box, 0)
                if _box[0] > _ok_before:
                    _fail_streak = 0
                else:
                    _fail_streak += 1
                for _s, _raw in _md.items():
"""
rep(B2_OLD, B2_NEW, 'B2 熔断/预算标志')

# ---------------------------------------------------------------- B3 熔断判定与收尾
B3_OLD = """                        if _pct >= _th:
                            _st[2] += 1
            if _stats:
                _cov['ok'], _cov['fail'], _cov['retry'] = _box[0], _box[1], _box[2]
                _cov['samples'] = _box[3]
                _cov['fields_all'] = not _fields
                break
            if _attempt == 0:
                _sent_wlog('close/preClose字段取数为空, 改用全字段重试(兼容个别客户端)')
                _fields = []
"""
B3_NEW = """                        if _pct >= _th:
                            _st[2] += 1
                # V2.6.90(2): 整体不可用熔断。
                #   旧版无论接口是否整体挂掉都照常拆批: 每批 300 只失败 -> 拆 3 个 100 ->
                #   每个 100 再拆 4 个 30 = 单批最多 16 次调用, 18 批 x 2 轮 = 最坏 576 次。
                #   接口越坏, 重试越多, 于是"快速失败"被放大成十分钟空转, 而日志里只有一堆
                #   第N批失败。判据用"连续3批整批零成功 且 累计一只都没拿到" —— 只要中途
                #   有任何一批成功过就说明接口是活的, 走正常的覆盖率判定, 不提前放弃。
                if _fail_streak >= 3 and _box[0] == 0:
                    _abort = True
                    break
            _cov_new = {'ok': _box[0], 'fail': _box[1], 'retry': _box[2],
                        'samples': list(_box[3]), 'fields_all': not _fields}
            if _stats:
                _cov.update(_cov_new)
                break
            if _abort or _budget_hit or _attempt == 1:
                # 零成功收尾: 失败/重试数必须留下, 否则日志会出现"失败0只"却"覆盖率0%"
                #   这种自相矛盾的组合(旧版两轮皆空时不写 _cov, 保留初始值 0)
                _cov.update(_cov_new)
                break
            if _attempt == 0:
                _sent_wlog('close/preClose字段取数为空, 改用全字段重试(兼容个别客户端)')
                _fields = []
"""
rep(B3_OLD, B3_NEW, 'B3 熔断判定与收尾')

# ---------------------------------------------------------------- B4 熔断/预算日志
B4_OLD = """        _cov['ratio'] = (float(_cov['ok']) / float(_cov['req'])) if _cov['req'] > 0 else 0.0
        SENT_STATE['cover'] = _cov
        if not _stats:
            _sent_wlog('全市场行情为空(内置接口), 情绪数据跳过(中性)')
"""
B4_NEW = """        _cov['ratio'] = (float(_cov['ok']) / float(_cov['req'])) if _cov['req'] > 0 else 0.0
        SENT_STATE['cover'] = _cov
        if _abort:
            _sent_wlog('[告警] 连续3批全部失败且无一成功, 判定行情接口整体不可用: 已中止后续'
                       '拆批重试与第二轮全字段重试(请求%d只/成功%d只) —— 本轮结果不采用, '
                       '上游将沿用上次成功信号; 请检查QMT行情接口/登录状态/是否多实例争用'
                       % (int(_cov['req']), int(_cov['ok'])))
        if _budget_hit:
            _sent_wlog('[告警] 情绪取数触发总预算(%d秒): 已取到%d只/请求%d只即中止, 余下%d只'
                       '本轮放弃 —— 正常应40秒内完成, 明显超时说明接口异常或拆批被放大'
                       % (int(_BUDGET_SEC), int(_cov['ok']), int(_cov['req']),
                          max(0, int(_cov['req']) - int(_cov['ok']))))
        if not _stats:
            _sent_wlog('全市场行情为空(内置接口), 情绪数据跳过(中性)')
"""
rep(B4_OLD, B4_NEW, 'B4 熔断/预算日志')

out = t.replace('\n', '\r\n').encode('gbk')
open(P, 'wb').write(out)
print('补丁完成: %d 处, 字节 %d' % (n_edit, len(out)))
