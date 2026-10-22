$ErrorActionPreference = 'Stop'
$root = 'E:\桌面\666666\dxgp'
Write-Output "================ 目录全貌扫描 ================"
Write-Output ("根目录: " + $root)
Write-Output ""

# 受保护目录(系统规则, 禁止删除/清理)
$protected = @('.workbuddy')

# 顶层条目
Write-Output "---------- 顶层条目 ----------"
$top = Get-ChildItem -LiteralPath $root -Force | Sort-Object PSIsContainer, Name
foreach ($t in $top) {
    if ($t.PSIsContainer) {
        $n = (Get-ChildItem -LiteralPath $t.FullName -Recurse -File -Force -ErrorAction SilentlyContinue).Count
        $sz = (Get-ChildItem -LiteralPath $t.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        Write-Output ("  [目录] {0,-34} 含文件 {1,4} 个  合计 {2,10:N0} bytes" -f $t.Name, $n, $sz)
    } else {
        Write-Output ("  [文件] {0,-34} {1,10:N0} bytes  {2}" -f $t.Name, $t.Length, $t.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))
    }
}
Write-Output ""

# 全部文件(排除受保护目录)
Write-Output "---------- 全部文件明细(排除 .workbuddy) ----------"
$files = Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '\\\.workbuddy\\' } |
    Sort-Object FullName
Write-Output ("  文件总数: " + $files.Count)
Write-Output ("  磁盘合计: {0:N0} bytes ({1:N2} MB)" -f (($files | Measure-Object -Property Length -Sum).Sum), ((($files | Measure-Object -Property Length -Sum).Sum)/1MB))
Write-Output ""
foreach ($f in $files) {
    $rel = $f.FullName.Substring($root.Length + 1)
    $dir = Split-Path $rel -Parent
    if ($dir -eq '') { $dir = '(根目录)' }
    Write-Output ("  {0,-14} {1,10:N0}  {2}  {3}" -f $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm'), $f.Length, $dir, $f.Name)
}
Write-Output ""

# 受保护目录内容(仅列名, 不动)
Write-Output "---------- .workbuddy(系统数据, 禁止删除, 仅列名) ----------"
foreach ($p in $protected) {
    $pp = Join-Path $root $p
    if (Test-Path -LiteralPath $pp) {
        Get-ChildItem -LiteralPath $pp -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
            $rel = $_.FullName.Substring($root.Length + 1)
            if ($_.PSIsContainer) { Write-Output ("  [目录] " + $rel) } else { Write-Output ("  [文件] {0,-60} {1,10:N0}" -f $rel, $_.Length) }
        }
    }
}
Write-Output ""

# 备份目录专项
Write-Output "---------- _baseline 备份点明细 ----------"
$bl = Join-Path $root '_baseline'
if (Test-Path -LiteralPath $bl) {
    Get-ChildItem -LiteralPath $bl -File -Force | Sort-Object Name | ForEach-Object {
        Write-Output ("  {0,-34} {1,10:N0} bytes  {2}" -f $_.Name, $_.Length, $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))
    }
}
