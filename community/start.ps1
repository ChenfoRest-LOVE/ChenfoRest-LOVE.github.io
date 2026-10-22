[CmdletBinding()]
param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$port = 4192
$url = "http://127.0.0.1:$port"
$scriptPath = Join-Path $PSScriptRoot 'server.py'
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $previewProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    if ($previewProcess.CommandLine -notlike "*$scriptPath*") { throw '4192 端口由其他程序使用，未停止它。' }
    Stop-Process -Id $listener.OwningProcess
    Start-Sleep -Milliseconds 300
}
if ($Stop) { Write-Host '评论预览已停止，账号与评论数据保留。'; exit 0 }
$python = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$logDirectory = Join-Path $env:LOCALAPPDATA 'ForestComments'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$process = Start-Process -FilePath $python -ArgumentList @('-u', ('"' + $scriptPath + '"'), '--port', "$port") -WorkingDirectory (Split-Path $PSScriptRoot -Parent) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'stdout.log') -RedirectStandardError (Join-Path $logDirectory 'stderr.log')
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 200
    if ($process.HasExited) { throw '评论预览启动失败，请检查本机 ForestComments 日志。' }
    try {
        $health = Invoke-RestMethod "$url/api/community/health" -TimeoutSec 1
        if ($health.app -eq 'forest-comments') { Write-Host "评论预览：$url/writing.html"; exit 0 }
    } catch { }
}
throw '评论预览没有及时响应，请检查本机 ForestComments 日志。'
