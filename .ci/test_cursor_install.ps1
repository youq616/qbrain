# Actual project-local Cursor installation and installed native process calls.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Binary,[Parameter(Mandatory=$true)][string]$Report)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$exe=(Resolve-Path -LiteralPath $Binary).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
$installer=Join-Path $PSScriptRoot '..\scripts\Install-QbrainMemory.ps1'
$bridge=Join-Path $PSScriptRoot '..\scripts\Invoke-QbrainJson.ps1'
$utf8=New-Object Text.UTF8Encoding($false,$true)
$root=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-cursor-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
$old=@{};Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|PG|CURSOR|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')} | ForEach-Object {$old[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
$env:HOME=$root;$env:USERPROFILE=$root;$env:LOCALAPPDATA=$root;$env:APPDATA=$root
$cwd=Get-Location;$passed=$false;$script:checks=New-Object System.Collections.ArrayList
$script:commands=New-Object System.Collections.ArrayList
$rawDir=$reportPath+'.raw';[void][IO.Directory]::CreateDirectory($rawDir)
function Check([bool]$ok,[string]$name){[void]$script:checks.Add([pscustomobject]@{name=$name;passed=$ok});if(-not $ok){throw $name};Write-Host "PASS $($script:checks.Count): $name"}
function J($o){return ConvertTo-Json -InputObject $o -Depth 64 -Compress}
function Load([string]$p){return [IO.File]::ReadAllText($p,$utf8)|ConvertFrom-Json}
function Save([string]$p,$o){[void][IO.Directory]::CreateDirectory((Split-Path $p -Parent));[IO.File]::WriteAllText($p,(J $o),$utf8)}
function Has($o,[string]$k){return $null -ne $o.PSObject.Properties[$k]}
function Record([string]$kind,$a,[string]$inputText,$r){
 $index=$script:commands.Count;$paths=@{}
 foreach($key in @('stdin','stdout','stderr')){
  $value=if($key -eq 'stdin'){$inputText}elseif($key -eq 'stdout'){$r.Stdout}else{$r.Stderr}
  $path=Join-Path $rawDir ($index.ToString('000')+'.'+$key)
  [IO.File]::WriteAllText($path,[string]$value,$utf8)
  $paths[$key]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
 }
 [void]$script:commands.Add([pscustomobject]@{kind=$kind;args=@($a);exit=$r.ExitCode;hashes=$paths})
}
function Qb([string[]]$a,[string]$body=''){
 $argsNative=@($a+@('--brain','cursor-install'));$r=& $bridge -FilePath $exe -ArgumentList $argsNative -InputJson $body
 Record 'native' $argsNative $body $r
 if($r.ExitCode -ne 0){throw 'Fixture native command failed.'};return $r.Stdout
}
function Reject([scriptblock]$f,[string]$name){$denied=$false;try{$null=& $f}catch{$denied=$true};Check $denied $name}
function Installed-Hook($owner,[string]$event,[string]$generation='one',[string]$text=''){
 $entry=@($owner.entries|Where-Object {$_.event -ceq $event})[0].group
 Check (-not (Has $entry 'hooks') -and -not (Has $entry 'commandWindows') -and -not (Has $entry 'args')) 'flat Cursor command, no Claude envelope'
 Check ($entry.command -match '^powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand ([A-Za-z0-9+/=]+)$') 'installed fixed bridge command'
 $encoded=$Matches[1]
 $payload=@{hook_event_name=$event;conversation_id='installed-conversation';generation_id=$generation;workspace_roots=@($owner.project_root);is_background_agent=$false;prompt=$text;text=$text;model='PRIVATE_MODEL';user_email='PRIVATE_EMAIL';transcript_path='PRIVATE_DO_NOT_OPEN'}
 $r=& $bridge -FilePath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',$encoded) -InputJson (J $payload)
 Record 'installed-cursor-hook' @($event,$generation) (J $payload) $r
 Check ($r.ExitCode -eq 0 -and [string]::IsNullOrEmpty($r.Stderr)) 'installed native command nonblocking'
 return $r.Stdout|ConvertFrom-Json
}
try{
 $name="Cursor ' "+[char]0x4E2D+[char]::ConvertFromUtf32(0x1F600)
 $project=Join-Path $root $name;[void][IO.Directory]::CreateDirectory($project);Set-Location -LiteralPath $project
 $hooks=Join-Path $project '.cursor\hooks.json';$mcp=Join-Path $project '.cursor\mcp.json'
 $external=[pscustomobject]@{command='echo original-plugin';timeout=7}
 Save $hooks ([pscustomobject]@{version=1;custom='KEEP';hooks=[pscustomobject]@{sessionStart=@($external);stop=@([pscustomobject]@{command='echo no-auto-loop'})}})
 Save $mcp ([pscustomobject]@{mcpServers=[pscustomobject]@{external=[pscustomobject]@{command='unrelated';args=@('keep')}}})
 $global=Join-Path $root '.cursor\hooks.json';Save $global ([pscustomobject]@{version=1;hooks=[pscustomobject]@{}})
 $globalRaw=[IO.File]::ReadAllText($global,$utf8)
 $null=& $installer -HostName Cursor -ProjectPath $project -Binary $exe -BrainId cursor-install
 $dir=@(Get-ChildItem -LiteralPath (Join-Path $root 'Qbrain\integrations') -Directory)[0].FullName
 $ownerPath=Join-Path $dir 'installation.json';$configPath=Join-Path $dir 'config.json';$owner=Load $ownerPath
 $cfg=Load $configPath;$state=Load $hooks;$m=Load $mcp
 Check ($cfg.host -ceq 'cursor' -and -not $cfg.capture -and -not $cfg.fact_promotion) 'Cursor default consent off'
 Check ($state.version -eq 1 -and $state.custom -ceq 'KEEP' -and (J $state.hooks.stop) -ceq (J @([pscustomobject]@{command='echo no-auto-loop'}))) 'version and unrelated hooks retained'
 Check (@($owner.entries).Count -eq 5) 'only five documented lifecycle events'
 Check ((@($owner.entries.event)-join ',') -ceq 'sessionStart,beforeSubmitPrompt,afterAgentResponse,preCompact,sessionEnd') 'exact native event names'
 Check (@($state.hooks.sessionStart).Count -eq 2 -and (J $state.hooks.sessionStart[0]) -ceq (J $external)) 'existing session handler preserved'
 Check ((Has $m.mcpServers 'external') -and (Has $m.mcpServers $owner.mcp.name)) 'MCP entries merged not replaced'
 Check ((J $m.mcpServers.($owner.mcp.name).args) -ceq '["serve","--brain","cursor-install","--tool-profile","memory"]') 'read-only MCP profile unchanged'
 $status=(& $installer -Action Status -HostName Cursor -ProjectPath $project)|ConvertFrom-Json
 Check ($status.installed -and $status.configuration_matches -and -not $status.host_consumption_confirmed) 'installed status not real consumption certification'
 $null=Qb @('config','set','embed.auto','false','--local');$null=Qb @('config','set','memory.writeback','salient','--local')
 $out=Installed-Hook $owner beforeSubmitPrompt one 'I prefer NOT_AUTHORIZED.'
 Check ($out.continue -and -not (Has $out 'additional_context')) 'no unsupported prompt injection'
 $mem=(Qb @('memory','read'))|ConvertFrom-Json;Check ($mem.items.Count -eq 0) 'per-install capture remains separate'
 $raw=[IO.File]::ReadAllText($hooks,$utf8)
 $null=& $installer -HostName Cursor -ProjectPath $project -Binary $exe -BrainId cursor-install
 Check ([IO.File]::ReadAllText($hooks,$utf8) -ceq $raw) 'reinstall adds no duplicate hooks'
 $null=& $installer -HostName Cursor -ProjectPath $project -Binary $exe -BrainId cursor-install -EnableCapture -EnableFactRecall -EnableFactPromotion
 $owner=Load $ownerPath
 $quote='I prefer Windows native '+[char]0x4E2D+[char]::ConvertFromUtf32(0x1F600)+' exactly.'
 $out=Installed-Hook $owner beforeSubmitPrompt capture $quote
 Check ($out.continue -and -not (Has $out 'additional_context')) 'explicit capture no beforeSubmitPrompt context'
 $mem=(Qb @('memory','read'))|ConvertFrom-Json;Check ($mem.items.Count -eq 1 -and $mem.items[0].quote -ceq $quote) 'installed Unicode capture preserves exact quote'
 $out=Installed-Hook $owner sessionStart
 Check ((Has $out 'additional_context') -and $out.additional_context.Contains($quote) -and -not (Has $out 'hookSpecificOutput')) 'installed sessionStart native Cursor context'
 $out=Installed-Hook $owner afterAgentResponse response 'I prefer ASSISTANT_MUST_NOT_BECOME_FACT.'
 Check (@($out.PSObject.Properties).Count -eq 0) 'assistant event no followup or context'
 $facts=(Qb @('fact','read'))|ConvertFrom-Json;Check ($facts.items.Count -eq 1 -and $facts.items[0].object -ceq $quote) 'assistant never promoted to user fact'
 $null=Installed-Hook $owner preCompact;$null=Installed-Hook $owner sessionEnd
 Check ([IO.File]::ReadAllText($global,$utf8) -ceq $globalRaw) 'no global Cursor edits'
 # Explicit partial-transaction recovery on Cursor paths. No custom rollback code.
 $journal=Join-Path $dir 'pending.json'
 $hookBefore=[IO.File]::ReadAllText($hooks,$utf8);$mcpBefore=[IO.File]::ReadAllText($mcp,$utf8)
 $hookAfter=$hookBefore+' ';$mcpAfter=$mcpBefore+' '
 $pending=[pscustomobject]@{version=1;changes=@([pscustomobject]@{path=$hooks;before=$hookBefore;after=$hookAfter},[pscustomobject]@{path=$mcp;before=$mcpBefore;after=$mcpAfter})}
 [IO.File]::WriteAllText($hooks,$hookAfter,$utf8);[IO.File]::WriteAllText($mcp,$mcpAfter,$utf8);Save $journal $pending
 $status=(& $installer -Action Status -HostName Cursor -ProjectPath $project)|ConvertFrom-Json
 Check ($status.recovery_required -and [IO.File]::ReadAllText($hooks,$utf8) -ceq $hookAfter) 'status reports pending recovery without changing files'
 # A late edit in the second member must prevent rolling back the first member.
 [IO.File]::WriteAllText($mcp,$mcpAfter+'external',$utf8)
 $journalBefore=[IO.File]::ReadAllText($journal,$utf8)
 Reject {& $installer -HostName Cursor -ProjectPath $project -Binary $exe -BrainId cursor-install -EnableCapture -EnableFactRecall -EnableFactPromotion} 'external edit blocks entire Cursor recovery preflight'
 Check ([IO.File]::ReadAllText($hooks,$utf8) -ceq $hookAfter -and [IO.File]::ReadAllText($mcp,$utf8) -ceq ($mcpAfter+'external') -and [IO.File]::ReadAllText($journal,$utf8) -ceq $journalBefore) 'no partial rollback before external-edit refusal'
 [IO.File]::WriteAllText($mcp,$mcpAfter,$utf8)
 $null=& $installer -HostName Cursor -ProjectPath $project -Binary $exe -BrainId cursor-install -EnableCapture -EnableFactRecall -EnableFactPromotion
 Check (-not [IO.File]::Exists($journal) -and [IO.File]::ReadAllText($hooks,$utf8) -ceq $hookBefore -and [IO.File]::ReadAllText($mcp,$utf8) -ceq $mcpBefore) 'Cursor recovery restores complete before images then idempotent install'
 $owner=Load $ownerPath

 # Owned modification refuses before touching the edited file or other settings.
 $state=Load $hooks;$state.hooks.beforeSubmitPrompt[0].command='echo edited-owner';Save $hooks $state
 $edited=[IO.File]::ReadAllText($hooks,$utf8);$beforeMcp=[IO.File]::ReadAllText($mcp,$utf8)
 Reject {& $installer -Action Uninstall -HostName Cursor -ProjectPath $project} 'modified owned command refuses uninstall'
 Check ([IO.File]::ReadAllText($hooks,$utf8) -ceq $edited -and [IO.File]::ReadAllText($mcp,$utf8) -ceq $beforeMcp) 'refusal preserves full configs'
 $state.hooks.beforeSubmitPrompt[0]=@($owner.entries|Where-Object {$_.event -ceq 'beforeSubmitPrompt'})[0].group;Save $hooks $state
 $null=& $installer -Action Uninstall -HostName Cursor -ProjectPath $project
 $state=Load $hooks;$m=Load $mcp
 Check (@($state.hooks.sessionStart).Count -eq 1 -and (J $state.hooks.sessionStart[0]) -ceq (J $external)) 'uninstall preserves only unrelated session handler'
 Check ((Has $m.mcpServers 'external') -and -not (Has $m.mcpServers $owner.mcp.name)) 'uninstall removes only owned MCP'
 Check (-not (Load $configPath).enabled) 'uninstall disables native config'
 # Malformed version is never normalized into an accepted schema.
 $bad=Join-Path $root 'invalid-version';[void][IO.Directory]::CreateDirectory($bad)
 $badHooks=Join-Path $bad '.cursor\hooks.json';Save $badHooks ([pscustomobject]@{version=2;hooks=[pscustomobject]@{}})
 $badRaw=[IO.File]::ReadAllText($badHooks,$utf8)
 Reject {& $installer -HostName Cursor -ProjectPath $bad -Binary $exe -BrainId never-created} 'unsupported Cursor version rejected'
 Check ([IO.File]::ReadAllText($badHooks,$utf8) -ceq $badRaw -and -not [IO.File]::Exists((Join-Path $root 'Qbrain\brains\never-created\brain.db'))) 'invalid version before database initialization'
 $passed=$true
}finally{
 if(-not $passed){
  Get-ChildItem -LiteralPath $root -Recurse -Filter '*.json' -ErrorAction SilentlyContinue | ForEach-Object {
   $relative=$_.FullName.Substring($root.Length).TrimStart('\','/')
   $dest=Join-Path ($reportPath+'.partial') $relative;[void][IO.Directory]::CreateDirectory((Split-Path $dest -Parent));[IO.File]::Copy($_.FullName,$dest,$true)
  }
 }
 $data=[pscustomobject]@{schema='qbrain-n48y-install-v1';passed=$passed;checks=@($script:checks);check_count=$script:checks.Count;commands=@($script:commands);powershell=$PSVersionTable.PSVersion.ToString();real_cursor_session=$false;binary_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()}
 [void][IO.Directory]::CreateDirectory((Split-Path $reportPath -Parent));[IO.File]::WriteAllText($reportPath,(J $data),$utf8)
 Set-Location $cwd
 Get-ChildItem Env:|Where-Object {$_.Name -match '^(QBRAIN|PG|CURSOR|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')}|ForEach-Object {[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
 foreach($k in $old.Keys){[Environment]::SetEnvironmentVariable($k,$old[$k],'Process')}
 if(Test-Path -LiteralPath $root){Remove-Item -LiteralPath $root -Recurse -Force}
}
