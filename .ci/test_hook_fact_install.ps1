# Actual native opt-in installation; process-only test environment, no user settings.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Binary,[Parameter(Mandatory=$true)][string]$Report)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'Native Windows required.'}
$exe=(Resolve-Path -LiteralPath $Binary).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
$installer=Join-Path $PSScriptRoot '..\scripts\Install-QbrainMemory.ps1'
$bridge=Join-Path $PSScriptRoot '..\scripts\Invoke-QbrainJson.ps1'
$utf8=New-Object Text.UTF8Encoding($false,$true)
$root=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-fact-optin-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
$old=@{};Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')} | ForEach-Object {$old[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
$env:HOME=$root;$env:LOCALAPPDATA=$root;$env:USERPROFILE=$root;$env:APPDATA=$root
$starting=Get-Location;$script:checks=New-Object System.Collections.ArrayList;$passed=$false
function Check([bool]$ok,[string]$name){[void]$script:checks.Add([pscustomobject]@{name=$name;status=$(if($ok){'PASS'}else{'FAIL'})});if(-not $ok){throw $name};Write-Host "PASS $($script:checks.Count): $name"}
function Qb([string[]]$arguments,[string]$body=''){$r=& $bridge -FilePath $exe -ArgumentList $arguments -InputJson $body;if($r.ExitCode -ne 0){throw 'Native fixture command failed.'};return $r.Stdout}
function Load([string]$p){return [IO.File]::ReadAllText($p,$utf8)|ConvertFrom-Json}
try {
 $global=Join-Path $root '.codex\config.toml';[void][IO.Directory]::CreateDirectory((Split-Path $global -Parent));[IO.File]::WriteAllText($global,'# unrelated global fixture',$utf8)
 foreach($name in @('Claude','Codex')){
  $project=Join-Path $root ($name+'Project');[void][IO.Directory]::CreateDirectory($project);Set-Location -LiteralPath $project
  $brain='fact-optin-'+$name.ToLowerInvariant();$null=Qb @('init','--brain',$brain,'--no-default');$null=Qb @('config','set','memory.writeback','salient','--brain',$brain)
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain
  $cfgPath=$null
  foreach($dir in Get-ChildItem -LiteralPath (Join-Path $root 'Qbrain\integrations') -Directory){$p=Join-Path $dir.FullName 'config.json';if([IO.File]::Exists($p) -and (Load $p).project_root -ceq $project){$cfgPath=$p}}
  Check ($null -ne $cfgPath -and -not (Load $cfgPath).fact_recall) "$name default_fact_off"
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.fact_recall_enabled) "$name default_status_off"
  Check (-not (Load $cfgPath).capture) "$name default_capture_off"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableFactRecall
  Check ((Load $cfgPath).fact_recall) "$name explicit_fact_on"
  Check (-not (Load $cfgPath).capture) "$name fact_not_capture_consent"
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check ($status.fact_recall_enabled -and $status.configuration_matches) "$name matching_optin_status"
  $quote='I prefer a complete synthetic fact from my installed Hook.'
  $captured=(Qb @('memory','capture','--brain',$brain,'--manual') (@{session_id='install-test';fragment_id='one';messages=@(@{role='user';content=$quote})}|ConvertTo-Json -Depth 6 -Compress))|ConvertFrom-Json
  $null=Qb @('memory','extract','--brain',$brain,'--event',$captured.event_id)
  $memory=(Qb @('memory','read','--brain',$brain))|ConvertFrom-Json
  $null=Qb @('fact','create','--brain',$brain) (@{predicate='preference.editor';item_id=$memory.items[0].item_id}|ConvertTo-Json -Compress)
  $out=(Qb @('hook','--config',$cfgPath) (@{hook_event_name='SessionStart';session_id='hook-start';cwd=$project}|ConvertTo-Json -Compress))|ConvertFrom-Json
  $text=$out.hookSpecificOutput.additionalContext;$body=$text.Substring($text.IndexOf("`n")+1)|ConvertFrom-Json
  Check ($body.fact_groups.Count -eq 1 -and $body.fact_groups[0].facts[0].object -ceq $quote) "$name installed_flag_reaches_native_hook"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableCapture
  Check (-not (Load $cfgPath).fact_recall) "$name capture_only_fact_off"
  Check ((Load $cfgPath).capture) "$name capture_only_capture_on"
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.fact_recall_enabled) "$name capture_only_status_off"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableCapture -EnableFactRecall
  Check ((Load $cfgPath).capture -and (Load $cfgPath).fact_recall) "$name independent_flags_both_on"
  $cfg=Load $cfgPath;$cfg.fact_recall='true';[IO.File]::WriteAllText($cfgPath,($cfg|ConvertTo-Json -Compress),$utf8)
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.fact_recall_enabled) "$name malformed_boolean_not_reported_enabled"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain
  Check (-not (Load $cfgPath).fact_recall -and -not (Load $cfgPath).capture) "$name reinstall_resets_optins"
  $null=& $installer -Action Uninstall -HostName $name -ProjectPath $project
  Check (-not (Load $cfgPath).enabled) "$name uninstall_disables_owned_config"
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.installed -and -not $status.fact_recall_enabled) "$name uninstalled_status"
  Check ($status.host_consumption_confirmed -eq $false) "$name fixture_not_live_model_consumption"
 }
 Check ([IO.File]::ReadAllText($global,$utf8) -ceq '# unrelated global fixture') 'global_client_config_unchanged'
 $passed=$true;Write-Host "N47D fact opt-in installer: $($script:checks.Count) checks passed."
} finally {
 Set-Location $starting
 if(-not $passed -and @($script:checks|Where-Object {$_.status -eq 'FAIL'}).Count -eq 0){[void]$script:checks.Add([pscustomobject]@{name='execution_interrupted';status='FAIL'})}
 $repo=Join-Path $PSScriptRoot '..';$source=(& git -C $repo rev-parse HEAD).Trim();if($LASTEXITCODE -ne 0){$source=$null}
 & git -C $repo diff --quiet HEAD --; $clean=($LASTEXITCODE -eq 0)
 $result=[pscustomobject]@{tracked_tree_clean=$clean;result=$(if($passed){'PASS'}else{'FAIL'});source_commit=$source;native_windows=$true;shell_major=$PSVersionTable.PSVersion.Major;checks=@($script:checks);check_count=$script:checks.Count;binary_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant();script_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();installer_sha256=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant();real_host_consumption_verified=$false}
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $reportPath));[IO.File]::WriteAllText($reportPath,($result|ConvertTo-Json -Depth 12),$utf8)
 foreach($key in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')){[Environment]::SetEnvironmentVariable($key,$null,'Process')}
 foreach($key in $old.Keys){[Environment]::SetEnvironmentVariable($key,$old[$key],'Process')}
 Remove-Item -LiteralPath $root -Recurse -Force
}
