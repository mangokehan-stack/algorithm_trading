# -*- coding: utf-8 -*-
"""V2.6.91 三项补丁

1) 世代标记: 防"跨脚本重载的孤儿取数线程"两代并行取数(22:55:42~23:17:04 实测 21分22秒)
2) 取数"完成"行带耗时: 旧版只能靠两头时间戳手算, 日志自己看不出异常
3) 心跳节拍修正: 实测 60 秒一拍(设计 30 秒), 分档阈值按错误节拍算过

严格约束: 不新增任何模块级大写常量 —— _fp_keys() 用 globals() 收集全部
UPPER_CASE 常量, 新增一个就会改变参数指纹, 让 verified_fp 无端失效。
世代文件名的前缀以字面量写在函数里, 不新增常量。
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


# ---------------------------------------------------------------- A 心跳节拍
A_OLD = """        if not force and (_now - _HB_STATE['last_ts']) < HEARTBEAT_SEC:
            return
"""
A_NEW = """        # V2.6.91(3): 节流阈值从 HEARTBEAT_SEC 降到 HEARTBEAT_SEC*0.8。
        #   实测(2026-10-19 23:18:14 -> 23:19:14 -> 23:20:14)心跳文件是 60 秒才落一拍,
        #   不是设计的 30 秒: timer_poll 每 30 秒回调一次, 而 _now - last_ts 恰好也在 30.0
        #   附近, 比较用 >=HEARTBEAT_SEC 时只要差一点点(<30.000)就被 return 掉, 于是每两轮
        #   才写一次。后果不只是"心跳看起来慢": V2.6.89 把"算不算真活着"的分档阈值定成
        #   HEARTBEAT_SEC*1.5=45 秒, 按 60 秒节拍只覆盖 0.75 个周期 —— 真出现双实例时约有
        #   1/4~1/2 的时间会被降级成"[提示]"而不是"[告警]", 等于把最该喊的那一下喊轻了。
        #   乘以 0.8(24 秒)让每次回调都能过闸, 节拍回到 30 秒; 阈值仍由 HEARTBEAT_SEC 派生,
        #   不新增大写常量, 参数指纹不受影响。
        if not force and (_now - _HB_STATE['last_ts']) < (HEARTBEAT_SEC * 0.8):
            return
"""
rep(A_OLD, A_NEW, 'A 心跳节流阈值')


# ---------------------------------------------------------------- B 世代标记函数
B_OLD = """    stem, ext = _split_name(HEARTBEAT_FILE)
    return _join_base('%s%s_%d%s' % (stem, _account_suffix(), _pid, ext))


def heartbeat_tick(force=False):
"""
B_NEW = """    stem, ext = _split_name(HEARTBEAT_FILE)
    return _join_base('%s%s_%d%s' % (stem, _account_suffix(), _pid, ext))


# V2.6.91(1): 世代标记 —— 防"跨脚本重载的孤儿取数线程"
#   实测(2026-10-19): QMT 里点停止/重新启动并不会杀掉已经创建的 threading.Thread。
#   旧代脚本的取数线程带着旧代全局变量继续跑: 22:55:42 发起, 23:17:04 才结束,
#   整整 21 分 22 秒; 而新代(23:16:43 启动, PID 仍是 37300)在 23:17:11 又发起一次
#   全量取数 —— 两代同时打同一个行情接口。这正是"18 批里 14 批失败""覆盖率只有 23%"
#   的物理原因(旧版日志里看不出半点痕迹), 也是接口被自己拖慢的主因。
#   更麻烦的是旧代线程跑完还会写 SENT_STATE 并打一行"取数完成", 让人误以为那是新代的结果。
#   做法: 每代启动时写一份世代文件(原子替换), 取数线程每批开始前比对一次;
#   发现文件里的 gen 比自己新、且那一代心跳仍在跳 -> 立即退出, 不写任何结果。
_GEN_STATE = {'id': 0.0, 'path': ''}


def gen_path():
    \"\"\"V2.6.91(1): 世代文件路径。只按账号后缀隔离, 刻意不带 PID ——
    跨脚本重载时 QMT 复用同一个 OS 进程, PID 不变, 带 PID 反而会让两代写同一个文件、
    谁都分辨不出先后; 按账号写同一份、用文件里的 gen 时间戳比新旧即可。\"\"\"
    return _join_base('zt_shrink_gen' + _account_suffix() + '.json')


def gen_announce():
    \"\"\"V2.6.91(1): 宣告本代进程(启动时调用一次)。失败不阻断取数, 但要说出原因。\"\"\"
    try:
        _t = time.time()
        _p = gen_path()
        _tmp = _p + '.tmp'
        with open(_tmp, 'w', encoding='utf-8') as _fh:
            json.dump({'gen': _t, 'pid': os.getpid(), 'ts': _t, 'ver': VERSION},
                      _fh, ensure_ascii=True)
        os.replace(_tmp, _p)
        _GEN_STATE['id'] = _t
        _GEN_STATE['path'] = _p
        return _t
    except Exception as _e:
        _GEN_STATE['id'] = 0.0
        _GEN_STATE['path'] = ''
        log('[安全][提示] 世代标记写入失败(跨重载的旧代取数线程将无法自愈): %s'
            % _exc_text(_e))
        return 0.0


