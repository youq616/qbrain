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
# Metadata-only native queries; never toggle directory flags or probe by writing.
# Keep legacy IDs only where every existing directory is provably insensitive.
if(-not ('Qbrain.N47V.PathGuard' -as [type])){
 Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
namespace Qbrain.N47V {
 public static class PathGuard {
  [StructLayout(LayoutKind.Sequential)]
  private struct AttributeTag { public uint Attributes; public uint Tag; }
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true, ExactSpelling=true)]
  private static extern SafeFileHandle CreateFileW(string path, uint access,
   uint share, IntPtr security, uint creation, uint flags, IntPtr template);
  [DllImport("kernel32.dll", SetLastError=true, EntryPoint="GetFileInformationByHandleEx")]
  [return: MarshalAs(UnmanagedType.Bool)]
  private static extern bool GetAttributes(SafeFileHandle handle, int info,
   out AttributeTag value, uint size);
  [DllImport("kernel32.dll", SetLastError=true, EntryPoint="GetFileInformationByHandleEx")]
  [return: MarshalAs(UnmanagedType.Bool)]
  private static extern bool GetCaseInfo(SafeFileHandle handle, int info,
   out uint value, uint size);
  public static void CheckDirectory(string path) {
   // FILE_READ_ATTRIBUTES; share read/write/delete; OPEN_EXISTING;
   // FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT.
   using(SafeFileHandle handle=CreateFileW(path, 0x80, 7, IntPtr.Zero, 3,
                                         0x02200000, IntPtr.Zero)) {
    if(handle.IsInvalid) throw new InvalidOperationException(
     "Cannot verify directory case sensitivity; operation refused.",
     new Win32Exception(Marshal.GetLastWin32Error()));
    AttributeTag attributes;
    if(!GetAttributes(handle, 9, out attributes, 8))
     throw new InvalidOperationException("Cannot verify directory attributes; operation refused.",
      new Win32Exception(Marshal.GetLastWin32Error()));
    if((attributes.Attributes & 0x400)!=0 || (attributes.Attributes & 0x10)==0)
     throw new InvalidOperationException("Reparse or non-directory path; operation refused.");
    uint flags;
    if(!GetCaseInfo(handle, 23, out flags, 4))
     throw new InvalidOperationException("Cannot verify directory case sensitivity; operation refused.",
      new Win32Exception(Marshal.GetLastWin32Error()));
    if(flags!=0) throw new InvalidOperationException(
     "Case-sensitive directories are not supported for integration configuration.");
   }
  }
 }
}
'@
}
function Safe([string]$p){
 $p=[IO.Path]::GetFullPath($p)
 $at=$p
 while($at){
  if(Test-Path -LiteralPath $at){
   $item=Get-Item -LiteralPath $at -Force
   if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Reparse paths are not supported for integration configuration.'}
   if($item.PSIsContainer){[Qbrain.N47V.PathGuard]::CheckDirectory($at)}
  }
  $parent=Split-Path -Parent $at;if($parent -eq $at){break};$at=$parent
 }
 return $p
}
function Raw([string]$p,[int]$limit=2097152){
 $null=Safe $p
 if(-not [IO.File]::Exists($p)){return $null}
 if((Get-Item -LiteralPath $p).Length -gt $limit){throw 'Configuration exceeds its byte limit.'}
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
 $h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash($utf8.GetBytes($s)))).Replace('-','').ToLowerInvariant()}
 finally{$h.Dispose()}
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
# Known unsupported binary paths must fail before creating the owned directory.
if($Action -eq 'Install' -and $Binary){$null=Safe ((Resolve-Path -LiteralPath $Binary).ProviderPath)}
# Version 1 stores multiple text images; its envelope is not one config file.
$journalLimit=33554432
function Exact-Fields($o,[string[]]$names){
 if($null -eq $o -or $o -isnot [pscustomobject]){throw 'Invalid recovery journal object.'}
 $actual=@($o.PSObject.Properties.Name)
 if($actual.Count -ne $names.Count){throw 'Invalid recovery journal fields.'}
 foreach($name in $actual){if($name -cnotin $names){throw 'Invalid recovery journal fields.'}}
}
function Check-Destination([string]$p){
 foreach($q in @($p,($p+'.tmp'))){
  $null=Safe $q
  if([IO.Directory]::Exists($q)){throw 'A transaction destination is a directory.'}
 }
 $parent=Split-Path -Parent $p
 while($parent){
  if([IO.File]::Exists($parent)){throw 'A transaction parent is a file.'}
  $next=Split-Path -Parent $parent;if($next -eq $parent){break};$parent=$next
 }
}
function Validate-Journal($pending){
 Exact-Fields $pending @('version','changes')
 if(($pending.version -isnot [int] -and $pending.version -isnot [long]) -or $pending.version -ne 1){throw 'Invalid recovery journal version.'}
 if($pending.changes -isnot [Array] -or $pending.changes.Count -lt 1 -or $pending.changes.Count -gt $allowed.Count){throw 'Invalid recovery journal changes.'}
 $seen=@()
 foreach($c in $pending.changes){
  Exact-Fields $c @('path','before','after')
  if($c.path -isnot [string] -or $c.path -cnotin $allowed){throw 'Recovery journal contains an unowned path.'}
  if($c.path -in $seen){throw 'Recovery journal repeats a path.'};$seen+=,$c.path
  foreach($key in @('before','after')){
   $image=$c.$key
   if($null -ne $image){
    if($image -isnot [string]){throw 'Recovery images must be strings or null.'}
    # Strict UTF-8 encoding rejects invalid surrogates before the first write.
    if($utf8.GetByteCount($image) -gt 2097152){throw 'Recovery image exceeds the 2 MiB limit.'}
   }
  }
 }
 # All schema/image checks finish before destination checks or rollback writes.
 foreach($c in $pending.changes){Check-Destination $c.path}
}
function Check-Current($pending){
 foreach($c in $pending.changes){
  $now=Raw $c.path
  if($now -cne $c.before -and $now -cne $c.after){throw 'External edit prevents recovery; no files changed.'}
 }
}
function Input-Image($images,[string]$p){
 if($null -ne $images){return $images[$p]}
 return Raw $p
}
function Matching($o,$images=$null){
 try {
  $current=Parse (Input-Image $images $target)
  if(-not (Has $current 'hooks')){return $false}
  foreach($e in $o.entries){
   if(-not (Has $current.hooks $e.event)){return $false}
   $matches=@($current.hooks.($e.event)|Where-Object {Same $_ $e.group})
   if($matches.Count -ne 1){return $false}
  }
  if($hostKey -eq 'claude'){
   $m=Parse (Input-Image $images $mcpPath);return (Has $m 'mcpServers') -and (Has $m.mcpServers $o.mcp.name) -and (Same $m.mcpServers.($o.mcp.name) $o.mcp.definition)
  }
  return ([string](Input-Image $images $mcpPath)).Contains([string]$o.mcp.block)
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
  $pendingText=Raw $journal $journalLimit
  # PowerShell 7 may enumerate a one-element JSON array into an object.
  if([string]::IsNullOrWhiteSpace($pendingText) -or -not $pendingText.TrimStart().StartsWith('{')){throw 'Recovery journal must be a JSON object.'}
  $pending=Parse $pendingText
  Validate-Journal $pending
  Check-Current $pending
  foreach($c in $pending.changes){Write-Atomic $c.path $c.before}
  [IO.File]::Delete($journal)
 }
 # Bind parsed input, journal before images and backup to the same reads.
 # A later Raw() inside Change would incorrectly bless an intervening edit.
 $initial=@{};$initial[$ownerPath]=Raw $ownerPath
 $owner=if($null -ne $initial[$ownerPath]){Parse $initial[$ownerPath]}else{$null}
 $active=$null -ne $owner -and (Has $owner 'active') -and $owner.active
 if($Action -eq 'Uninstall' -and -not $active){return}
 foreach($p in $allowed){if($p -cne $ownerPath){$initial[$p]=Raw $p}}
 if($active -and -not (Matching $owner $initial)){throw 'An owned hook or MCP definition was edited; refusing to overwrite.'}
 $rawTarget=$initial[$target]
 if($null -ne $rawTarget -and [string]::IsNullOrWhiteSpace($rawTarget)){throw 'Existing JSON settings are empty.'}
 $settings=Parse $rawTarget
 if(-not (Has $settings 'hooks')){Set-Key $settings 'hooks' ([pscustomobject]@{})}
 if($settings.hooks -isnot [pscustomobject]){throw 'hooks must be an object.'}
 $rawMcp=$initial[$mcpPath]
 if($hostKey -eq 'claude'){
  if($null -ne $rawMcp -and [string]::IsNullOrWhiteSpace($rawMcp)){throw 'Existing MCP settings are empty.'}
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
 function Change([string]$p,[AllowNull()]$s){[void]$changes.Add([pscustomobject]@{path=$p;before=$initial[$p];after=$s})}
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
  Change $bridgePath (Raw $bridgeSource);Change $cfgPath (Json $cfg);Change $ownerPath (Json $newOwner)
 }else{
  $cfg=Parse $initial[$cfgPath];Set-Key $cfg 'enabled' $false;$owner.active=$false
  Change $cfgPath (Json $cfg);Change $ownerPath (Json $owner)
 }
 Change $target (Json $settings)
 if($hostKey -eq 'claude'){Change $mcpPath (Json $mcp)}else{Change $mcpPath $rawMcp}
 # Preflight the actual journal before brain initialization or backup creation.
 $pending=[pscustomobject]@{version=1;changes=@($changes)}
 Validate-Journal $pending
 $pendingText=Json $pending
 if($utf8.GetByteCount($pendingText) -gt $journalLimit){throw 'Recovery journal exceeds the 32 MiB limit.'}
 $stamp=[Guid]::NewGuid().ToString('N')
 $backupPath=Join-Path $owned ('settings-backup-'+$stamp+'.json')
 Check-Destination $journal;Check-Destination $backupPath
 foreach($c in $changes){if((Raw $c.path) -cne $c.before){throw 'Configuration changed during install.'}}
 if($Action -eq 'Install'){
  # All external file validation above precedes brain creation. Installation never
  # selects this brain globally. Capture remains inert until separately opted in.
  $result=& $bridgeSource -FilePath $exe -ArgumentList @('init','--brain',$BrainId,'--no-default')
  if($result.ExitCode -ne 0){throw 'Project brain initialization failed.'}
  if($EnableCapture){
   $result=& $bridgeSource -FilePath $exe -ArgumentList @('config','set','memory.writeback','salient','--brain',$BrainId,'--local')
   if($result.ExitCode -ne 0){throw 'Capture opt-in failed.'}
  }
 }
 # Recheck after brain initialization, before producing any backup/journal.
 foreach($c in $changes){if((Raw $c.path) -cne $c.before){throw 'Configuration changed during install.'}}
 Write-Atomic $backupPath (Json ([pscustomobject]@{settings=$initial[$target];mcp=$initial[$mcpPath]}))
 Write-Atomic $journal $pendingText
 foreach($c in $changes){Write-Atomic $c.path $c.after}
 [IO.File]::Delete($journal)
 Json ([pscustomobject]@{action=$Action;project=$project;host=$hostKey;host_consumption_confirmed=$false})
}finally{$lock.Dispose()}
