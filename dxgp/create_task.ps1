# 删除旧任务
Unregister-ScheduledTask -TaskName 'ZTShrink-RiskExclude' -Confirm:$false -ErrorAction SilentlyContinue

# 路径
$py = 'C:\Program Files\Python311\python.exe'
$script = 'C:\广发证券QMT量化交易系统 - 交易端\bin.x64\download_risk_exclude.py'
$workDir = 'C:\广发证券QMT量化交易系统 - 交易端\bin.x64'
$log = "$workDir\zt_shrink_risk_exclude_update.log"

# 触发器1: 开机启动
$trig1 = New-ScheduledTaskTrigger -AtStartup

# 触发器2: 每天08:00
$trig2 = New-ScheduledTaskTrigger -Daily -At 08:00

# 动作
$argStr = "/c `"$py`" `"$script`" --account 8973786 >> `"$log`" 2>&1"
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $argStr -WorkingDirectory $workDir

# 设置
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 注册 (两个触发器)
Register-ScheduledTask `
    -TaskName 'ZTShrink-RiskExclude' `
    -Trigger $trig1, $trig2 `
    -Action $action `
    -Settings $settings `
    -Description '涨停缩量策略 - 排雷清单自动更新(开机+每日08:00)' `
    -Force

Write-Host '=== 完成 ==='
$t = Get-ScheduledTask -TaskName 'ZTShrink-RiskExclude'
Write-Host '任务名: ' $t.TaskName
Write-Host '状态: ' $t.State
Write-Host '触发器数: ' $t.Triggers.Count
foreach ($trig in $t.Triggers) {
    Write-Host '  ' $trig.ToString()
}
Write-Host '下次运行: ' (Get-ScheduledTaskInfo -TaskName 'ZTShrink-RiskExclude').NextRunTime
