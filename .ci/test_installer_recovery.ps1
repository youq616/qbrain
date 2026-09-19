# Real Windows filesystem and installer calls, isolated from user state.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Binary,
 [Parameter(Mandatory=$true)][string]$Report,
 [string]$Installer=''
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if(-not $Installer){$Installer=Join-Path $PSScriptRoot '..\scripts\Install-QbrainMemory.ps1'}
$exe=(Resolve-Path -LiteralPath $Binary).ProviderPath
$installerPath=(Resolve-Path -LiteralPath $Installer).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
$utf8=New-Object Text.UTF8Encoding($false,$true)
$top=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-recovery-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($top)
$old=@{}
Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE')} | ForEach-Object {
 $old[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')
}
$env:HOME=$top;$env:LOCALAPPDATA=$top;$env:USERPROFILE=$top
$script:results=New-Object System.Collections.ArrayList
function Need([bool]$value,[string]$why){if(-not $value){throw $why}}
function Save([string]$p,[AllowNull()]$value){
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $p))
 if($null -eq $value){if([IO.File]::Exists($p)){[IO.File]::Delete($p)};return}
 [IO.File]::WriteAllText($p,[string]$value,$utf8)
}
function Load([string]$p){if([IO.File]::Exists($p)){return [IO.File]::ReadAllText($p,$utf8)};return $null}
function Json($value){return ConvertTo-Json -InputObject $value -Depth 64 -Compress}
function Digest([string]$p){if([IO.File]::Exists($p)){return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash};return 'ABSENT'}
function Fixture([string]$hostName){
 $leaf=$hostName+' '+[char]0x4E2D+[char]0x6587+' '+[char]::ConvertFromUtf32(0x1F600)+' '+[Guid]::NewGuid().ToString('N')
 $project=Join-Path $top $leaf;[void][IO.Directory]::CreateDirectory($project)
 $project=(Resolve-Path -LiteralPath $project).ProviderPath
 $h=[Security.Cryptography.SHA256]::Create()
 try{$id=([BitConverter]::ToString($h.ComputeHash($utf8.GetBytes($hostName.ToLowerInvariant()+'|'+$project.ToLowerInvariant())))).Replace('-','').ToLowerInvariant().Substring(0,24)}finally{$h.Dispose()}
 $owned=Join-Path $top ('Qbrain\integrations\'+$id);[void][IO.Directory]::CreateDirectory($owned)
 $target=if($hostName -eq 'Claude'){Join-Path $project '.claude\settings.local.json'}else{Join-Path $project '.codex\hooks.json'}
 $mcp=if($hostName -eq 'Claude'){Join-Path $project '.mcp.json'}else{Join-Path $project '.codex\config.toml'}
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $target));[void][IO.Directory]::CreateDirectory((Split-Path -Parent $mcp))
 return [pscustomobject]@{hostName=$hostName;project=$project;owned=$owned;target=$target;mcp=$mcp;journal=(Join-Path $owned 'pending.json');brain=('recovery-'+$id)}
}
function Entry([string]$p,[AllowNull()]$before,[AllowNull()]$after){return [pscustomobject]@{path=$p;before=$before;after=$after}}
function Journal($f,$entries){return [pscustomobject]@{version=1;changes=@($entries)}}
function Recover($f){$null=& $installerPath -Action Uninstall -HostName $f.hostName -ProjectPath $f.project}
function Rejected([scriptblock]$call){$rejected=$false;try{$null=& $call}catch{$rejected=$true};Need $rejected 'Expected rejection'}
function Case([string]$name,[scriptblock]$call){
 try{
  $null=& $call
  [void]$script:results.Add([pscustomobject]@{name=$name;passed=$true})
  Write-Host ('PASS '+$name)
 }catch{
  [void]$script:results.Add([pscustomobject]@{name=$name;passed=$false;error=$_.Exception.Message})
  Write-Host ('FAIL '+$name+': '+$_.Exception.Message)
 }
}
function Unchanged-Rejection($f,$pending){
 Save $f.target 'after-one';Save $f.mcp 'after-two';Save $f.journal (Json $pending)
 $before=@((Digest $f.target),(Digest $f.mcp),(Digest $f.journal))
 Rejected {Recover $f}
 Need ((Digest $f.target) -ceq $before[0]) 'Earlier member was rolled back on invalid journal'
 Need ((Digest $f.mcp) -ceq $before[1]) 'Later member changed on invalid journal'
 Need ((Digest $f.journal) -ceq $before[2]) 'Rejected journal was altered or deleted'
 Need (-not [IO.Directory]::Exists((Join-Path $top ('Qbrain\brains\'+$f.brain)))) 'Recovery created a brain'
 Need (@(Get-ChildItem -LiteralPath $f.owned -Filter 'settings-backup-*').Count -eq 0) 'Rejected recovery created backup'
}
try{
 foreach($hostName in @('Claude','Codex')){
  foreach($kind in @('top-array','version-string','version-bool','version-float','zero-changes','scalar-changes','duplicate-path','extra-change-field','extra-root-field','missing-before','bad-before','bad-after','bad-path','unowned-late-path','too-many-changes')){
   Case ($hostName+'/'+$kind) {
    $f=Fixture $hostName
    $one=Entry $f.target 'before-one' 'after-one';$two=Entry $f.mcp 'before-two' 'after-two'
    $j=Journal $f @($one,$two)
    switch($kind){
     'top-array' {$j=@($j)}
     'version-string' {$j.version='1'}
     'version-bool' {$j.version=$true}
     'version-float' {$j.version=1.5}
     'zero-changes' {$j.changes=@()}
     'scalar-changes' {$j.changes=$one}
     'duplicate-path' {$j.changes=@($one,$one)}
     'extra-change-field' {$two | Add-Member -NotePropertyName 'extra' -NotePropertyValue 'ignored'}
     'extra-root-field' {$j | Add-Member -NotePropertyName 'extra' -NotePropertyValue 'ignored'}
     'missing-before' {$two.PSObject.Properties.Remove('before')}
     'bad-before' {$two.before=@('not','a','string')}
     'bad-after' {$two.after=[pscustomobject]@{bad=1};$two.before='after-two'}
     'bad-path' {$two.path=@($f.mcp)}
     'unowned-late-path' {$two.path=Join-Path $f.project 'not-owned.txt'}
     'too-many-changes' {$j.changes=@($one,$one,$one,$one,$one,$one)}
    }
    Unchanged-Rejection $f $j
   }
  }
  Case ($hostName+'/late-temp-directory') {
   $f=Fixture $hostName
   [void][IO.Directory]::CreateDirectory($f.mcp+'.tmp')
   Unchanged-Rejection $f (Journal $f @((Entry $f.target 'before-one' 'after-one'),(Entry $f.mcp 'before-two' 'after-two')))
  }
  Case ($hostName+'/late-temp-junction') {
   $f=Fixture $hostName;$other=Join-Path $f.project 'junction-target';[void][IO.Directory]::CreateDirectory($other)
   [void](New-Item -ItemType Junction -Path ($f.mcp+'.tmp') -Target $other)
   try{Unchanged-Rejection $f (Journal $f @((Entry $f.target 'before-one' 'after-one'),(Entry $f.mcp 'before-two' 'after-two')))}
   finally{[IO.Directory]::Delete($f.mcp+'.tmp')}
  }
  Case ($hostName+'/external-late-edit') {
   $f=Fixture $hostName
   Unchanged-Rejection $f (Journal $f @((Entry $f.target 'before-one' 'after-one'),(Entry $f.mcp 'before-two' 'different-after')))
  }
  Case ($hostName+'/oversized-unicode-image') {
   $f=Fixture $hostName;$large=([string][char]0x4E2D)*700000
   Unchanged-Rejection $f (Journal $f @((Entry $f.target 'before-one' 'after-one'),(Entry $f.mcp $large 'after-two')))
  }
  Case ($hostName+'/journal-envelope-cap') {
   $f=Fixture $hostName;Save $f.target 'unchanged';Save $f.journal (' '*(33554432+1))
   $before=Digest $f.journal;Rejected {Recover $f}
   Need ((Load $f.target) -ceq 'unchanged' -and (Digest $f.journal) -ceq $before) 'Oversized journal changed files'
  }
  foreach($mode in @('absent-before','empty-before','text-before','already-before','absent-after','empty-after')){
   Case ($hostName+'/'+$mode) {
    $f=Fixture $hostName;$before='original '+[char]0x4E2D+[char]::ConvertFromUtf32(0x1F600);$after='partial'
    if($mode -eq 'absent-before'){$before=$null};if($mode -eq 'empty-before'){$before=''}
    if($mode -eq 'absent-after'){$after=$null};if($mode -eq 'empty-after'){$after=''}
    $now=if($mode -eq 'already-before'){$before}else{$after}
    Save $f.target $now;Save $f.journal (Json (Journal $f @((Entry $f.target $before $after))))
    Recover $f
    Need ((Load $f.target) -ceq $before) 'Wrong recovered text/absence'
    Need ([IO.File]::Exists($f.target) -eq ($null -ne $before)) 'Empty and absent were conflated'
    Need (-not [IO.File]::Exists($f.journal)) 'Successful recovery retained journal'
   }
  }
  Case ($hostName+'/large-valid-journal') {
   $f=Fixture $hostName;$before='a'*1100000;$after='b'*1100000
   Save $f.target $after;Save $f.journal (Json (Journal $f @((Entry $f.target $before $after))))
   Need ((Get-Item -LiteralPath $f.journal).Length -gt 2097152) 'Fixture did not exceed old journal cap'
   Recover $f
   Need ((Load $f.target) -ceq $before -and -not [IO.File]::Exists($f.journal)) 'Large valid journal did not recover'
  }
  Case ($hostName+'/io-failure-remains-retryable') {
   $f=Fixture $hostName;Save $f.target 'after-one';Save $f.mcp 'after-two'
   Save $f.journal (Json (Journal $f @((Entry $f.target 'before-one' 'after-one'),(Entry $f.mcp 'before-two' 'after-two'))))
   $journalHash=Digest $f.journal
   $lock=[IO.File]::Open($f.mcp,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
   try{Rejected {Recover $f}}finally{$lock.Dispose()}
   Need ((Digest $f.journal) -ceq $journalHash) 'I/O failure lost recovery journal'
   Need ((Load $f.target) -ceq 'before-one' -and (Load $f.mcp) -ceq 'after-two') 'Fixture did not stop at second rollback member'
   Recover $f
   Need ((Load $f.target) -ceq 'before-one' -and (Load $f.mcp) -ceq 'before-two') 'Retry did not restore both images'
   Need (-not [IO.File]::Exists($f.journal)) 'Retry did not retire journal'
  }
  Case ($hostName+'/generated-image-overflow-before-init') {
   $f=Fixture $hostName;Save $f.target (Json ([pscustomobject]@{padding=('x'*(2097152-128))}))
   $before=Digest $f.target
   Rejected {& $installerPath -HostName $hostName -ProjectPath $f.project -Binary $exe -BrainId $f.brain}
   Need ((Digest $f.target) -ceq $before) 'Invalid output budget changed settings'
   Need (-not [IO.Directory]::Exists((Join-Path $top ('Qbrain\brains\'+$f.brain)))) 'Invalid output budget initialized a brain'
   Need (-not [IO.File]::Exists($f.journal)) 'Invalid output budget left a journal'
   Need (@(Get-ChildItem -LiteralPath $f.owned -Filter 'settings-backup-*').Count -eq 0) 'Invalid output budget created backup'
  }
  Case ($hostName+'/real-interrupted-large-install') {
   $f=Fixture $hostName
   $original=Json ([pscustomobject]@{padding=('x'*1100000);unrelated='keep'})
   $mcpOriginal=if($hostName -eq 'Claude'){'{"mcpServers":{"other":{"command":"existing"}}}'}else{"# keep comment`nmodel = 'existing'`n"}
   Save $f.target $original;Save $f.mcp $mcpOriginal
   $lock=[IO.File]::Open($f.mcp,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
   try{Rejected {& $installerPath -HostName $hostName -ProjectPath $f.project -Binary $exe -BrainId $f.brain}}finally{$lock.Dispose()}
   Need ([IO.File]::Exists($f.journal) -and (Get-Item -LiteralPath $f.journal).Length -gt 2097152) 'Real install did not leave large recovery journal'
   $database=Join-Path $top ('Qbrain\brains\'+$f.brain+'\brain.db');$dbBefore=Digest $database
   Need ($dbBefore -ne 'ABSENT') 'Real native brain was not initialized'
   $status=(& $installerPath -Action Status -HostName $hostName -ProjectPath $f.project) | ConvertFrom-Json
   Need $status.recovery_required 'Status missed pending recovery'
   Recover $f
   Need ((Load $f.target) -ceq $original -and (Load $f.mcp) -ceq $mcpOriginal) 'Rollback lost original settings'
   Need (-not [IO.File]::Exists((Join-Path $f.owned 'installation.json')) -and -not [IO.File]::Exists((Join-Path $f.owned 'config.json'))) 'Rollback retained new ownership/config'
   Need (-not [IO.File]::Exists($f.journal)) 'Real rollback retained journal'
   Need ((Digest $database) -ceq $dbBefore) 'Recovery changed or deleted brain data'
  }
 }
}finally{
 foreach($key in @('HOME','LOCALAPPDATA','USERPROFILE')){[Environment]::SetEnvironmentVariable($key,$null,'Process')}
 foreach($key in $old.Keys){[Environment]::SetEnvironmentVariable($key,$old[$key],'Process')}
 Remove-Item -LiteralPath $top -Force -Recurse
}
$failed=@($script:results | Where-Object {-not $_.passed}).Count
[void][IO.Directory]::CreateDirectory((Split-Path -Parent $reportPath))
Save $reportPath (Json ([pscustomobject]@{schema='qbrain-n47p-recovery-v1';powershell=$PSVersionTable.PSVersion.ToString();installer_sha256=(Digest $installerPath);binary_sha256=(Digest $exe);cases=@($script:results);passed=($script:results.Count-$failed);failed=$failed;live_client_tested=$false}))
Write-Host ('N47P recovery: '+($script:results.Count-$failed)+'/'+$script:results.Count+' passed; failures='+$failed)
if($failed){exit 1}
