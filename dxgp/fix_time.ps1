Unregister-ScheduledTask -TaskName 'ZTShrink-RiskExclude' -Confirm:$false -ErrorAction SilentlyContinue

$py = 'C:\Program Files\Python311\python.exe'
$script = 'C:\广发证券QMT量化交易系统 - 交易端\bin.x64\download_risk_exclude.py'
$workDir = 'C:\广发证券QMT量化交易系统 - 交易端\bin.x64'
$log = "$workDir\zt_shrink_risk_exclude_update.log"

$trig1 = New-ScheduledTaskTrigger -AtStartup
$trig2 = New-ScheduledTaskTrigger -Daily -At 06:00

$argStr = "/c `"$py`" `"$script`" --account 8973786 >> `"$log`" 2>&1"
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $argStr -WorkingDirectory $workDir

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask `
    -TaskName 'ZTShrink-RiskExclude' `
    -Trigger $trig1, $trig2 `
    -Action $action `
    -Settings $settings `
    -Description '涨停缩量策略 - 排雷清单自动更新(开机+每日06:00)' `
    -Force

$info = Get-ScheduledTaskInfo -TaskName 'ZTShrink-RiskExclude'
Write-Host "OK: 下次运行 = $info.NextRunTime"
