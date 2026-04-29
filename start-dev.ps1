$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$runtimeDir = Join-Path $root ".runtime"
$logDir = Join-Path $runtimeDir "logs"
$pidFile = Join-Path $runtimeDir "pids.json"
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$pythonPath = Join-Path $root ".deps"
$frontendEntry = Join-Path $frontendDir "node_modules"

function Ensure-Directory {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Test-PortOpen {
    param(
        [string]$HostName,
        [int]$Port
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(500)
        if (-not $connected) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

if (-not (Test-Path $pythonExe)) {
    throw "Missing Python environment at $pythonExe"
}

if (-not (Test-Path $frontendEntry)) {
    throw "Frontend dependencies are missing. Run 'cd frontend; npm install' once first."
}

if (-not (Test-PortOpen -HostName "127.0.0.1" -Port 6379)) {
    throw "Redis is not reachable on 127.0.0.1:6379. Start Redis before launching the stack."
}

Ensure-Directory -Path $runtimeDir
Ensure-Directory -Path $logDir

if (Test-Path $pidFile) {
    throw "Existing runtime state found at $pidFile. Run .\stop-dev.ps1 first if the stack is already running."
}

$envBlock = @{
    PYTHONPATH = $pythonPath
    CELERY_BROKER_URL = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
}

foreach ($entry in $envBlock.GetEnumerator()) {
    [System.Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
}

& $pythonExe manage.py migrate | Tee-Object -FilePath (Join-Path $logDir "migrate.log")

$serverLog = Join-Path $logDir "backend.log"
$workerLog = Join-Path $logDir "celery.log"
$frontendLog = Join-Path $logDir "frontend.log"

$backendProcess = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList "manage.py", "runserver", "127.0.0.1:8000" `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $serverLog `
    -RedirectStandardError $serverLog `
    -PassThru `
    -WindowStyle Hidden

$workerProcess = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList "-m", "celery", "-A", "config", "worker", "-l", "info" `
    -WorkingDirectory $backendDir `
    -RedirectStandardOutput $workerLog `
    -RedirectStandardError $workerLog `
    -PassThru `
    -WindowStyle Hidden

$frontendProcess = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "--host", "127.0.0.1" `
    -WorkingDirectory $frontendDir `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendLog `
    -PassThru `
    -WindowStyle Hidden

$state = @{
    backend_pid = $backendProcess.Id
    celery_pid = $workerProcess.Id
    frontend_pid = $frontendProcess.Id
}

$state | ConvertTo-Json | Set-Content -Path $pidFile

Write-Host "PlayTo stack started."
Write-Host "Frontend: http://127.0.0.1:5173"
Write-Host "Backend API: http://127.0.0.1:8000/api/v1/merchants"
Write-Host "Logs: $logDir"
Write-Host "Stop with: .\stop-dev.ps1"
