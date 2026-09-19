# Native NTFS case-sensitive fixtures. Never modifies a real project or OS setting.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Binary,
 [Parameter(Mandatory=$true)][string]$BaselineInstaller,
 [Parameter(Mandatory=$true)][string]$Report,
 [string]$Installer=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'Native Windows required.'}
if(-not $Installer){$Installer=Join-Path $PSScriptRoot '..\scripts\Install-QbrainMemory.ps1'}
$installerPath=(Resolve-Path -LiteralPath $Installer).ProviderPath
$prior=(Resolve-Path -LiteralPath $BaselineInstaller).ProviderPath
$exe=(Resolve-Path -LiteralPath $Binary).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
$utf8=New-Object Text.UTF8Encoding($false,$true)
$fsutil=Join-Path ([Environment]::GetFolderPath('System')) 'fsutil.exe'
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class N47VFixture {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true,ExactSpelling=true)]
 [return:MarshalAs(UnmanagedType.Bool)]
 private static extern bool CreateDirectoryW(string path, IntPtr security);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true,ExactSpelling=true)]
 private static extern SafeFileHandle CreateFileW(string p,uint a,uint s,IntPtr x,uint c,uint f,IntPtr t);
 [DllImport("kernel32.dll",SetLastError=true)]
 [return:MarshalAs(UnmanagedType.Bool)]
 private static extern bool GetFileInformationByHandleEx(SafeFileHandle h,int i,out uint f,uint n);
 public static void Make(string path) {
  if(!CreateDirectoryW(path,IntPtr.Zero)) throw new Win32Exception(Marshal.GetLastWin32Error());
 }
 public static uint Flags(string path) {
  using(var h=CreateFileW(path,0x80,7,IntPtr.Zero,3,0x02200000,IntPtr.Zero)) {
   uint f;
   if(h.IsInvalid || !GetFileInformationByHandleEx(h,23,out f,4))
    throw new Win32Exception(Marshal.GetLastWin32Error());
   return f;
  }
 }
 public static SafeFileHandle Hold(string path) {
  var h=CreateFileW(path,0x80,0,IntPtr.Zero,3,0x02200000,IntPtr.Zero);
  if(h.IsInvalid){h.Dispose();throw new Win32Exception(Marshal.GetLastWin32Error());}
  return h;
 }
}
'@
$top=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-case-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($top)
$data=Join-Path $top 'appdata';[void][IO.Directory]::CreateDirectory($data)
$old=@{}
Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')} | ForEach-Object {
 $old[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')
}
$env:HOME=$data;$env:LOCALAPPDATA=$data;$env:USERPROFILE=$data;$env:APPDATA=$data
$results=New-Object System.Collections.ArrayList
$flagsLog=New-Object System.Collections.ArrayList
$starting=Get-Location;$success=$false
function Need([bool]$ok,[string]$name){
 [void]$results.Add([pscustomobject]@{name=$name;passed=$ok})
 if(-not $ok){throw $name};Write-Host ('PASS '+$results.Count+' : '+$name)
}
function Flag([string]$path,[bool]$enabled){
 $mode=if($enabled){'enable'}else{'disable'}
 $text=& $fsutil file setCaseSensitiveInfo $path $mode 2>&1
 if($LASTEXITCODE -ne 0){throw ('Required NTFS fixture unavailable: '+($text -join ' '))}
 $value=[N47VFixture]::Flags($path)
 if($value -ne [int]$enabled){throw 'NTFS flag did not take effect.'}
 [void]$flagsLog.Add([pscustomobject]@{path=$path;flags=$value;fsutil_output=($text -join "`n")})
}
function New-N47VDirectory([string]$name){$p=Join-Path $top $name;[void][IO.Directory]::CreateDirectory($p);return $p}
function Hash([byte[]]$bytes){$h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
function Snap{
 $rows=New-Object 'System.Collections.Generic.List[string]'
 foreach($dir in [IO.Directory]::EnumerateDirectories($top,'*',[IO.SearchOption]::AllDirectories)){$rows.Add('D|'+$dir)}
 foreach($file in [IO.Directory]::EnumerateFiles($top,'*',[IO.SearchOption]::AllDirectories)){$rows.Add('F|'+$file+'|'+(Hash ([IO.File]::ReadAllBytes($file))))}
 $rows.Sort([StringComparer]::Ordinal)
 return Hash ($utf8.GetBytes(($rows -join "`n")))
}
function Reject([scriptblock]$call,[string]$name,[string]$reason='Case-sensitive directories are not supported'){
 $before=Snap;$errorText=''
 try{$null=& $call}catch{$errorText=$_.Exception.ToString()}
 Need ($errorText.Contains($reason)) ($name+' rejected explicitly')
 Need ((Snap) -ceq $before) ($name+' preserves all fixture bytes and directories')
}
function Own([string]$project,[string]$hostName){
 $id=(Hash ($utf8.GetBytes($hostName.ToLowerInvariant()+'|'+$project.ToLowerInvariant()))).Substring(0,24)
 return Join-Path $env:LOCALAPPDATA ('Qbrain\integrations\'+$id)
}
try {
 foreach($hostName in @('Claude','Codex')){
  $parent=New-N47VDirectory ($hostName+' case parent');Flag $parent $true
  $upper=Join-Path $parent 'Project';$lower=Join-Path $parent 'project'
  [N47VFixture]::Make($upper);[N47VFixture]::Make($lower)
  Flag $upper $false;Flag $lower $false
  [IO.File]::WriteAllText((Join-Path $upper 'identity.txt'),'UPPER',$utf8)
  [IO.File]::WriteAllText((Join-Path $lower 'identity.txt'),'lower',$utf8)
  Need ([IO.File]::ReadAllText((Join-Path $upper 'identity.txt')) -ceq 'UPPER' -and [IO.File]::ReadAllText((Join-Path $lower 'identity.txt')) -ceq 'lower') ($hostName+' actual distinct case-only project directories')
  Need ((Own $upper $hostName) -ceq (Own $lower $hostName)) ($hostName+' old identity algorithm collides')
  $null=& $prior -HostName $hostName -ProjectPath $upper -Binary $exe -BrainId ('case-old-'+$hostName.ToLowerInvariant())
  $wrong=(& $prior -Action Status -HostName $hostName -ProjectPath $lower)|ConvertFrom-Json
  $lowerConfig=Join-Path $lower $(if($hostName -eq 'Claude'){'.claude\settings.local.json'}else{'.codex\hooks.json'})
  Need ($wrong.installed -and -not [IO.File]::Exists($lowerConfig)) ($hostName+' old Status incorrectly reports sibling installed')
  foreach($project in @($upper,$lower)){
   foreach($action in @('Status','Install','Uninstall')){
    Reject {& $installerPath -Action $action -HostName $hostName -ProjectPath $project -Binary $exe} ($hostName+'/'+(Split-Path $project -Leaf)+'/'+$action)
   }
  }
  Need ([N47VFixture]::Flags($parent) -eq 1 -and [N47VFixture]::Flags($upper) -eq 0 -and [N47VFixture]::Flags($lower) -eq 0) ($hostName+' guard never changes case flags')
  $sensitive=New-N47VDirectory ($hostName+' sensitive self');Flag $sensitive $true
  foreach($action in @('Install','Uninstall','Status')){Reject {& $installerPath -Action $action -HostName $hostName -ProjectPath $sensitive -Binary $exe} ($hostName+'/self/'+$action)}
  $normal=New-N47VDirectory ($hostName+' config parent')
  $cfg=Join-Path $normal $(if($hostName -eq 'Claude'){'.claude'}else{'.codex'})
  [void][IO.Directory]::CreateDirectory($cfg);Flag $cfg $true
  foreach($action in @('Install','Uninstall','Status')){Reject {& $installerPath -Action $action -HostName $hostName -ProjectPath $normal -Binary $exe} ($hostName+'/config/'+$action)}
  # Recovery must not apply a pending transaction under an unsupported target.
  $owned=Own $normal $hostName;[void][IO.Directory]::CreateDirectory($owned)
  $dest=Join-Path $cfg $(if($hostName -eq 'Claude'){'settings.local.json'}else{'hooks.json'})
  [IO.File]::WriteAllText($dest,'after-sentinel',$utf8)
  $pending=[pscustomobject]@{version=1;changes=@([pscustomobject]@{path=$dest;before='before-sentinel';after='after-sentinel'})}
  [IO.File]::WriteAllText((Join-Path $owned 'pending.json'),(ConvertTo-Json -InputObject $pending -Depth 6),$utf8)
  Reject {& $installerPath -Action Uninstall -HostName $hostName -ProjectPath $normal} ($hostName+'/pending-recovery')
  $ordinary=New-N47VDirectory ($hostName+' Ordinary '+[char]0x4E2D+" ' space")
  $null=& $installerPath -HostName $hostName -ProjectPath $ordinary -Binary $exe
  $expected=Own $ordinary $hostName
  Need ([IO.File]::Exists((Join-Path $expected 'installation.json'))) ($hostName+' ordinary legacy ID unchanged')
  $alias=$ordinary.ToUpperInvariant()
  $status=(& $installerPath -Action Status -HostName $hostName -ProjectPath $alias)|ConvertFrom-Json
  Need ($status.installed -and $status.configuration_matches -and -not $status.recovery_required) ($hostName+' ordinary case alias still resolves installation')
  $config=[IO.File]::ReadAllText((Join-Path $expected 'config.json'))|ConvertFrom-Json
  Need (-not $config.capture -and -not $config.fact_promotion -and -not $config.fact_recall) ($hostName+' ordinary default consent stays off')
  $null=& $installerPath -HostName $hostName -ProjectPath $ordinary -Binary $exe
  $null=& $installerPath -Action Uninstall -HostName $hostName -ProjectPath $ordinary
  $status=(& $installerPath -Action Status -HostName $hostName -ProjectPath $ordinary)|ConvertFrom-Json
  Need (-not $status.installed) ($hostName+' ordinary reinstall and uninstall succeed')
 }
 $binaryDir=New-N47VDirectory 'sensitive binary';Flag $binaryDir $true
 $sensitiveExe=Join-Path $binaryDir 'qbrain.exe';[IO.File]::Copy($exe,$sensitiveExe)
 $ordinary=New-N47VDirectory 'normal binary project'
 Reject {& $installerPath -HostName Claude -ProjectPath $ordinary -Binary $sensitiveExe} 'sensitive binary parent before owned creation'
 $sensitiveData=New-N47VDirectory 'sensitive appdata';Flag $sensitiveData $true
 $env:LOCALAPPDATA=$sensitiveData
 foreach($action in @('Install','Uninstall','Status')){Reject {& $installerPath -Action $action -HostName Claude -ProjectPath $ordinary -Binary $exe} ('sensitive appdata/'+$action)}
 $env:LOCALAPPDATA=$data
 $change=New-N47VDirectory 'flag changes between reads'
 $null=& $installerPath -Action Status -HostName Claude -ProjectPath $change
 Flag $change $true
 Reject {& $installerPath -Action Status -HostName Claude -ProjectPath $change} 'no stale directory flag cache'
 $blocked=New-N47VDirectory 'blocked metadata';$before=Snap;$handle=[N47VFixture]::Hold($blocked);$errorText=''
 try{try{$null=& $installerPath -Action Status -HostName Claude -ProjectPath $blocked}catch{$errorText=$_.Exception.ToString()}}finally{$handle.Dispose()}
 Need ($errorText.Contains('Cannot verify directory')) 'metadata sharing failure rejected explicitly'
 Need ((Snap) -ceq $before) 'metadata sharing failure preserves fixture bytes and directories'
 $null=& $installerPath -Action Status -HostName Claude -ProjectPath $blocked
 Need $true 'metadata query recovers after sharing handle is disposed'
 $success=$true
}finally{
 Set-Location $starting
 if(-not $success -and @($results|Where-Object {-not $_.passed}).Count -eq 0){[void]$results.Add([pscustomobject]@{name='execution interrupted';passed=$false})}
 $source=(& git -C (Join-Path $PSScriptRoot '..') rev-parse HEAD).Trim()
 $value=[pscustomobject]@{schema='qbrain-n47v-case-paths-v1';source_commit=$source;native_windows=$true;shell_major=$PSVersionTable.PSVersion.Major;powershell=$PSVersionTable.PSVersion.ToString();installer_sha256=(Get-FileHash $installerPath -Algorithm SHA256).Hash.ToLowerInvariant();baseline_installer_sha256=(Get-FileHash $prior -Algorithm SHA256).Hash.ToLowerInvariant();binary_sha256=(Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant();script_sha256=(Get-FileHash $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();result=$(if($success){'PASS'}else{'FAIL'});checks=@($results);flags=@($flagsLog);real_client_verified=$false}
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $reportPath));[IO.File]::WriteAllText($reportPath,(ConvertTo-Json -InputObject $value -Depth 12),$utf8)
 foreach($k in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')){[Environment]::SetEnvironmentVariable($k,$null,'Process')}
 foreach($k in $old.Keys){[Environment]::SetEnvironmentVariable($k,$old[$k],'Process')}
 Remove-Item -LiteralPath $top -Force -Recurse
}
if(-not $success){exit 1}
