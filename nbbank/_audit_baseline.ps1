$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Output "=== pwsh version ==="
$PSVersionTable.PSVersion.ToString()

$f = "E:\桌面\666666\nbbank\gf_qmt_native_multi_gbk.py"
$dir = "E:\桌面\666666\nbbank"

Write-Output "=== target file ==="
$fi = Get-Item -LiteralPath $f
Write-Output ("FullName=" + $fi.FullName)
Write-Output ("Length=" + $fi.Length)
Write-Output ("LastWriteTime=" + $fi.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
Write-Output ("SHA256=" + (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash)

$bytes = [System.IO.File]::ReadAllBytes($f)
$hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
Write-Output ("BOM=" + $hasBom)
$nCrlf = 0
for ($i = 0; $i -lt $bytes.Length - 1; $i++) { if ($bytes[$i] -eq 13 -and $bytes[$i+1] -eq 10) { $nCrlf++ } }
Write-Output ("CRLF_count=" + $nCrlf)

$enc = [System.Text.Encoding]::GetEncoding(936)
$text = $enc.GetString($bytes)
$lines = $text -split "`r`n"
Write-Output ("lines=" + $lines.Count)

Write-Output "=== first 24 lines (GBK decoded) ==="
0..23 | ForEach-Object { Write-Output ("{0,4}: {1}" -f ($_ + 1), $lines[$_]) }

Write-Output "=== dir listing ==="
Get-ChildItem -LiteralPath $dir -File | Sort-Object Name | ForEach-Object {
    Write-Output ($_.Name + "  " + $_.Length + "  " + $_.LastWriteTime.ToString("yyyy-MM-dd HH:mm"))
}

Write-Output "=== backup ==="
$bak = $f + ".bak_20261021_v1243"
Copy-Item -LiteralPath $f -Destination $bak -Force
Write-Output ("backup=" + $bak)
Write-Output ("backup_size=" + (Get-Item -LiteralPath $bak).Length)