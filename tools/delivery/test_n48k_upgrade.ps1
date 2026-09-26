# N47X -> N48K native upgrade, synthetic facts and explicit use receipts only.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$OldPackage,
 [Parameter(Mandatory=$true)][string]$NewPackage,
 [Parameter(Mandatory=$true)][string]$Report,
 [Parameter(Mandatory=$true)][ValidatePattern("^[0-9a-f]{64}$")][string]$ExpectedNewSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$old=(Resolve-Path -LiteralPath $OldPackage).ProviderPath
$new=(Resolve-Path -LiteralPath $NewPackage).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
if(Test-Path -LiteralPath $reportPath){throw 'Report must be new.'}
$utf8=New-Object Text.UTF8Encoding($false,$true)
function Hash([string]$p){return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
if((Hash $old) -cne 'c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d'){throw 'Wrong original release.'}
if((Hash $new) -cne $ExpectedNewSha256){throw 'Wrong new candidate ZIP.'}
# OldPackage is a verified ZIP; expand both packages into fresh Unicode paths.
$root=Join-Path ([IO.Path]::GetTempPath()) ('n48k-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
$oldRoot=Join-Path $root 'old';$newRoot=Join-Path $root ('new '+[char]0x4E2D+[char]::ConvertFromUtf32(0x1F600)+" ' package")
Expand-Archive -LiteralPath $old -DestinationPath $oldRoot
Expand-Archive -LiteralPath $new -DestinationPath $newRoot
$oldExe=Join-Path $oldRoot 'qbrain.exe';$exe=Join-Path $newRoot 'qbrain.exe'
$oldInstaller=Join-Path $oldRoot 'scripts\Install-QbrainMemory.ps1';$installer=Join-Path $newRoot 'scripts\Install-QbrainMemory.ps1'
$oldBridge=Join-Path $oldRoot 'scripts\Invoke-QbrainJson.ps1';$bridge=Join-Path $newRoot 'scripts\Invoke-QbrainJson.ps1'
$data=Join-Path $root 'data';[void][IO.Directory]::CreateDirectory($data)
$saved=@{};$before=Get-Location;$checks=New-Object System.Collections.ArrayList;$ok=$false;$failure=''
Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')} | ForEach-Object {$saved[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
foreach($key in @('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')){[Environment]::SetEnvironmentVariable($key,$data,'Process')}
function Check([bool]$condition,[string]$name){[void]$checks.Add([pscustomobject]@{name=$name;passed=$condition});if(-not $condition){throw $name};Write-Host ('PASS '+$checks.Count+' : '+$name)}
function Call-Qbrain([string]$targetExe,[string]$targetBridge,[string[]]$arguments,[string]$body=''){
 $r=& $targetBridge -FilePath $targetExe -ArgumentList $arguments -InputJson $body
 if($r.ExitCode -ne 0){throw ('Native command failed: '+$r.Stdout)}
 return $r.Stdout
}
function Load([string]$path){return [IO.File]::ReadAllText($path,$utf8)|ConvertFrom-Json}
try{
 Set-Location -LiteralPath $root
 $null=Call-Qbrain $oldExe $oldBridge @('init','--brain','default-to-preserve')
 $global=Join-Path $data 'Qbrain\config.json';$globalHash=Hash $global
 $manifest=Load (Join-Path $newRoot 'MANIFEST.json')
 Check ($manifest.product_source -ceq '24345f85e0c4962c93205a7fab0fbdb380a5ff09' -and (Hash $exe) -ceq $manifest.binary_sha256) 'new package source and executable identity'
 Check ((Hash $exe) -cne (Hash $oldExe)) 'new package does not reuse the old N47X executable'
 foreach($hostName in @('Claude','Codex')){
  $project=Join-Path $root ($hostName+' project');[void][IO.Directory]::CreateDirectory($project);Set-Location -LiteralPath $project
  $settings=Join-Path $project $(if($hostName -ceq 'Claude'){'.claude\settings.local.json'}else{'.codex\hooks.json'})
  [void][IO.Directory]::CreateDirectory((Split-Path -Parent $settings))
  [IO.File]::WriteAllText($settings,'{"user_setting":"keep-user-value","hooks":{}}',$utf8)
  $mcp=Join-Path $project $(if($hostName -ceq 'Claude'){'.mcp.json'}else{'.codex\config.toml'})
  $initial=if($hostName -ceq 'Claude'){'{"user_setting":"keep-mcp-value","mcpServers":{}}'}else{"# keep-mcp-value`nmodel = 'fixture'`n"}
  [IO.File]::WriteAllText($mcp,$initial,$utf8)
  $brain='upgrade-'+$hostName.ToLowerInvariant()
  $null=& $oldInstaller -HostName $hostName -ProjectPath $project -BrainId $brain -Binary $oldExe -EnableCapture -EnableFactPromotion -EnableFactRecall
  $config=$null
  foreach($dir in Get-ChildItem -LiteralPath (Join-Path $data 'Qbrain\integrations') -Directory){$path=Join-Path $dir.FullName 'config.json';if([IO.File]::Exists($path) -and (Load $path).project_root -ceq $project){$config=$path}}
  Check ($null -ne $config) ($hostName+' old installation found')
  $status=(& $oldInstaller -Action Status -HostName $hostName -ProjectPath $project)|ConvertFrom-Json
  Check ($status.installed -and $status.configuration_matches) ($hostName+' old installation coherent')
  $quote='I prefer '+$hostName+' preserved upgrade evidence.'
  $event=@{hook_event_name='UserPromptSubmit';session_id='before-upgrade';turn_id='one';cwd=$project;prompt=$quote}|ConvertTo-Json -Compress
  $null=Call-Qbrain $oldExe $oldBridge @('hook','--config',$config) $event
  $facts=(Call-Qbrain $oldExe $oldBridge @('fact','read','--brain',$brain))|ConvertFrom-Json
  Check ($facts.items.Count -eq 1 -and $facts.items[0].object -ceq $quote) ($hostName+' old EXE creates actual preserved evidence')
  $factId=$facts.items[0].fact_id;$revision=$facts.items[0].revision
  $null=& $installer -HostName $hostName -ProjectPath $project -BrainId $brain -Binary $exe -EnableCapture -EnableFactPromotion -EnableFactRecall
  $status=(& $installer -Action Status -HostName $hostName -ProjectPath $project)|ConvertFrom-Json
  Check ($status.installed -and $status.configuration_matches -and -not $status.recovery_required) ($hostName+' new installer upgrades coherently')
  $cfg=Load $config
  Check ($cfg.capture -and $cfg.fact_promotion -and $cfg.fact_recall) ($hostName+' explicit opt-ins retained')
  $settingsValue=Load $settings
  Check ($settingsValue.user_setting -ceq 'keep-user-value' -and [IO.File]::ReadAllText($mcp,$utf8).Contains('keep-mcp-value')) ($hostName+' unrelated configuration retained')
  foreach($name in @('SessionStart','UserPromptSubmit','Stop','PreCompact','SessionEnd')){Check (@($settingsValue.hooks.$name).Count -eq 1) ($hostName+' no duplicate '+$name)}
  $owned=Split-Path -Parent $config;$owner=Load (Join-Path $owned 'installation.json')
  Check ($owner.mcp.definition.command -ceq $exe) ($hostName+' new executable path registered')
  Check ((Hash (Join-Path $owned 'Invoke-QbrainJson.ps1')) -ceq (Hash $bridge)) ($hostName+' new diagnostic bridge actually installed')
  $event=@{hook_event_name='SessionStart';session_id='after-upgrade';cwd=$project}|ConvertTo-Json -Compress
  $response=(Call-Qbrain $exe $bridge @('hook','--config',$config) $event)|ConvertFrom-Json
  $text=$response.hookSpecificOutput.additionalContext;$context=$text.Substring($text.IndexOf("`n")+1)|ConvertFrom-Json
  Check ($context.fact_groups[0].facts[0].fact_id -ceq $factId -and $context.fact_groups[0].facts[0].object -ceq $quote) ($hostName+' new session returns original fact and quote')
  $uid=[Guid]::NewGuid().ToString('N')+[Guid]::NewGuid().ToString('N')
  $body=@{fact_id=$factId;usage_id=$uid;expected_revision=$revision}|ConvertTo-Json -Compress
  $use=(Call-Qbrain $exe $bridge @('fact','report-use','--brain',$brain) $body)|ConvertFrom-Json
  Check ($use.status -ceq 'reported' -and -not $use.host_consumption_verified) ($hostName+' new report-use works without consumption claim')
  $list=(Call-Qbrain $exe $bridge @('fact','usage-list','--brain',$brain,'--id',$factId,'--state','current'))|ConvertFrom-Json
  Check ($list.items.Count -eq 1 -and $list.items[0].usage_id -ceq $uid) ($hostName+' new usage-list finds the actual receipt')
  $body=@{fact_id=$factId;usage_id=$uid}|ConvertTo-Json -Compress
  $withdrawn=(Call-Qbrain $exe $bridge @('fact','revoke-use','--brain',$brain) $body)|ConvertFrom-Json
  Check ($withdrawn.status -ceq 'withdrawn') ($hostName+' explicit receipt withdrawal succeeds')
  $list=(Call-Qbrain $exe $bridge @('fact','usage-list','--brain',$brain,'--id',$factId,'--state','withdrawn'))|ConvertFrom-Json
  Check ($list.items.Count -eq 1 -and $list.items[0].usage_id -ceq $uid) ($hostName+' audit retains withdrawal tombstone')
  $d=& $bridge -FilePath $exe -ArgumentList @('version') -IncludeDiagnostics
  Check ($d.ExitCode -eq 0 -and $d.Transport.phase -ceq 'complete') ($hostName+' packaged bridge diagnostics are usable')
  $null=& $installer -HostName $hostName -ProjectPath $project -BrainId $brain -Binary $exe
  $cfg=Load $config
  Check (-not $cfg.capture -and -not $cfg.fact_promotion -and -not $cfg.fact_recall) ($hostName+' omitted opt-ins return to default off')
  $null=& $installer -Action Uninstall -HostName $hostName -ProjectPath $project
  $status=(& $installer -Action Status -HostName $hostName -ProjectPath $project)|ConvertFrom-Json
  Check (-not $status.installed -and -not $status.host_consumption_confirmed) ($hostName+' uninstall disables integration')
  $facts=(Call-Qbrain $exe $bridge @('fact','read','--brain',$brain))|ConvertFrom-Json
  Check ($facts.items.Count -eq 1 -and $facts.items[0].fact_id -ceq $factId) ($hostName+' uninstall preserves original fact')
  $list=(Call-Qbrain $exe $bridge @('fact','usage-list','--brain',$brain,'--id',$factId))|ConvertFrom-Json
  Check ($list.items.Count -eq 1 -and $list.items[0].usage_id -ceq $uid) ($hostName+' uninstall preserves receipt audit history')
 }
 Check ((Hash $global) -ceq $globalHash) 'global default brain configuration unchanged'
 Check ((Hash $new) -ceq $ExpectedNewSha256) 'tested package bytes unchanged'
 $ok=$true
}catch{$failure=$_.Exception.Message}
finally{
 Set-Location $before
 $record=[pscustomobject]@{schema='qbrain-n48k-upgrade-v1';result=$(if($ok){'PASS'}else{'FAIL'});shell_major=$PSVersionTable.PSVersion.Major;checks=@($checks);failure=$failure;old_zip_sha256=(Hash $old);new_zip_sha256=(Hash $new);binary_sha256=(Hash $exe);script_sha256=(Hash $PSCommandPath);real_client_verified=$false}
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $reportPath));[IO.File]::WriteAllText($reportPath,(ConvertTo-Json -InputObject $record -Depth 10),$utf8)
 foreach($key in @('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')){[Environment]::SetEnvironmentVariable($key,$null,'Process')}
 foreach($key in $saved.Keys){[Environment]::SetEnvironmentVariable($key,$saved[$key],'Process')}
 Remove-Item -LiteralPath $root -Recurse -Force
}
if(-not $ok){Write-Error ('Upgrade test failed: '+$failure);exit 1}
