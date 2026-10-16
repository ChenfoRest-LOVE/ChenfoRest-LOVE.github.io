[CmdletBinding()]
param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$port = 4180
$url = "http://127.0.0.1:$port"
$scriptPath = Join-Path $PSScriptRoot 'server.py'
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Stop) {
    if ($listener) {
        $managerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
        if ($managerProcess.CommandLine -notlike "*$scriptPath*") { throw '该端口由其他程序使用，未停止它。' }
        Stop-Process -Id $listener.OwningProcess
    }
    Write-Host '封面管理已停止。'
    exit 0
}
if ($listener) {
    $health = Invoke-RestMethod "$url/_manage/health" -TimeoutSec 3
    if ($health.app -ne 'forest-cover-manager') { throw '4180 端口由其他程序使用。' }
    if ($health.version -ge 3) {
        Write-Host "封面管理：$url/photos.html"
        exit 0
    }
    $managerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    if ($managerProcess.CommandLine -notlike "*$scriptPath*") { throw '旧版管理入口由其他程序启动，未停止它。' }
    Stop-Process -Id $listener.OwningProcess
    Start-Sleep -Milliseconds 300
}
$python = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$logDirectory = Join-Path $env:LOCALAPPDATA 'ForestWebsiteManager'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$process = Start-Process -FilePath $python -ArgumentList @('-u', ('"' + $scriptPath + '"'), '--port', "$port") -WorkingDirectory (Split-Path $PSScriptRoot -Parent) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'stdout.log') -RedirectStandardError (Join-Path $logDirectory 'stderr.log')
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 200
    if ($process.HasExited) { throw '管理服务启动失败，请检查本机管理日志。' }
    try {
        $health = Invoke-RestMethod "$url/_manage/health" -TimeoutSec 1
        if ($health.app -eq 'forest-cover-manager') { Write-Host "封面管理：$url/photos.html"; exit 0 }
    } catch { }
}
throw '管理服务没有及时响应，请检查本机管理日志。'
