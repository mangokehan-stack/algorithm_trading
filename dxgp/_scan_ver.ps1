$ErrorActionPreference = 'Stop'
Write-Output ("pwsh 版本: " + $PSVersionTable.PSVersion.ToString())
Write-Output ("pwsh 路径: " + (Get-Process -Id $PID).Path)
