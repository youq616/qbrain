# Project-local hooks, explicit ownership, recoverable file transaction. No admin needed.
[CmdletBinding()]
param(
 [ValidateSet('Install','Uninstall','Status')][string]$Action='Install',
 [Parameter(Mandatory=$true)][ValidateSet('Claude','Codex')][string]$HostName,
 [Parameter(Mandatory=$true)][string]$ProjectPath,
 [string]$Binary='', [string]$BrainId='',
 [switch]$EnableCapture,
 [switch]$EnableFactRecall,
 [switch]$EnableFactPromotion
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($Action -eq 'Install' -and $EnableFactPromotion -and -not $EnableCapture){throw 'Fact promotion requires explicit -EnableCapture.'}
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'Native Windows is required.'}
$utf8=New-Object Text.UTF8Encoding($false,$true)
function Safe([string]$p){
 $p=[IO.Path]::GetFullPath($p)
 $at=$p
 while($at){
  if(Test-Path -LiteralPath $at){
   $item=Get-Item -LiteralPath $at -Force
   if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Reparse paths are not supported for integration configuration.'}
  }
  $parent=Split-Path -Parent $at;if($parent -eq $at){break};$at=$parent
 }
 return $p
}
function Raw([string]$p){
 $null=Safe $p
 if(-not [IO.File]::Exists($p)){return $null}
 if((Get-Item -LiteralPath $p).Length -gt 2097152){throw 'Configuration exceeds the 2 MiB limit.'}
 $text=[IO.File]::ReadAllText($p,$utf8)
 return $text
}
function Json($value){return ConvertTo-Json -InputObject $value -Depth 80 -Compress}
function Parse([string]$s){
 if($null -eq $s -or $s -eq ''){return [pscustomobject]@{}}
 $j=ConvertFrom-Json -InputObject $s
 if($null -eq $j -or $j -isnot [pscustomobject]){throw 'Expected an object configuration.'};return $j
}
function Has($o,[string]$k){return $null -ne $o.PSObject.Properties[$k]}
function Set-Key($o,[string]$k,$v){$o | Add-Member -NotePropertyName $k -NotePropertyValue $v -Force}
function Hash([string]$s){
 $h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash($utf8.GetBytes($s)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}
}
function Write-Atomic([string]$p,[AllowNull()]$s){
 $null=Safe $p;$temp=$p+'.tmp';$null=Safe $temp
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $p))
 if($null -eq $s){if([IO.File]::Exists($p)){[IO.File]::Delete($p)};return}
 [IO.File]::WriteAllText($temp,$s,$utf8)
 if([IO.File]::Exists($p)){[IO.File]::Replace($temp,$p,[System.Management.Automation.Language.NullString]::Value)}else{[IO.File]::Move($temp,$p)}
}
function Same($a,$b){return (Json $a) -ceq (Json $b)}
$project=Safe ((Resolve-Path -LiteralPath $ProjectPath).ProviderPath)
$hostKey=$HostName.ToLowerInvariant()
$id=(Hash ($hostKey+'|'+$project.ToLowerInvariant())).Substring(0,24)
$owned=Safe (Join-Path $env:LOCALAPPDATA ('Qbrain\integrations\'+$id))
$ownerPath=Join-Path $owned 'installation.json';$cfgPath=Join-Path $owned 'config.json'
$journal=Join-Path $owned 'pending.json';$bridgePath=Join-Path $owned 'Invoke-QbrainJson.ps1'
$target=if($hostKey -eq 'claude'){Join-Path $project '.claude\settings.local.json'}else{Join-Path $project '.codex\hooks.json'}
$mcpPath=if($hostKey -eq 'claude'){Join-Path $project '.mcp.json'}else{Join-Path $project '.codex\config.toml'}
$allowed=@($target,$mcpPath,$ownerPath,$cfgPath,$bridgePath)
foreach($p in $allowed){$null=Safe $p}
function Matching($o){
 try {
  $current=Parse (Raw $target)
  if(-not (Has $current 'hooks')){return $false}
  foreach($e in $o.entries){
   if(-not (Has $current.hooks $e.event)){return $false}
   $matches=@($current.hooks.($e.event)|Where-Object {Same $_ $e.group})
   if($matches.Count -ne 1){return $false}
  }
  if($hostKey -eq 'claude'){
   $m=Parse (Raw $mcpPath);return (Has $m 'mcpServers') -and (Has $m.mcpServers $o.mcp.name) -and (Same $m.mcpServers.($o.mcp.name) $o.mcp.definition)
  }
  return ([string](Raw $mcpPath)).Contains([string]$o.mcp.block)
 }catch{return $false}
}
if($Action -eq 'Status'){
 $o=if([IO.File]::Exists($ownerPath)){Parse (Raw $ownerPath)}else{$null}
 $installed=$null -ne $o -and (Has $o 'active') -and $o.active
 $factEnabled=$false;$promotionEnabled=$false
 if($installed -and [IO.File]::Exists($cfgPath)){
  try{
   $c=Parse (Raw $cfgPath);$factEnabled=(Has $c 'fact_recall') -and ($c.fact_recall -is [bool]) -and $c.fact_recall
   $promotionEnabled=(Has $c 'fact_promotion') -and ($c.fact_promotion -is [bool]) -and $c.fact_promotion -and (Has $c 'capture') -and ($c.capture -is [bool]) -and $c.capture -and (Has $c 'extraction') -and ($c.extraction -ceq 'local') -and (Has $c 'enabled') -and ($c.enabled -is [bool]) -and $c.enabled
  }catch{$factEnabled=$false;$promotionEnabled=$false}
 }
 Json ([pscustomobject]@{fact_promotion_enabled=$promotionEnabled;fact_recall_enabled=$factEnabled;installed=$installed;configuration_matches=($installed -and (Matching $o));recovery_required=[IO.File]::Exists($journal);host_consumption_confirmed=$false})
 return
}
[void][IO.Directory]::CreateDirectory($owned)
# Exclusive installer lock; a crash releases the operating system handle.
$lockPath=Join-Path $owned 'install.lock';$null=Safe $lockPath
$lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
try {
 if([IO.File]::Exists($journal)){
  $pending=Parse (Raw $journal)
  if($pending.version -ne 1 -or @($pending.changes).Count -gt 8){throw 'Invalid recovery journal.'}
  foreach($c in $pending.changes){
   if($c.path -cnotin $allowed){throw 'Recovery journal contains an unowned path.'}
   $now=Raw $c.path
   if($now -cne $c.before -and $now -cne $c.after){throw 'External edit prevents recovery; no files changed.'}
  }
  foreach($c in $pending.changes){Write-Atomic $c.path $c.before}
  [IO.File]::Delete($journal)
 }
 $owner=if([IO.File]::Exists($ownerPath)){Parse (Raw $ownerPath)}else{$null}
 $active=$null -ne $owner -and (Has $owner 'active') -and $owner.active
 if($active -and -not (Matching $owner)){throw 'An owned hook or MCP definition was edited; refusing to overwrite.'}
 if($Action -eq 'Uninstall' -and -not $active){return}
 $rawTarget=Raw $target
 if([IO.File]::Exists($target) -and [string]::IsNullOrWhiteSpace($rawTarget)){throw 'Existing JSON settings are empty.'}
 $settings=Parse $rawTarget
 if(-not (Has $settings 'hooks')){Set-Key $settings 'hooks' ([pscustomobject]@{})}
 if($settings.hooks -isnot [pscustomobject]){throw 'hooks must be an object.'}
 $rawMcp=Raw $mcpPath
 if($hostKey -eq 'claude'){
  if([IO.File]::Exists($mcpPath) -and [string]::IsNullOrWhiteSpace($rawMcp)){throw 'Existing MCP settings are empty.'}
  $mcp=Parse $rawMcp
  if(-not (Has $mcp 'mcpServers')){Set-Key $mcp 'mcpServers' ([pscustomobject]@{})}
  if($mcp.mcpServers -isnot [pscustomobject]){throw 'mcpServers must be an object.'}
 }
 # Remove exactly one identical owned group, retaining unrelated entries and edits.
 if($active){
  foreach($e in $owner.entries){
   $rest=@($settings.hooks.($e.event)|Where-Object {-not (Same $_ $e.group)})
   if($rest.Count){Set-Key $settings.hooks $e.event $rest}else{$settings.hooks.PSObject.Properties.Remove($e.event)}
  }
  if($hostKey -eq 'claude'){$mcp.mcpServers.PSObject.Properties.Remove($owner.mcp.name)}
  else{$rawMcp=$rawMcp.Replace([string]$owner.mcp.block,'')}
 }
 $changes=New-Object System.Collections.ArrayList
 function Change([string]$p,[AllowNull()]$s){[void]$changes.Add([pscustomobject]@{path=$p;before=(Raw $p);after=$s})}
 if($Action -eq 'Install'){
  if(-not $Binary){throw 'Binary is required for Install.'}
  $exe=Safe ((Resolve-Path -LiteralPath $Binary).ProviderPath)
  if([IO.Path]::GetExtension($exe) -ine '.exe'){throw 'Binary must be a native executable.'}
  if(-not $BrainId){$BrainId='project-'+$id}
  if($BrainId -cnotmatch '^[a-z0-9][a-z0-9_-]{0,63}$'){throw 'Use a safe lowercase brain identifier.'}
  $bridgeSource=Join-Path $PSScriptRoot 'Invoke-QbrainJson.ps1'
  $cfg=[pscustomobject]@{version=1;host=$hostKey;project_root=$project;brain_id=$BrainId;source_id='default';enabled=$true;capture=[bool]$EnableCapture;fact_recall=[bool]$EnableFactRecall;fact_promotion=[bool]$EnableFactPromotion;extraction='local';recall_bytes=4096;max_items=8}
  $entry=[pscustomobject]@{type='command';command=$exe;args=@('hook','--config',$cfgPath);timeout=10}
  if($hostKey -eq 'codex'){
   function Literal([string]$s){return "'"+$s.Replace("'","''")+"'"}
   $ps="[Console]::InputEncoding=New-Object Text.UTF8Encoding(`$false);[Console]::OutputEncoding=New-Object Text.UTF8Encoding(`$false);`$r=& "+(Literal $bridgePath)+' -FilePath '+(Literal $exe)+" -ArgumentList @('hook','--config',"+(Literal $cfgPath)+") -InputJson ([Console]::In.ReadToEnd());[Console]::Write(`$r.Stdout)"
   $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($ps))
   $cmd='powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand '+$encoded
   $entry=[pscustomobject]@{type='command';command=$cmd;commandWindows=$cmd;timeout=10}
  }
  $entries=@()
  foreach($ev in @('SessionStart','UserPromptSubmit','Stop','PreCompact','SessionEnd')){
   $handler=Parse (Json $entry);if($ev -eq 'SessionEnd'){$handler.timeout=3}
   $group=[pscustomobject]@{hooks=@($handler)}
   $old=@();if(Has $settings.hooks $ev){$old=@($settings.hooks.($ev))}
   Set-Key $settings.hooks $ev @($old+@($group))
   $entries+=,[pscustomobject]@{event=$ev;group=$group}
  }
  $name='qbrain_memory_'+$id
  $definition=[pscustomobject]@{command=$exe;args=@('serve','--brain',$BrainId,'--tool-profile','memory')}
  $mcpOwner=[pscustomobject]@{name=$name;definition=$definition;block=''}
  if($hostKey -eq 'claude'){
   if(Has $mcp.mcpServers $name){throw 'MCP name collision.'};Set-Key $mcp.mcpServers $name $definition
  }else{
   # JSON basic strings are valid TOML basic strings; no interpolation of repo text.
   if(([string]$rawMcp).Contains($name)){throw 'MCP name collision.'}
   $block="`n# Qbrain managed $id`n[mcp_servers.$name]`ncommand = "+(Json $exe)+"`nargs = "+(Json $definition.args)+"`n# Qbrain end $id`n"
   $mcpOwner.block=$block;$rawMcp=[string]$rawMcp+$block
  }
  $newOwner=[pscustomobject]@{version=1;active=$true;host=$hostKey;project_root=$project;entries=$entries;mcp=$mcpOwner}
  # All external file validation above precedes brain creation. Installation never
  # selects this brain globally. Capture remains inert until separately opted in.
  $result=& $bridgeSource -FilePath $exe -ArgumentList @('init','--brain',$BrainId,'--no-default')
  if($result.ExitCode -ne 0){throw 'Project brain initialization failed.'}
  if($EnableCapture){
   $result=& $bridgeSource -FilePath $exe -ArgumentList @('config','set','memory.writeback','salient','--brain',$BrainId,'--local')
   if($result.ExitCode -ne 0){throw 'Capture opt-in failed.'}
  }
  Change $bridgePath (Raw $bridgeSource);Change $cfgPath (Json $cfg);Change $ownerPath (Json $newOwner)
 }else{
  $cfg=Parse (Raw $cfgPath);Set-Key $cfg 'enabled' $false;$owner.active=$false
  Change $cfgPath (Json $cfg);Change $ownerPath (Json $owner)
 }
 Change $target (Json $settings)
 if($hostKey -eq 'claude'){Change $mcpPath (Json $mcp)}else{Change $mcpPath $rawMcp}
 $stamp=[Guid]::NewGuid().ToString('N')
 Write-Atomic (Join-Path $owned ('settings-backup-'+$stamp+'.json')) (Json ([pscustomobject]@{settings=$rawTarget;mcp=(Raw $mcpPath)}))
 # Compare-before-write to catch edits occurring after initial validation.
 foreach($c in $changes){if((Raw $c.path) -cne $c.before){throw 'Configuration changed during install.'}}
 Write-Atomic $journal (Json ([pscustomobject]@{version=1;changes=@($changes)}))
 foreach($c in $changes){Write-Atomic $c.path $c.after}
 [IO.File]::Delete($journal)
 Json ([pscustomobject]@{action=$Action;project=$project;host=$hostKey;host_consumption_confirmed=$false})
}finally{$lock.Dispose()}