def _gen_superseded():
    \"\"\"V2.6.91(1): 本线程是否属旧代残留(已有更新的一代在运行)。

    三个条件同时满足才算"被取代", 缺一不可:
      1) 本代成功宣告过(gen>0), 否则无从比较, 一律放行;
      2) 世代文件里的 gen 严格大于本代;
      3) 那一代的 PID 心跳仍在 HEARTBEAT_STALE_SEC 内 —— 少了这条, 一次"新代启动又退出"
         或上一次运行留下的旧文件就会永久压制本代, 情绪整天取不到数。
    任何异常一律返回 False(按无法判定处理), 宁可两代并行也不能让取数停摆。
    \"\"\"
    try:
        _mine = _f(_GEN_STATE.get('id') or 0.0)
        if _mine <= 0:
            return False
        _p = _GEN_STATE.get('path') or gen_path()
        with open(_p, 'r', encoding='utf-8') as _fh:
            _d = json.load(_fh)
        if not isinstance(_d, dict):
            return False
        _g = _f(_d.get('gen') or 0.0)
        if _g <= _mine + 1e-6:
            return False
        _gp = int(_f(_d.get('pid') or 0))
        _stem, _ext = _split_name(HEARTBEAT_FILE)
        _hp = _join_base('%s%s_%d%s' % (_stem, _account_suffix(), _gp, _ext))
        with open(_hp, 'r', encoding='utf-8') as _fh:
            _hd = json.load(_fh)
        return (time.time() - _f(_hd.get('ts') or 0.0)) <= HEARTBEAT_STALE_SEC
    except Exception:
        return False


def heartbeat_tick(force=False):
"""
rep(B_OLD, B_NEW, 'B 世代标记函数')


# ---------------------------------------------------------------- C 启动宣告
C_OLD = """    log('after_init: 初始化阶段结束')
    heartbeat_tick(force=True)   # V2.6.87(5): 启动即检测, 双实例不必等到首轮定时器
"""
C_NEW = """    log('after_init: 初始化阶段结束')
    # V2.6.91(1): 先宣告本代(世代文件), 再打心跳 —— 取数线程要能同时看到"谁是最新一代"
    #   和"那一代是否还活着"。老客户端不调用 after_init 时两件事都不做, 取数退化为旧行为, 无副作用。
    gen_announce()
    heartbeat_tick(force=True)   # V2.6.87(5): 启动即检测, 双实例不必等到首轮定时器
"""
rep(C_OLD, C_NEW, 'C 启动宣告世代')


# ---------------------------------------------------------------- D 取数入口自检
D_OLD = """    _t_beg = time.time()
    _BUDGET_SEC = 180.0
    C = getattr(G, 'C', None)
"""
D_NEW = """    _t_beg = time.time()
    _BUDGET_SEC = 180.0
    # V2.6.91(1): 进函数先判一次世代 —— 最常见的情形是"旧代线程刚被重载抛下就轮到它取数",
    #   此时连股票列表都不该去拉(列表本身也是一次全市场接口调用)。
    if _gen_superseded():
        _sent_wlog('[提示] 检测到更新的一代策略进程在运行, 本线程属旧代残留: '
                   '已自行退出取数(不写结果, 不覆盖状态)')
        return None
    C = getattr(G, 'C', None)
"""
rep(D_OLD, D_NEW, 'D 取数入口世代自检')


# ---------------------------------------------------------------- E 每批前自检
E_OLD = """            for _i in range(0, len(_stocks), 300):
                if time.time() - _t_beg >= _BUDGET_SEC:
                    _budget_hit = True
                    break
"""
E_NEW = """            for _i in range(0, len(_stocks), 300):
                # V2.6.91(1): 每批前再判一次世代。单批最坏 16 次接口调用, 不逐批检查的话
                #   旧代线程可能抱着半份数据再跑好几分钟, 白白和新代抢接口。
                if _gen_superseded():
                    _sent_wlog('[提示] 取数中途发现更新的一代策略进程已接管: 本线程属旧代残留, '
                               '提前退出(不写结果, 不覆盖状态)')
                    return None
                if time.time() - _t_beg >= _BUDGET_SEC:
                    _budget_hit = True
                    break
"""
rep(E_OLD, E_NEW, 'E 每批前世代自检')


# ---------------------------------------------------------------- F 完成行带耗时
F_OLD = """        _sent_wlog('内置通道取数完成: 请求%d只 成功%d只(覆盖率%.1f%%) 失败%d只 拆分重试%d次 '
                   '字段=%s | 预下载%d只 覆盖日期%d天 窗口起点%s'
                   % (_cov['req'], _cov['ok'], _ratio_pct, _cov['fail'], _cov['retry'],
                      '全字段' if _cov['fields_all'] else 'close/preClose',
                      _prefetched, len(rows), _start))
"""
F_NEW = """        # V2.6.91(2): 带耗时。旧版只有"请求/成功/失败/重试", 单看这行分不出 17 秒还是
        #   21 分钟 —— 2026-10-19 那次孤儿线程跑了 21 分 22 秒, 是靠"22:55:42 发起、
        #   23:17:04 完成"两头时间戳手算出来的, 日志本身看不出异常。
        _elapsed = time.time() - _t_beg
        _sent_wlog('内置通道取数完成: 请求%d只 成功%d只(覆盖率%.1f%%) 失败%d只 拆分重试%d次 '
                   '耗时%.0f秒 字段=%s | 预下载%d只 覆盖日期%d天 窗口起点%s'
                   % (_cov['req'], _cov['ok'], _ratio_pct, _cov['fail'], _cov['retry'],
                      _elapsed,
                      '全字段' if _cov['fields_all'] else 'close/preClose',
                      _prefetched, len(rows), _start))
"""
rep(F_OLD, F_NEW, 'F 完成行带耗时')


out = t.replace('\n', '\r\n').encode('gbk')
open(P, 'wb').write(out)
print('补丁完成: %d 处, 字节 %d' % (n_edit, len(out)))
