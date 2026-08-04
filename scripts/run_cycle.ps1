<#
.SYNOPSIS
    Scheduled entry point for the serving cycle. Logs, then propagates the code.

.DESCRIPTION
    Task Scheduler reports "last run result" and nothing else, so this wrapper
    exists to make a run reconstructable afterwards: every run appends to a
    dated log, and the exit code is passed through unchanged rather than being
    swallowed by PowerShell's default of returning 0 for a completed script.

    Exit codes come from services.run_cycle and mean different things:

        0   clean
        2   ran, but needs a look   (empty feed, unknown club, unbridged name)
        1   a step failed

    Two is not a worse one. A scheduler that treats every non-zero the same
    will page someone at 3am for an out-of-season feed, and they will then stop
    reading the alerts -- which is the failure this whole design is avoiding.

.PARAMETER DryRun
    Write nothing. Used by the pre-launch checklist in docs/RUNBOOK.md.

.PARAMETER Refreeze
    Refit the artifact before serving, regardless of its age.

.EXAMPLE
    .\scripts\run_cycle.ps1
    .\scripts\run_cycle.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Refreeze,
    [string]$LogDir = "$PSScriptRoot\..\logs"
)

$ErrorActionPreference = 'Continue'   # a failing cycle must still be logged

$repo = Resolve-Path "$PSScriptRoot\.."
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$log = Join-Path $LogDir ("cycle-{0}.log" -f (Get-Date -Format 'yyyy-MM-dd'))

$cmdArgs = @('-m', 'services.run_cycle')
if ($DryRun)   { $cmdArgs += '--dry-run' }
if ($Refreeze) { $cmdArgs += '--refreeze' }

"" | Add-Content $log
"=== {0} :: python {1} ===" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), ($cmdArgs -join ' ') |
    Add-Content $log

Push-Location $repo
try {
    # 2>&1 so a traceback lands in the log rather than vanishing into the
    # scheduler's stderr. Tee-Object keeps it visible when run by hand.
    & python @cmdArgs 2>&1 | Tee-Object -FilePath $log -Append
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

$verdict = switch ($code) {
    0       { 'clean' }
    2       { 'ATTENTION -- see the log' }
    1       { 'FAILED -- see the log' }
    default { "unexpected exit code $code" }
}
"--- exit {0} ({1}) ---" -f $code, $verdict | Add-Content $log
Write-Host "cycle exit $code ($verdict); log: $log"

exit $code
