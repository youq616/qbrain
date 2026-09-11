# ASCII source so Windows PowerShell 5.1 does not depend on a source-file BOM.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Binary)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$bridge = Join-Path $PSScriptRoot '..\scripts\Invoke-QbrainJson.ps1'
$original = (Resolve-Path -LiteralPath $Binary).ProviderPath
$unicode = [string][char]0x4E2D + [char]0x6587 + ' space ' + [char]::ConvertFromUtf32(0x1F600)
$root = Join-Path ([IO.Path]::GetTempPath()) ('qbrain-ps-' + [Guid]::NewGuid().ToString('N'))
$root = Join-Path $root $unicode
[void][IO.Directory]::CreateDirectory($root)
$binaryPath = Join-Path $root 'qbrain.exe'
[IO.File]::Copy($original, $binaryPath)
$oldEnv = @{}
Get-ChildItem Env: | Where-Object { $_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE') } | ForEach-Object {
    $oldEnv[$_.Name] = $_.Value
    [Environment]::SetEnvironmentVariable($_.Name, $null, 'Process')
}
$env:HOME=$root; $env:LOCALAPPDATA=$root; $env:USERPROFILE=$root
$script:checks = 0
function Check([bool]$Value, [string]$Label) {
    if (-not $Value) { throw $Label }
    $script:checks++
    Write-Host "PASS $script:checks : $Label"
}
function Invoke-Test([string[]]$Arguments, [string]$Data='') {
    $r = & $bridge -FilePath $binaryPath -ArgumentList ($Arguments + @('--brain','transport-ci')) -InputJson $Data
    if ($r.ExitCode -ne 0) { throw ('Qbrain failed: ' + $r.Stderr + $r.Stdout) }
    return $r.Stdout
}
try {
    $null=Invoke-Test @('init')
    # A manual archive does not require changing the operator's auto-write policy.
    $quote='I prefer ' + $unicode + ' and a literal "quote" and trailing slash\'
    $data=@{session_id=$unicode;fragment_id='stdin';messages=@(@{role='user';content=$quote})} | ConvertTo-Json -Depth 6 -Compress
    $capture=(Invoke-Test @('memory','capture','--manual') $data) | ConvertFrom-Json
    Check ($capture.status -eq 'archived') 'UTF-8 stdin reaches a real native executable'
    $extraction=(Invoke-Test @('memory','extract','--event',$capture.event_id)) | ConvertFrom-Json
    Check ($extraction.item_count -eq 1) 'exact original user quote is extracted'
    $read=(Invoke-Test @('memory','read','--query',$unicode)) | ConvertFrom-Json
    Check ($read.items.Count -eq 1 -and $read.items[0].quote -ceq $quote) 'Chinese and emoji argv/stdout survive round trip'
    $read=(Invoke-Test @('memory','read','--query','"quote"')) | ConvertFrom-Json
    Check ($read.items.Count -eq 1) 'embedded quotation marks are not interpreted by a shell'
    $read=(Invoke-Test @('memory','read','--query','slash\')) | ConvertFrom-Json
    Check ($read.items.Count -eq 1) 'trailing backslash follows CRT quoting rules'
    $read=(Invoke-Test @('memory','read','--query','')) | ConvertFrom-Json
    Check ($read.items.Count -eq 1) 'empty arguments are preserved'
    $rejected=$false
    try { $null=& $bridge -FilePath $binaryPath -ArgumentList @('memory','capture') -InputJson ('x' * 262145) } catch { $rejected=$true }
    Check $rejected 'bridge rejects oversized input before process launch'
    $rejected=$false
    try { $null=& $bridge -FilePath $binaryPath -ArgumentList @('memory','read',([string][char]0)) } catch { $rejected=$true }
    Check $rejected 'bridge rejects NUL-bearing process arguments'
    Write-Host "N44A native transport: $script:checks checks passed under PowerShell $($PSVersionTable.PSVersion)."
} finally {
    foreach($name in @('HOME','LOCALAPPDATA','USERPROFILE')) { [Environment]::SetEnvironmentVariable($name,$null,'Process') }
    foreach($name in $oldEnv.Keys) { [Environment]::SetEnvironmentVariable($name,$oldEnv[$name],'Process') }
    Remove-Item -LiteralPath (Split-Path -Parent $root) -Recurse -Force
}
