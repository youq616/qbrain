# Isolated native installer/Hook promotion test; does not launch a real client.
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
$root=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-promotion-optin-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
$old=@{};Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')} | ForEach-Object {$old[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
$env:HOME=$root;$env:LOCALAPPDATA=$root;$env:USERPROFILE=$root;$env:APPDATA=$root
$starting=Get-Location;$script:checks=New-Object System.Collections.ArrayList;$passed=$false
function Check([bool]$ok,[string]$name){[void]$script:checks.Add([pscustomobject]@{name=$name;status=$(if($ok){'PASS'}else{'FAIL'})});if(-not $ok){throw $name};Write-Host "PASS $($script:checks.Count): $name"}
function Qb([string[]]$arguments,[string]$body=''){$r=& $bridge -FilePath $exe -ArgumentList $arguments -InputJson $body;if($r.ExitCode -ne 0){throw 'Native fixture command failed.'};return $r.Stdout}
function Load([string]$p){return [IO.File]::ReadAllText($p,$utf8)|ConvertFrom-Json}
function Store([string]$p,$v){[IO.File]::WriteAllText($p,($v|ConvertTo-Json -Depth 20 -Compress),$utf8)}
try {
 $global=Join-Path $root '.codex\config.toml';[void][IO.Directory]::CreateDirectory((Split-Path $global -Parent));[IO.File]::WriteAllText($global,'# unrelated global fixture',$utf8)
 foreach($name in @('Claude','Codex')){
  $project=Join-Path $root ($name+'Promotion');[void][IO.Directory]::CreateDirectory($project);Set-Location -LiteralPath $project
  $brain='promotion-install-'+$name.ToLowerInvariant()
  $rejected=$false
  try{$null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableFactPromotion}catch{$rejected=$true}
  Check ($rejected -and -not (Test-Path -LiteralPath (Join-Path $project '.claude')) -and -not (Test-Path -LiteralPath (Join-Path $project '.codex'))) "$name promotion_requires_capture_before_writes"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain
  $cfgPath=$null
  foreach($dir in Get-ChildItem -LiteralPath (Join-Path $root 'Qbrain\integrations') -Directory){$p=Join-Path $dir.FullName 'config.json';if([IO.File]::Exists($p) -and (Load $p).project_root -ceq $project){$cfgPath=$p}}
  $cfg=Load $cfgPath
  Check (-not $cfg.fact_promotion -and -not $cfg.capture -and -not $cfg.fact_recall) "$name default_all_optins_off"
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.fact_promotion_enabled) "$name default_status_off"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableCapture
  Check ((Load $cfgPath).capture -and -not (Load $cfgPath).fact_promotion) "$name capture_only_not_promotion"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableCapture -EnableFactPromotion
  $cfg=Load $cfgPath
  Check ($cfg.capture -and $cfg.fact_promotion -and -not $cfg.fact_recall) "$name explicit_promotion_not_recall"
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check ($status.fact_promotion_enabled -and $status.configuration_matches) "$name effective_status_on"
  $quote='I prefer complete automatic '+$name+' fact promotion.'
  $null=Qb @('hook','--config',$cfgPath) (@{hook_event_name='UserPromptSubmit';session_id='installed';turn_id='one';cwd=$project;prompt=$quote}|ConvertTo-Json -Compress)
  $facts=(Qb @('fact','read','--brain',$brain))|ConvertFrom-Json
  Check ($facts.items.Count -eq 1 -and $facts.items[0].object -ceq $quote -and $facts.items[0].predicate -ceq 'memory.preference') "$name installed_flag_promotes_actual_event"
  $trace=Load (Join-Path (Split-Path $cfgPath -Parent) 'last-trace.json')
  Check ($trace.fact_promotion_status -ceq 'completed' -and $trace.fact_promotion_counts.created -eq 1) "$name actual_promotion_trace"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableCapture -EnableFactPromotion -EnableFactRecall
  $out=(Qb @('hook','--config',$cfgPath) (@{hook_event_name='SessionStart';session_id='new';cwd=$project}|ConvertTo-Json -Compress))|ConvertFrom-Json
  $text=$out.hookSpecificOutput.additionalContext;$context=$text.Substring($text.IndexOf("`n")+1)|ConvertFrom-Json
  Check ($context.fact_groups.Count -eq 1 -and $context.fact_groups[0].facts[0].object -ceq $quote) "$name three_flags_complete_pipeline"
  $cfg=Load $cfgPath;$cfg.fact_promotion='true';Store $cfgPath $cfg
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.fact_promotion_enabled) "$name malformed_boolean_off"
  $cfg.fact_promotion=$true;$cfg.capture=$false;Store $cfgPath $cfg
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.fact_promotion_enabled) "$name capture_dependency_status_off"
  $cfg.capture=$true;$cfg.extraction='deferred';Store $cfgPath $cfg
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.fact_promotion_enabled) "$name local_dependency_status_off"
  $cfg.extraction='local';$cfg.enabled=$false;Store $cfgPath $cfg
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.fact_promotion_enabled) "$name disabled_config_status_off"
  $null=& $installer -HostName $name -ProjectPath $project -Binary $exe -BrainId $brain -EnableCapture -EnableFactRecall
  Check (-not (Load $cfgPath).fact_promotion) "$name reinstall_resets_promotion"
  $null=& $installer -Action Uninstall -HostName $name -ProjectPath $project
  $status=(& $installer -Action Status -HostName $name -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.installed -and -not $status.fact_promotion_enabled -and -not (Load $cfgPath).enabled) "$name uninstall_disables_promotion"
  Check ($status.host_consumption_confirmed -eq $false) "$name fixture_not_live_consumption"
 }
 Check ([IO.File]::ReadAllText($global,$utf8) -ceq '# unrelated global fixture') 'global_client_config_unchanged'
 $passed=$true;Write-Host "N47E promotion installer: $($script:checks.Count) checks passed."
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
