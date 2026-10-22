# 更新现有任务, 添加每日触发器
$py = 'C:\Program Files\Python311\python.exe'
$script = 'C:\广发证券QMT量化交易系统 - 交易端\bin.x64\download_risk_exclude.py'
$workDir = 'C:\广发证券QMT量化交易系统 - 交易端\bin.x64'
$log = "$workDir\zt_shrink_risk_exclude_update.log"

# 触发器1: 开机启动
$trig1 = New-ScheduledTaskTrigger -AtStartup

# 触发器2: 每天08:00
$trig2 = New-ScheduledTaskTrigger -Daily -At 08:00

# 获取现有任务的 Action 和 Settings
$task = Get-ScheduledTask -TaskName 'ZTShrink-RiskExclude'
$action = $task.Actions[0]
$settings = $task.Settings

# 更新任务
Set-ScheduledTask -TaskName 'ZTShrink-RiskExclude' -Trigger $trig1, $trig2 -Force

Write-Host '=== 任务已更新: 开机 + 每日08:00 ==='
Get-ScheduledTask -TaskName 'ZTShrink-RiskExclude' | Format-List Name, State
Get-ScheduledTaskInfo -TaskName 'ZTShrink-RiskExclude' | Format-List NextRunTime
