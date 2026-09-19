# Deterministically interleave real file edits during installer plan serialization.
# The wrapper delegates to the real cmdlet; no production test flag or code patch.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Binary,
 [Parameter(Mandatory=$true)][string]$Report,
 [string]$Installer=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){throw 'Native Windows required.'}
if(-not $Installer){$Installer=Join-Path $PSScriptRoot '..\scripts\Install-QbrainMemory.ps1'}
$installerPath=(Resolve-Path -LiteralPath $Installer).ProviderPath
$exe=(Resolve-Path -LiteralPath $Binary).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
$utf8=New-Object Text.UTF8Encoding($false,$true)
$top=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-snapshot-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($top)
$old=@{}
Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')} | ForEach-Object {
 $old[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')
}
$env:HOME=$top;$env:LOCALAPPDATA=$top;$env:USERPROFILE=$top;$env:APPDATA=$top
$global:N47PTestState=[pscustomobject]@{armed=$false;path='';text='';hits=0}
function ConvertTo-Json {
 [CmdletBinding()]
 param([Parameter(ValueFromPipeline=$true)]$InputObject,[int]$Depth=2,[switch]$Compress)
 process {
  if($global:N47PTestState.armed){
   $global:N47PTestState.armed=$false
   $global:N47PTestState.hits++
   [IO.File]::WriteAllText($global:N47PTestState.path,$global:N47PTestState.text,(New-Object Text.UTF8Encoding($false,$true)))
  }
  Microsoft.PowerShell.Utility\ConvertTo-Json -InputObject $InputObject -Depth $Depth -Compress:$Compress
 }
}
function Need([bool]$value,[string]$message){if(-not $value){throw $message}}
function Save([string]$p,[AllowNull()]$text){
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $p))
 if($null -eq $text){if([IO.File]::Exists($p)){[IO.File]::Delete($p)};return}
 [IO.File]::WriteAllText($p,[string]$text,$utf8)
}
function Image([string]$p){if([IO.File]::Exists($p)){return [Convert]::ToBase64String([IO.File]::ReadAllBytes($p))};return 'ABSENT'}
function Fixture([string]$hostName,[bool]$empty){
 $leaf=$hostName+' '+[char]0x4E2D+[char]::ConvertFromUtf32(0x1F600)+' '+[Guid]::NewGuid().ToString('N')
 $project=Join-Path $top $leaf;[void][IO.Directory]::CreateDirectory($project)
 $project=(Resolve-Path -LiteralPath $project).ProviderPath
 $h=[Security.Cryptography.SHA256]::Create()
 try{$id=([BitConverter]::ToString($h.ComputeHash($utf8.GetBytes($hostName.ToLowerInvariant()+'|'+$project.ToLowerInvariant())))).Replace('-','').ToLowerInvariant().Substring(0,24)}finally{$h.Dispose()}
 $owned=Join-Path $top ('Qbrain\integrations\'+$id);[void][IO.Directory]::CreateDirectory($owned)
 $target=if($hostName -eq 'Claude'){Join-Path $project '.claude\settings.local.json'}else{Join-Path $project '.codex\hooks.json'}
 $mcp=if($hostName -eq 'Claude'){Join-Path $project '.mcp.json'}else{Join-Path $project '.codex\config.toml'}
 $paths=@{target=$target;mcp=$mcp;owner=(Join-Path $owned 'installation.json');config=(Join-Path $owned 'config.json');bridge=(Join-Path $owned 'Invoke-QbrainJson.ps1')}
 foreach($p in $paths.Values){Save $p $null}
 if(-not $empty){
  Save $target '{"user_setting":"preserve-me","hooks":{}}'
  if($hostName -eq 'Claude'){Save $mcp '{"user_setting":"preserve-me","mcpServers":{}}'}else{Save $mcp "# preserve-me`nmodel = 'fixture-model'`n"}
  Save $paths.owner '{"active":false}'
  Save $paths.config '{"enabled":false,"capture":false}'
  Save $paths.bridge '# old owned bridge'
 }
 return [pscustomobject]@{hostName=$hostName;project=$project;owned=$owned;paths=$paths;brain=('snapshot-'+$id)}
}
$results=New-Object System.Collections.ArrayList
$starting=Get-Location
try {
 foreach($hostName in @('Claude','Codex')){
  foreach($kind in @('target-existing','target-absent','mcp-existing','mcp-absent','owner-existing','owner-absent','config-existing','config-absent','bridge-existing','bridge-absent','normal-existing','normal-absent')){
   $label=$hostName+'/'+$kind
   try {
    $normal=$kind.StartsWith('normal-');$f=Fixture $hostName $kind.EndsWith('-absent');Set-Location -LiteralPath $f.project
    $global:N47PTestState.armed=$false;$global:N47PTestState.hits=0
    $expected=@{};foreach($key in $f.paths.Keys){$expected[$key]=Image $f.paths[$key]}
    if(-not $normal){
     $key=$kind.Split('-')[0]
     $text=if($key -eq 'mcp' -and $hostName -eq 'Codex'){"# external edit must survive`nmodel = 'externally-edited'`n"}elseif($key -eq 'bridge'){'# external edited bridge'}else{'{"external_edit":"must-survive","active":false}'}
     $global:N47PTestState.path=$f.paths[$key];$global:N47PTestState.text=$text;$global:N47PTestState.armed=$true
     $expected[$key]=[Convert]::ToBase64String($utf8.GetBytes($text))
    }
    $errorText=$null
    try{$null=& $installerPath -HostName $hostName -ProjectPath $f.project -Binary $exe -BrainId $f.brain}catch{$errorText=$_.Exception.Message}
    $global:N47PTestState.armed=$false
    if($normal){
     Need ($null -eq $errorText) ('Normal installation failed: '+$errorText)
     Need ($global:N47PTestState.hits -eq 0) 'Control unexpectedly edited a file'
     $status=(& $installerPath -Action Status -HostName $hostName -ProjectPath $f.project)|ConvertFrom-Json
     Need ($status.installed -and $status.configuration_matches -and -not $status.recovery_required) 'Normal install is not coherent'
     $cfg=[IO.File]::ReadAllText($f.paths.config,$utf8)|ConvertFrom-Json
     Need (-not $cfg.capture -and -not $cfg.fact_recall -and -not $cfg.fact_promotion) 'Default consent changed'
     if($kind -eq 'normal-existing'){
      Need ([IO.File]::ReadAllText($f.paths.target,$utf8).Contains('preserve-me')) 'Unrelated settings lost in control'
      Need ([IO.File]::ReadAllText($f.paths.mcp,$utf8).Contains('preserve-me')) 'Unrelated MCP data lost in control'
     }
     $null=& $installerPath -Action Uninstall -HostName $hostName -ProjectPath $f.project
     Need (-not ((& $installerPath -Action Status -HostName $hostName -ProjectPath $f.project)|ConvertFrom-Json).installed) 'Control uninstall failed'
    } else {
     Need ($global:N47PTestState.hits -eq 1) 'Serialization seam was not reached exactly once'
     Need ($errorText -ceq 'Configuration changed during install.') ('Conflict was not correctly rejected: '+$errorText)
     foreach($key in $f.paths.Keys){Need ((Image $f.paths[$key]) -ceq $expected[$key]) ('Conflict overwrote '+$key)}
     Need (-not [IO.File]::Exists((Join-Path $f.owned 'pending.json'))) 'Conflict wrote a journal'
     Need (@(Get-ChildItem -LiteralPath $f.owned -Filter 'settings-backup-*').Count -eq 0) 'Conflict wrote a misleading backup'
     Need (-not [IO.Directory]::Exists((Join-Path $top ('Qbrain\brains\'+$f.brain)))) 'Planning conflict created a brain'
    }
    [void]$results.Add([pscustomobject]@{name=$label;passed=$true})
    Write-Host ('PASS '+$label)
   } catch {
    $global:N47PTestState.armed=$false
    [void]$results.Add([pscustomobject]@{name=$label;passed=$false;error=$_.Exception.Message})
    Write-Host ('FAIL '+$label+': '+$_.Exception.Message)
   }
  }
 }
} finally {
 Set-Location $starting
 $failed=@($results|Where-Object {-not $_.passed}).Count
 $source=(& git -C (Join-Path $PSScriptRoot '..') rev-parse HEAD).Trim()
 $value=[pscustomobject]@{schema='qbrain-n47p-input-snapshot-v1';source_commit=$source;native_windows=$true;shell_major=$PSVersionTable.PSVersion.Major;powershell=$PSVersionTable.PSVersion.ToString();installer_sha256=(Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant();test_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();binary_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant();passed=($results.Count-$failed);failed=$failed;cases=@($results);real_client_tested=$false;interleaving='test-only serialization wrapper; real Windows files; original cmdlet delegated'}
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $reportPath))
 [IO.File]::WriteAllText($reportPath,(Microsoft.PowerShell.Utility\ConvertTo-Json -InputObject $value -Depth 12),$utf8)
 Remove-Variable N47PTestState -Scope Global -ErrorAction SilentlyContinue
 foreach($key in @('HOME','LOCALAPPDATA','USERPROFILE','APPDATA')){[Environment]::SetEnvironmentVariable($key,$null,'Process')}
 foreach($key in $old.Keys){[Environment]::SetEnvironmentVariable($key,$old[$key],'Process')}
 Remove-Item -LiteralPath $top -Recurse -Force
}
if($failed){exit 1}
