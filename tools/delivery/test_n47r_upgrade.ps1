# Actual old-preview -> integrated-package upgrade and exact guide extraction.
# Test-only roots; no signed-in clients, real brain data or model requests.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$BaselineZip,
 [Parameter(Mandatory=$true)][string]$CandidateZip,
 [Parameter(Mandatory=$true)][string]$Guide,
 [Parameter(Mandatory=$true)][string]$Report
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'Native Windows required.'}
$baseline=(Resolve-Path -LiteralPath $BaselineZip).ProviderPath
$candidate=(Resolve-Path -LiteralPath $CandidateZip).ProviderPath
$guidePath=(Resolve-Path -LiteralPath $Guide).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
$utf8=New-Object Text.UTF8Encoding($false,$true)
$zipHash='e7158949d805a0a25157bfb720561e4b21e80a433a6c7f031c60ee3bbaa746c5'
function FileHash([string]$p){return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
if((FileHash $baseline) -cne 'ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c'){throw 'Wrong old package.'}
if((FileHash $candidate) -cne $zipHash){throw 'Wrong candidate.'}
if((FileHash $guidePath) -cne '7db4673720d68d902555f72bbe778b0da3045c4c3b02cefa3717e3843b9e9b46'){
 # Native checkout may have CRLF, while the bundled guide is pinned LF.
 $text=[IO.File]::ReadAllText($guidePath,$utf8).Replace("`r`n","`n")
 $h=[Security.Cryptography.SHA256]::Create()
 try{$guideHash=([BitConverter]::ToString($h.ComputeHash($utf8.GetBytes($text)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}
 if($guideHash -cne '7db4673720d68d902555f72bbe778b0da3045c4c3b02cefa3717e3843b9e9b46'){throw 'Wrong guide.'}
}
$guideText=[IO.File]::ReadAllText($guidePath,$utf8)
$match=[regex]::Match($guideText,'(?s)```powershell\r?\n(.*?)\r?\n```')
if(-not $match.Success){throw 'Guide command block missing.'}
# Only this previously hash-validated first block is executed.
$extractBlock=[scriptblock]::Create($match.Groups[1].Value)
$root=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-upgrade-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
$before=Get-Location;$saved=@{}
Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')} | ForEach-Object {$saved[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
$env:HOME=$root;$env:LOCALAPPDATA=$root;$env:USERPROFILE=$root;$env:APPDATA=$root
$checks=New-Object System.Collections.ArrayList;$success=$false
function Check([bool]$ok,[string]$name){[void]$checks.Add([pscustomobject]@{name=$name;passed=$ok});if(-not $ok){throw $name};Write-Host ('PASS '+$checks.Count+' : '+$name)}
function Save([string]$p,$value){[IO.File]::WriteAllText($p,(ConvertTo-Json -InputObject $value -Depth 30 -Compress),$utf8)}
function Load([string]$p){return [IO.File]::ReadAllText($p,$utf8)|ConvertFrom-Json}
try {
 $stage=Join-Path $root ('package '+[char]0x4E2D+[char]::ConvertFromUtf32(0x1F600)+" ' fixture")
 [void][IO.Directory]::CreateDirectory($stage);Set-Location -LiteralPath $stage
 Copy-Item -LiteralPath $candidate -Destination (Join-Path $stage 'qbrain-windows-x64-n47r-candidate.zip')
 [IO.File]::WriteAllText((Join-Path $stage 'SHA256SUMS.txt'),('0'*64+'  qbrain-windows-x64-n47r-candidate.zip'+"`n"),$utf8)
 $rejected=$false;try{. $extractBlock}catch{$rejected=$true}
 Check ($rejected -and -not (Test-Path -LiteralPath (Join-Path $stage 'qbrain-n47r'))) 'guide rejects wrong checksum before extraction'
 [IO.File]::WriteAllText((Join-Path $stage 'SHA256SUMS.txt'),($zipHash+'  qbrain-windows-x64-n47r-candidate.zip'+"`n"),$utf8)
 . $extractBlock
 Check ((FileHash $exe) -ceq 'c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5') 'guide extracts exact native EXE'
 Check ((FileHash $installer) -ceq 'd802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51') 'guide extracts exact repaired installer'
 $rejected=$false;try{. $extractBlock}catch{$rejected=$true}
 Check $rejected 'guide rejects existing extraction directory'
 $oldRoot=Join-Path $root 'old';Expand-Archive -LiteralPath $baseline -DestinationPath $oldRoot
 $oldInstaller=Join-Path $oldRoot 'scripts\Install-QbrainMemory.ps1';$oldExe=Join-Path $oldRoot 'qbrain.exe'
 $bridge=Join-Path $target 'scripts\Invoke-QbrainJson.ps1'
 function Qb([string[]]$argv,[string]$body=''){$r=& $bridge -FilePath $exe -ArgumentList $argv -InputJson $body;if($r.ExitCode -ne 0){throw 'Actual native command failed.'};return $r.Stdout}
 $null=Qb @('init','--brain','keep-default')
 $globalPath=Join-Path $root 'Qbrain\config.json';$globalBytes=[Convert]::ToBase64String([IO.File]::ReadAllBytes($globalPath))
 foreach($hostName in @('Claude','Codex')){
  $project=Join-Path $root ($hostName+' project');[void][IO.Directory]::CreateDirectory($project);Set-Location -LiteralPath $project
  $hostPath=if($hostName -ceq 'Claude'){Join-Path $project '.claude\settings.local.json'}else{Join-Path $project '.codex\hooks.json'}
  [void][IO.Directory]::CreateDirectory((Split-Path -Parent $hostPath))
  Save $hostPath ([pscustomobject]@{user_setting='preserve-user-setting';hooks=[pscustomobject]@{}})
  $mcp=if($hostName -ceq 'Claude'){Join-Path $project '.mcp.json'}else{Join-Path $project '.codex\config.toml'}
  if($hostName -ceq 'Claude'){Save $mcp ([pscustomobject]@{user_setting='preserve-user-mcp';mcpServers=[pscustomobject]@{}})}else{[IO.File]::WriteAllText($mcp,"# preserve-user-mcp`nmodel = 'fixture'`n",$utf8)}
  $brain='upgrade-'+$hostName.ToLowerInvariant()
  $null=& $oldInstaller -HostName $hostName -ProjectPath $project -BrainId $brain -Binary $oldExe -EnableCapture -EnableFactPromotion -EnableFactRecall
  $cfgPath=$null
  foreach($dir in Get-ChildItem -LiteralPath (Join-Path $root 'Qbrain\integrations') -Directory){$p=Join-Path $dir.FullName 'config.json';if([IO.File]::Exists($p) -and (Load $p).project_root -ceq $project){$cfgPath=$p}}
  Check ($null -ne $cfgPath) ($hostName+' old installation found')
  $status=(& $oldInstaller -Action Status -HostName $hostName -ProjectPath $project)|ConvertFrom-Json
  Check ($status.installed -and $status.configuration_matches -and $status.fact_promotion_enabled) ($hostName+' old installation active')
  $quote='I prefer preserved '+$hostName+' upgrade evidence.'
  $null=Qb @('hook','--config',$cfgPath) (ConvertTo-Json -InputObject @{hook_event_name='UserPromptSubmit';session_id='before-upgrade';turn_id='one';cwd=$project;prompt=$quote} -Compress)
  $facts=(Qb @('fact','read','--brain',$brain))|ConvertFrom-Json
  Check ($facts.items.Count -eq 1 -and $facts.items[0].object -ceq $quote) ($hostName+' old stored evidence exists')
  $factId=$facts.items[0].fact_id
  $null=& $installer -HostName $hostName -ProjectPath $project -BrainId $brain -Binary $exe -EnableCapture -EnableFactPromotion -EnableFactRecall
  $status=(& $installer -Action Status -HostName $hostName -ProjectPath $project)|ConvertFrom-Json
  Check ($status.installed -and $status.configuration_matches -and -not $status.recovery_required) ($hostName+' new installation coherent')
  $cfg=Load $cfgPath
  Check ($cfg.capture -and $cfg.fact_promotion -and $cfg.fact_recall) ($hostName+' explicit upgrade consent retained')
  $settings=Load $hostPath
  Check ($settings.user_setting -ceq 'preserve-user-setting' -and [IO.File]::ReadAllText($mcp,$utf8).Contains('preserve-user-mcp')) ($hostName+' unrelated configuration preserved')
  foreach($event in @('SessionStart','UserPromptSubmit','Stop','PreCompact','SessionEnd')){Check (@($settings.hooks.$event).Count -eq 1) ($hostName+' no duplicate '+$event)}
  $owner=Load (Join-Path (Split-Path -Parent $cfgPath) 'installation.json')
  Check ($owner.mcp.definition.command -ceq $exe) ($hostName+' MCP routed to new EXE location')
  $out=(Qb @('hook','--config',$cfgPath) (ConvertTo-Json -InputObject @{hook_event_name='SessionStart';session_id='after-upgrade';cwd=$project} -Compress))|ConvertFrom-Json
  $text=$out.hookSpecificOutput.additionalContext;$context=$text.Substring($text.IndexOf("`n")+1)|ConvertFrom-Json
  Check ($context.fact_groups.Count -eq 1 -and $context.fact_groups[0].facts[0].fact_id -ceq $factId -and $context.fact_groups[0].facts[0].object -ceq $quote) ($hostName+' new session preserves old fact identity and quotation')
  $null=& $installer -HostName $hostName -ProjectPath $project -BrainId $brain -Binary $exe
  $cfg=Load $cfgPath
  Check (-not $cfg.capture -and -not $cfg.fact_promotion -and -not $cfg.fact_recall) ($hostName+' unspecified upgrade flags default off')
  $null=& $installer -Action Uninstall -HostName $hostName -ProjectPath $project
  $status=(& $installer -Action Status -HostName $hostName -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.installed -and -not $status.host_consumption_confirmed) ($hostName+' uninstall disables without claiming consumption')
  $facts=(Qb @('fact','read','--brain',$brain))|ConvertFrom-Json
  Check ($facts.items.Count -eq 1 -and $facts.items[0].fact_id -ceq $factId) ($hostName+' uninstall keeps original brain evidence')
 }
 Check ([Convert]::ToBase64String([IO.File]::ReadAllBytes($globalPath)) -ceq $globalBytes) 'global default configuration unchanged'
 $success=$true
} finally {
 Set-Location $before
 if(-not $success -and @($checks|Where-Object {-not $_.passed}).Count -eq 0){[void]$checks.Add([pscustomobject]@{name='execution interrupted';passed=$false})}
 $source=(& git -C (Join-Path $PSScriptRoot '../..') rev-parse HEAD).Trim()
 $record=[pscustomobject]@{schema='qbrain-n47r-upgrade-v1';result=$(if($success){'PASS'}else{'FAIL'});source_commit=$source;native_windows=$true;shell_major=$PSVersionTable.PSVersion.Major;powershell=$PSVersionTable.PSVersion.ToString();candidate_sha256=$zipHash;baseline_sha256=(FileHash $baseline);script_sha256=(FileHash $PSCommandPath);checks=@($checks);count=$checks.Count;real_client_verified=$false}
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $reportPath));[IO.File]::WriteAllText($reportPath,(ConvertTo-Json -InputObject $record -Depth 12),$utf8)
 foreach($key in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')){[Environment]::SetEnvironmentVariable($key,$null,'Process')}
 foreach($key in $saved.Keys){[Environment]::SetEnvironmentVariable($key,$saved[$key],'Process')}
 Remove-Item -LiteralPath $root -Recurse -Force
}
if(-not $success){exit 1}
