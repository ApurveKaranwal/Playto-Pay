$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $root ".runtime"
$pidFile = Join-Path $runtimeDir "pids.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "No running PlayTo stack found."
    exit 0
}

$state = Get-Content -Raw $pidFile | ConvertFrom-Json
$pids = @($state.backend_pid, $state.celery_pid, $state.frontend_pid) | Where-Object { $_ }

foreach ($pid in $pids) {
    $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $pid -Force
    }
}

Remove-Item -LiteralPath $pidFile -Force
Write-Host "PlayTo stack stopped."
