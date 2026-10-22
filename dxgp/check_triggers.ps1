$ps = Get-Command New-ScheduledTaskTrigger
foreach ($set in $ps.ParameterSets) {
    $name = $set.Name
    $params = $set.Parameters | ForEach-Object { $_.Name }
    Write-Host "$name : $params"
}
