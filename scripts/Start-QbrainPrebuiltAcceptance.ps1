# Acceptance helper only. Does not install tools or modify persistent settings.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Package,
    [string]$OutputDirectory = '',
    [switch]$RunSmoke
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Get-Command may return multiple applications; select one executable path.
$python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { throw 'Python 3.10+ is needed for acceptance only; no compiler is required.' }
$arguments = @((Join-Path $PSScriptRoot 'prebuilt_acceptance.py'), '--package', $Package)
if ($OutputDirectory) { $arguments += @('--output', $OutputDirectory) }
if ($RunSmoke) { $arguments += '--run-smoke' }
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "Prebuilt acceptance exited with code $LASTEXITCODE. Preserve the report/logs." }
