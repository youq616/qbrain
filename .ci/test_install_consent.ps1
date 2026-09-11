# Test installer consent and Windows path aliases with actual native hook calls.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Binary)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Binary).ProviderPath
$installer=Join-Path $PSScriptRoot '..\scripts\Install-QbrainMemory.ps1'
$bridge=Join-Path $PSScriptRoot '..\scripts\Invoke-QbrainJson.ps1'
$utf8=New-Object Text.UTF8Encoding($false,$true)
$root=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-consent-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
$old=@{};Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE')} | ForEach-Object {$old[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
$env:HOME=$root;$env:LOCALAPPDATA=$root;$env:USERPROFILE=$root
$starting=Get-Location;$script:checks=0
function Check([bool]$v,[string]$s){if(-not $v){throw $s};$script:checks++;Write-Host "PASS $script:checks : $s"}
function Qb([string[]]$arguments,[string]$body=''){$r=& $bridge -FilePath $exe -ArgumentList $arguments -InputJson $body;if($r.ExitCode -ne 0){throw ($r.Stdout+$r.Stderr)};return $r.Stdout}
function Load([string]$p){return [IO.File]::ReadAllText($p,$utf8)|ConvertFrom-Json}
try {
 foreach($name in @('Claude','Codex')) {
  $project=Join-Path $root ($name+'CaseProject');[void][IO.Directory]::CreateDirectory($project);Set-Location -LiteralPath $project
  $brain='optin-'+$name.ToLowerInvariant()
  $null=Qb @('init','--brain',$brain,'--no-default')
  $null=Qb @('config','set','memory.writeback','salient','--brain',$brain)
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain
  $cfgPath=$null
  foreach($dir in Get-ChildItem -LiteralPath (Join-Path $root 'Qbrain\integrations') -Directory){$p=Join-Path $dir.FullName 'config.json';if([IO.File]::Exists($p) -and (Load $p).project_root -ceq $project){$cfgPath=$p}}
  Check ($null -ne $cfgPath) 'owned runtime configuration exists'
  Check (-not (Load $cfgPath).capture) 'shared salient brain does not bypass installation capture opt-in'
  $quote='I prefer explicit capture consent for this project.'
  $payload=@{hook_event_name='UserPromptSubmit';session_id='declined';turn_id='one';cwd=$project;prompt=$quote}|ConvertTo-Json -Compress
  $null=Qb @('hook','--config',$cfgPath) $payload
  $read=(Qb @('memory','read','--brain',$brain))|ConvertFrom-Json
  Check ($read.items.Count -eq 0) 'unconsented installation does not publish a user memory'
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableCapture
  Check ((Load $cfgPath).capture) 'explicit opt-in enables runtime capture'
  $payload=@{hook_event_name='UserPromptSubmit';session_id='accepted';turn_id='one';cwd=$project.ToUpperInvariant();prompt=$quote}|ConvertTo-Json -Compress
  $null=Qb @('hook','--config',$cfgPath) $payload
  $read=(Qb @('memory','read','--brain',$brain))|ConvertFrom-Json
  Check ($read.items.Count -eq 1 -and $read.items[0].quote -ceq $quote) 'case-only event cwd alias uses filesystem identity'
  $cfg=Load $cfgPath;$cfg.project_root=$project.ToUpperInvariant();[IO.File]::WriteAllText($cfgPath,($cfg|ConvertTo-Json -Compress),$utf8)
  $payload=@{hook_event_name='SessionStart';session_id='reopened';cwd=$project}|ConvertTo-Json -Compress
  $result=(Qb @('hook','--config',$cfgPath) $payload)|ConvertFrom-Json
  Check ($result.hookSpecificOutput.additionalContext.Contains($quote)) 'case-only fixed root alias still recalls actual project memory'
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain
  Check (-not (Load $cfgPath).capture) 'reinstallation without opt-in returns to recall-only mode'
  $null=& $installer -Action Uninstall -HostName $name -ProjectPath $project
  Check (-not (Load $cfgPath).enabled) 'uninstallation disables the integration'
 }
 Write-Host "Additional installation consent: $script:checks checks passed."
} finally {
 Set-Location $starting
 foreach($key in @('HOME','LOCALAPPDATA','USERPROFILE')){[Environment]::SetEnvironmentVariable($key,$null,'Process')}
 foreach($key in $old.Keys){[Environment]::SetEnvironmentVariable($key,$old[$key],'Process')}
 Remove-Item -LiteralPath $root -Recurse -Force
}
