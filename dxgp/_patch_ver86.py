# -*- coding: utf-8 -*-
"""V2.6.86: 仅文档更正 —— 修正 V2.6.85 版本记录里写错的参数指纹数字。

背景: V2.6.85 记录中"实测 V2.6.83/V2.6.84/当前 三版恒定 94d5c464"是错的。
94d5c464 来自开发机 _verify_fp.py 的 AST 近似法(只抓单目标字面量赋值),
而母版 _fp_keys() 抓的是 globals() 里全部 UPPER_CASE 常量(255 个), 口径不同,
故与 QMT 运行时实际打印的 392cbf3a 不符。

本次只改: 文件头版本记录(V2.6.85 那行的错误数字) + 顶部新增 V2.6.86 记录行
        + VERSION 常量。代码、参数、日志输出一律不动。
"""
import io
import re
import sys

P = 'zt_shrink_strategy_gbk.py'

old_frag = ('(VERSION 进 _FP_DENY, 供 verified_fp 比对, 实测 '
            'V2.6.83/V2.6.84/当前 三版恒定 94d5c464)')
new_frag = ('(VERSION 进 _FP_DENY, 供 verified_fp 比对; 运行时实测 V2.6.85=392cbf3a, '
            '升版模拟后不变 —— 注: 旧记录写的 94d5c464 系开发机 AST 近似法口径错误, '
            '详见 V2.6.86 更正)')

REC = (
    '版本号: V2.6.86              修改时间: 2026-10-19 22:26 '
    '(V2.6.86记录: 仅文档更正, 代码零改动 —— 客户端 V2.6.85 实跑日志(22:18:36)复核时发现'
    '版本记录自述与实际输出不符: 记录写"实测 V2.6.83/V2.6.84/当前 三版恒定 94d5c464", '
    '而 QMT 日志实际打印 [参数指纹] 392cbf3a。根因是我方开发机 _verify_fp.py 用 AST 只抓'
    '"单目标字面量赋值"近似复算, 与母版 _fp_keys() 抓 globals() 全量 UPPER_CASE 常量的口径'
    '不一致(前者漏掉多目标赋值/表达式赋值/try 块内赋值, 共 255 个键), 故数值不可比。'
    '现 _verify_fp.py 改为 exec 母版后直接调用 param_fingerprint()/code_fingerprint(), '
    '与 QMT 同一算法、同一 globals(), 复现值 392cbf3a / 8c30a7a2 与客户端日志逐字符一致。'
    '另更正一处表述: V2.6.83/84 的参数指纹 a36ba5ec / 77b9f089 因当时 VERSION 仍参与计算, '
    '与新版不可直接比较, 并非"三版恒定"。本版实测: 参数指纹 392cbf3a(与 V2.6.85 完全相同, '
    '证明注释变更不影响参数指纹), 版本指纹 8c30a7a2->本版新值(证明 VERSION 已从参数指纹剥离)。'
    '除版本记录与 VERSION 常量外, 与 V2.6.85 逐字节一致, 无需为交易目的重新上传。)')


def main():
    raw = open(P, 'rb').read()
    text = raw.decode('gbk')
    lines = text.split('\r\n')

    if not lines[4].startswith('版本号: V2.6.85'):
        print('FAIL: 第5行不是 V2.6.85 记录: %r' % lines[4][:40])
        return 1
    if old_frag not in lines[4]:
        print('FAIL: V2.6.85 记录中未找到待更正片段')
        return 1
    if any(l.startswith('版本号: V2.6.86') for l in lines):
        print('SKIP: V2.6.86 记录已存在')
        return 0

    # 1 更正 V2.6.85 记录里的错误数字
    lines[4] = lines[4].replace(old_frag, new_frag)
    # 2 顶部插入 V2.6.86 记录
    lines.insert(4, REC)
    # 3 VERSION 常量
    hit = 0
    for i, l in enumerate(lines):
        if l.startswith("VERSION = 'V2.6.85'"):
            lines[i] = l.replace("VERSION = 'V2.6.85'", "VERSION = 'V2.6.86'", 1)
            hit += 1
    if hit != 1:
        print('FAIL: VERSION 常量命中 %d 次' % hit)
        return 1

    out = '\r\n'.join(lines)
    open(P, 'wb').write(out.encode('gbk'))
    print('OK 行数 %d, VERSION=V2.6.86, 版本记录行 %d'
          % (len(lines), sum(1 for l in lines if l.startswith('版本号: V'))))
    print('OK MD5 需重算(见体检)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
