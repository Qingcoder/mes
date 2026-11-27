# 双击 .md 由「MD阅读器.html」打开的启动器（隐藏运行）
# 由注册表关联调用：powershell -File md打开器.ps1 "<md路径>"
param([Parameter(Mandatory=$true)][string]$Path)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$tpl  = Join-Path $root 'MD阅读器.html'
if (-not (Test-Path -LiteralPath $tpl)) { exit 1 }

$resolved = (Resolve-Path -LiteralPath $Path).Path
$text = [System.IO.File]::ReadAllText($resolved, [System.Text.Encoding]::UTF8)
$name = [System.IO.Path]::GetFileName($resolved)

function B64([string]$s) {
  [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($s))
}

$payload = 'window.__MD_PRELOAD__={n:"' + (B64 $name) + '",b:"' + (B64 $text) + '"};'
$html = [System.IO.File]::ReadAllText($tpl, [System.Text.Encoding]::UTF8)
$html = $html.Replace('window.__MD_PRELOAD__=null;', $payload)

$dir = Join-Path $env:TEMP 'daimon-md'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$hash = (Get-FileHash -LiteralPath $resolved -Algorithm MD5).Hash.Substring(0, 10)
$out  = Join-Path $dir ($hash + '.html')
[System.IO.File]::WriteAllText($out, $html, (New-Object System.Text.UTF8Encoding($false)))

Start-Process $out
