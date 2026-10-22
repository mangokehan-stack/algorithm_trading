Set-Location "E:\桌面\666666\dxgp"
Write-Output ("CWD: " + (Get-Location).Path)
Write-Output "--- top-level non-underscore files (sorted by LastWriteTime desc) ---"
Get-ChildItem -File | Where-Object { $_.Name -notlike '_*' -and $_.Name -notlike '.*' } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 60 |
    ForEach-Object {
        [PSCustomObject]@{
            Name = $_.Name
            Len  = $_.Length
            MTime = $_.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        }
    } | Format-Table -AutoSize -Wrap | Out-String -Width 240 | Write-Output
