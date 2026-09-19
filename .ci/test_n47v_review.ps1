# Separate boundary probes of the unmodified N47V installer, native Windows only.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Installer,
 [Parameter(Mandatory=$true)][string]$Report
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'Native Windows required.'}
$scriptPath=(Resolve-Path -LiteralPath $Installer).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
if(Test-Path -LiteralPath $reportPath){throw 'Report already exists.'}
$utf8=New-Object Text.UTF8Encoding($false,$true)
function Digest([byte[]]$bytes){$h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
$installerHash=Digest ([IO.File]::ReadAllBytes($scriptPath))
if($installerHash -cnotin @('b2c6b64a4ad33adb9ab7b4d436c2a3427191fec7965482cfa97c2a824f6da64b','8800b24d1eda8f4aefc85e64c9ded46406983c03271f2365acb9014ccbb2d860')){throw 'Wrong installer bytes.'}
$root=Join-Path ([IO.Path]::GetTempPath()) ('n47v-review-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
$data=Join-Path $root 'data';[void][IO.Directory]::CreateDirectory($data)
$normal=Join-Path $root 'ordinary';[void][IO.Directory]::CreateDirectory($normal)
$linkTarget=Join-Path $root 'junction-target';[void][IO.Directory]::CreateDirectory($linkTarget)
[IO.File]::WriteAllText((Join-Path $linkTarget 'keep.txt'),'KEEP',$utf8)
$file=Join-Path $root 'plain-file';[IO.File]::WriteAllText($file,'file',$utf8)
$saved=@{};$checks=New-Object System.Collections.ArrayList;$complete=$false;$failure=''
Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')} | ForEach-Object {$saved[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
foreach($key in @('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')){[Environment]::SetEnvironmentVariable($key,$data,'Process')}
function Check([bool]$ok,[string]$name){[void]$checks.Add([pscustomobject]@{name=$name;passed=$ok});if(-not $ok){throw $name};Write-Host ('PASS '+$checks.Count+' : '+$name)}
function Snap {
 $rows=New-Object 'System.Collections.Generic.List[string]'
 foreach($p in [IO.Directory]::EnumerateDirectories($root,'*',[IO.SearchOption]::AllDirectories)){$rows.Add('D|'+$p)}
 foreach($p in [IO.Directory]::EnumerateFiles($root,'*',[IO.SearchOption]::AllDirectories)){$rows.Add('F|'+$p+'|'+(Digest ([IO.File]::ReadAllBytes($p))))}
 $rows.Sort([StringComparer]::Ordinal);return Digest ($utf8.GetBytes(($rows -join "`n")))
}
try {
 $before=Snap
 $status=(& $scriptPath -Action Status -HostName Claude -ProjectPath $normal)|ConvertFrom-Json
 [Qbrain.N47V.PathGuard]::CheckDirectory($normal)
 Check (-not $status.installed) 'ordinary metadata query succeeds without installation'
 $err='';try{[Qbrain.N47V.PathGuard]::CheckDirectory($file)}catch{$err=$_.Exception.ToString()}
 Check ($err.Contains('Reparse or non-directory path')) 'native regular file rejected as a directory'
 $err='';try{[Qbrain.N47V.PathGuard]::CheckDirectory((Join-Path $root 'missing'))}catch{$err=$_.Exception.ToString()}
 Check ($err.Contains('Cannot verify directory case sensitivity')) 'missing native metadata handle rejected'
 for($i=0;$i -lt 32;$i++){try{[Qbrain.N47V.PathGuard]::CheckDirectory($file)}catch{};[Qbrain.N47V.PathGuard]::CheckDirectory($normal)}
 Check ((Snap) -ceq $before) 'repeated native success and error paths preserve all fixture state'
 foreach($kind in @('file','junction')){
  foreach($action in @('Status','Install','Uninstall')){
   $victim=Join-Path $root ($kind+'-'+$action);[void][IO.Directory]::CreateDirectory($victim)
   $before=Snap
   $global:N47VReviewSwap=[pscustomobject]@{path=$victim;kind=$kind;target=$linkTarget;armed=$true;hits=0}
   function Get-Item {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][string]$LiteralPath,[switch]$Force)
    $item=Microsoft.PowerShell.Management\Get-Item @PSBoundParameters
    if($global:N47VReviewSwap.armed -and $LiteralPath -ceq $global:N47VReviewSwap.path){
     $attributes=$item.Attributes;$isDirectory=$item.PSIsContainer
     $global:N47VReviewSwap.armed=$false;$global:N47VReviewSwap.hits++
     [IO.Directory]::Delete($LiteralPath)
     if($global:N47VReviewSwap.kind -ceq 'file'){[IO.File]::WriteAllText($LiteralPath,'external-substitution')}
     else{$null=New-Item -ItemType Junction -Path $LiteralPath -Target $global:N47VReviewSwap.target}
     # Return the metadata actually read before this deliberate external change.
     return [pscustomobject]@{Attributes=$attributes;PSIsContainer=$isDirectory}
    }
    return $item
   }
   $err='';$hits=0
   try{try{$null=& $scriptPath -Action $action -HostName Claude -ProjectPath $victim}catch{$err=$_.Exception.ToString()};$hits=$global:N47VReviewSwap.hits}
   finally{
    Remove-Item Function:Get-Item -ErrorAction SilentlyContinue
    Remove-Variable N47VReviewSwap -Scope Global -ErrorAction SilentlyContinue
    if($kind -ceq 'file'){if([IO.File]::Exists($victim)){[IO.File]::Delete($victim)}}
    else{if([IO.Directory]::Exists($victim)){[IO.Directory]::Delete($victim)}}
    [void][IO.Directory]::CreateDirectory($victim)
   }
   Check ($hits -eq 1) ($kind+'/'+$action+' substituted after exactly one metadata read')
   Check ($err.Contains('Reparse or non-directory path')) ($kind+'/'+$action+' native guard rejects substituted type')
   Check ((Snap) -ceq $before) ($kind+'/'+$action+' restores test substitution without application changes')
  }
 }
 $complete=$checks.Count -eq 22
}catch{$failure=$_.Exception.Message}
finally{
 $source=(& git -C (Join-Path $PSScriptRoot '..') rev-parse HEAD).Trim()
 $value=[pscustomobject]@{schema='qbrain-n47v-boundary-review-v1';result=$(if($complete){'PASS'}else{'FAIL'});source_commit=$source;shell_major=$PSVersionTable.PSVersion.Major;powershell=$PSVersionTable.PSVersion.ToString();native_windows=$true;installer_sha256=$installerHash;script_sha256=(Digest ([IO.File]::ReadAllBytes($PSCommandPath)));checks=@($checks);count=$checks.Count;failure=$failure;real_client_verified=$false;production_changes=$false}
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $reportPath))
 $bytes=$utf8.GetBytes((ConvertTo-Json -InputObject $value -Depth 10))
 $stream=[IO.File]::Open($reportPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
 try{$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
 foreach($key in @('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')){[Environment]::SetEnvironmentVariable($key,$null,'Process')}
 foreach($key in $saved.Keys){[Environment]::SetEnvironmentVariable($key,$saved[$key],'Process')}
 Remove-Item -LiteralPath $root -Recurse -Force
}
if(-not $complete){Write-Error ('N47V separate review failed: '+$failure);exit 1}
