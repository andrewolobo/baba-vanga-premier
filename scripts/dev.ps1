<#
.SYNOPSIS
    One command for the whole local stack: cycle once, then API and frontend.

.DESCRIPTION
    Runs the three pieces of docs/RUNBOOK.md sec 0.1 in one shell instead of three.

        1. the cycle   -- via run_cycle.ps1, ONCE, then it exits
        2. the API     -- uvicorn on $ApiPort
        3. the web app -- vite dev on $WebPort

    **Scheduling still lives outside the application.** This runs the cycle a
    single time at startup and then leaves it alone; recurring runs remain the
    Task Scheduler's job (sec 2). That is deliberate -- services/run_cycle.py
    argues a process that supervises itself has two ways to be wrong, and there
    is no lock file to make overlapping runs safe (sec 8).

    The cycle is run first and to completion, never alongside the servers.
    Since WAL it no longer has to be (sec 5.6) -- but a cycle that finishes
    before the API binds is one whose exit code you actually read, instead of
    losing it in a console filling with request logs.

    A non-zero cycle exit is reported but does not stop the servers -- empty
    pages are a documented, correct state (sec 0.1), and being unable to see them
    is worse than seeing them empty.

    Ctrl-C stops everything. Both servers share this console, so their output
    interleaves; that is the price of one window.

.PARAMETER SkipCycle
    Start the servers only. For when the cycle already ran this session.

.EXAMPLE
    .\scripts\dev.ps1
    .\scripts\dev.ps1 -SkipCycle
#>
[CmdletBinding()]
param(
    [switch]$SkipCycle,
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)

$ErrorActionPreference = 'Continue'   # match run_cycle.ps1; failures are reported, not thrown

$repo = Resolve-Path "$PSScriptRoot\.."

# --- preflight -------------------------------------------------------------
# Each of these is a failure that otherwise surfaces as an unrelated traceback
# several seconds later, once two other processes are already running.

& python -c "import fastapi, uvicorn" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "The API's dependencies are an extra, not a base dependency:" -ForegroundColor Red
    Write-Host '    pip install -e ".[serve]"'
    exit 1
}

if (-not (Test-Path "$repo\web\node_modules")) {
    Write-Host "web/node_modules is missing:" -ForegroundColor Red
    Write-Host "    cd web; npm install"
    exit 1
}

foreach ($port in @($ApiPort, $WebPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "Port $port is already in use -- is the stack already running?" -ForegroundColor Red
        exit 1
    }
}

# --- 1. the cycle ----------------------------------------------------------
# Delegated to run_cycle.ps1 rather than reimplemented, so a run started this
# way lands in the same dated log as a scheduled one.

if (-not $SkipCycle) {
    & "$PSScriptRoot\run_cycle.ps1"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Cycle exit $LASTEXITCODE -- starting the servers anyway; see the log." `
            -ForegroundColor Yellow
    }
}

# --- 2 and 3. the servers --------------------------------------------------

# No --reload: uvicorn's reloader watches the working directory, and the cycle
# writes db/premier.db inside it. Reloading on your own database is a loop.
$api = Start-Process -FilePath "python" `
    -ArgumentList @('-m', 'uvicorn', 'api.main:app', '--port', $ApiPort) `
    -WorkingDirectory $repo -NoNewWindow -PassThru

# vite proxies /api to the API, and until now had the port hardcoded at 8000 --
# so -ApiPort started uvicorn somewhere else and left the frontend proxying to a
# dead port, which reads as an empty week rather than as a broken stack.
# Start-Process inherits this process's environment, so setting it here is enough.
$env:BVP_API_PORT = $ApiPort

$web = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @('run', 'dev', '--', '--port', $WebPort) `
    -WorkingDirectory "$repo\web" -NoNewWindow -PassThru

Write-Host ""
Write-Host "  app  http://localhost:$WebPort   <- use localhost, not 127.0.0.1 (see RUNBOOK)"
Write-Host "  api  http://127.0.0.1:$ApiPort/health"
Write-Host "  Ctrl-C to stop both."
Write-Host ""

try {
    # If one server dies, stop the other: half a stack looks like a working one
    # right up until the page is blank for a reason nobody can see.
    while ($true) {
        if ($api.HasExited) { Write-Host "API exited ($($api.ExitCode))." -ForegroundColor Yellow; break }
        if ($web.HasExited) { Write-Host "Frontend exited ($($web.ExitCode))." -ForegroundColor Yellow; break }
        Start-Sleep -Seconds 1
    }
}
finally {
    # taskkill /T, not Stop-Process: npm.cmd and uvicorn each spawn children
    # that outlive their parent and keep the port bound.
    foreach ($proc in @($api, $web)) {
        if ($proc -and -not $proc.HasExited) {
            & taskkill.exe /PID $proc.Id /T /F 2>&1 | Out-Null
        }
    }
    Write-Host "Stopped."
}
