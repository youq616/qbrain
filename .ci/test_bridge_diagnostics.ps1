# Native, synthetic child processes; no real client or private data. ASCII source.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Bridge,
 [Parameter(Mandatory=$true)][string]$PriorBridge,
 [Parameter(Mandatory=$true)][string]$Child,
 [Parameter(Mandatory=$true)][string]$Report
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$bridgePath=(Resolve-Path -LiteralPath $Bridge).ProviderPath
$priorPath=(Resolve-Path -LiteralPath $PriorBridge).ProviderPath
$childPath=(Resolve-Path -LiteralPath $Child).ProviderPath
$reportPath=[IO.Path]::GetFullPath($Report)
if(Test-Path -LiteralPath $reportPath){throw 'Report must be new.'}
$utf8=New-Object Text.UTF8Encoding($false,$true)
$root=Join-Path ([IO.Path]::GetTempPath()) ('n47w-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($root)
$checks=New-Object System.Collections.ArrayList
$diagnostics=New-Object System.Collections.ArrayList
$success=$false;$failure=''
$secret='private-content-'+[Guid]::NewGuid().ToString('N')
function Check([bool]$ok,[string]$name){
 [void]$checks.Add([pscustomobject]@{name=$name;passed=$ok})
 if(-not $ok){throw $name};Write-Host ('PASS '+$checks.Count+' : '+$name)
}
function HashFile([string]$p){return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}
function DiagnosticFrom($errorRecord){
 $ex=$errorRecord.Exception
 for($i=0;$i -lt 8 -and $null -ne $ex;$i++){
  if($ex.Data.Contains('QbrainTransport')){
   $raw=[string]$ex.Data['QbrainTransport']
   if($raw.Contains($secret) -or $raw.Contains($root) -or $utf8.GetByteCount($raw) -gt 2048){throw 'Unsafe diagnostic payload.'}
   $d=$raw|ConvertFrom-Json
   [void]$diagnostics.Add($d)
   return [pscustomobject]@{Value=$d;Message=$ex.Message}
  }
  $ex=$ex.InnerException
 }
 throw 'Expected structured failure metadata.'
}
function IsStopped([string]$pidFile){
 if(-not [IO.File]::Exists($pidFile)){return $false}
 $childId=[int][IO.File]::ReadAllText($pidFile)
 try{$p=[Diagnostics.Process]::GetProcessById($childId);try{return $p.HasExited}finally{$p.Dispose()}}catch{return $true}
}
function Failure([string]$mode,[string]$inputText=''){
 $pidFile=Join-Path $root ($mode+'.pid');$errorRecord=$null
 try{$null=& $bridgePath -FilePath $childPath -ArgumentList @($mode,$pidFile,$secret) -InputJson $inputText -TimeoutMilliseconds 2000}catch{$errorRecord=$_}
 if($null -eq $errorRecord){throw 'Expected failure, got success.'}
 return DiagnosticFrom $errorRecord
}
try{
 $text=$secret+' '+[char]0x4E2D+[char]::ConvertFromUtf32(0x1F600)+' "quoted" trailing\'
 $old=& $priorPath -FilePath $childPath -ArgumentList @('echo',(Join-Path $root 'old.pid'),$secret) -InputJson $text
 $plain=& $bridgePath -FilePath $childPath -ArgumentList @('echo',(Join-Path $root 'plain.pid'),$secret) -InputJson $text
 Check ((@($plain.PSObject.Properties.Name|Sort-Object)-join ',') -ceq 'ExitCode,Stderr,Stdout') 'default success result has exactly the original three fields'
 Check ($plain.ExitCode -eq 7 -and $plain.Stdout -ceq $text -and $plain.Stderr -ceq 'fixture-stderr') 'nonzero child exit and exact Unicode streams remain successful transport'
 Check (($plain|ConvertTo-Json -Compress) -ceq ($old|ConvertTo-Json -Compress)) 'default success matches the exact prior bridge result'
 $observed=& $bridgePath -FilePath $childPath -ArgumentList @('echo',(Join-Path $root 'observed.pid'),$secret) -InputJson $text -IncludeDiagnostics
 Check ($observed.Stdout -ceq $plain.Stdout -and $observed.Stderr -ceq $plain.Stderr -and $observed.ExitCode -eq 7) 'opt-in diagnostics do not change child output'
 $d=$observed.Transport;[void]$diagnostics.Add($d)
 Check ($d.schema -ceq 'qbrain-transport-diagnostic-v1' -and $d.phase -ceq 'complete' -and $d.code -ceq 'completed') 'success diagnostic has versioned completed identity'
 Check ($d.timeout_ms -eq 10000 -and $d.process_started -and $d.input_closed -and $d.process_exited -and $d.exit_code -eq 7) 'success diagnostic preserves default timeout and observed exit'
 Check ($d.input_state -ceq 'completed' -and $d.stdout_state -ceq 'completed' -and $d.stderr_state -ceq 'completed') 'success diagnostic reports completed streams'
 Check ($d.wait_budget_ms.input -le (10000-$d.stage_ms.start) -and $d.wait_budget_ms.process -le $d.wait_budget_ms.input -and $d.wait_budget_ms.output -le $d.wait_budget_ms.process) 'all waits consume one decreasing elapsed budget'
 $bad=Join-Path $root ($secret+'.exe');[IO.File]::WriteAllText($bad,'not an executable')
 $e=$null;try{$null=& $bridgePath -FilePath $bad -ArgumentList @($secret) -InputJson $secret}catch{$e=$_}
 Check ($null -ne $e) 'invalid executable does not report success'
 $f=DiagnosticFrom $e;$d=$f.Value
 Check ($d.phase -ceq 'start' -and $d.code -ceq 'start_failed' -and -not $d.process_started) 'startup failure is distinct from process timeout'
 Check ($null -eq $d.process_exited -and $null -eq $d.exit_code -and $d.input_state -ceq 'not_started') 'unstarted process observations remain null and not started'
 Check ($f.Message -ceq 'Could not start Qbrain.' -and -not $f.Message.Contains($secret)) 'startup failure is normalized without native path text'
 $f=Failure 'input-stall' ('x'*262144);$d=$f.Value
 Check ($d.phase -ceq 'input' -and $d.code -ceq 'input_timeout' -and $f.Message -ceq 'Qbrain input timeout.') 'blocked input has the original input timeout message'
 Check ($d.process_started -and -not $d.input_closed -and $d.input_state -ceq 'running') 'blocked input reports actual pre-cleanup input state'
 Check ($d.wait_budget_ms.input -le (2000-$d.stage_ms.start) -and $null -eq $d.wait_budget_ms.process) 'blocked input does not receive a fresh timeout budget'
 Check (IsStopped (Join-Path $root 'input-stall.pid')) 'input timeout cleanup terminates the direct test child'
 $f=Failure 'process-stall' $secret;$d=$f.Value
 Check ($d.phase -ceq 'process' -and $d.code -ceq 'process_timeout' -and $f.Message -ceq 'Qbrain process timeout.') 'live child has the original process timeout message'
 Check ($d.input_closed -and $d.input_state -ceq 'completed' -and $d.process_exited -eq $false -and $null -eq $d.exit_code) 'process timeout distinguishes finished input from live child'
 Check (IsStopped (Join-Path $root 'process-stall.pid')) 'process timeout cleanup terminates the direct test child'
 $f=Failure 'held-output';$d=$f.Value
 Check ($d.phase -ceq 'output' -and $d.code -ceq 'output_timeout' -and $f.Message -ceq 'Qbrain output timeout.') 'inherited pipe holder has the original output timeout message'
 Check ($d.process_exited -eq $true -and $d.exit_code -eq 0 -and ($d.stdout_state -ceq 'running' -or $d.stderr_state -ceq 'running')) 'output timeout distinguishes an exited parent from open streams'
 $descendantFile=Join-Path $root 'held-output.pid.descendant'
 Check ([IO.File]::Exists($descendantFile)) 'output fixture records its separately cleaned descendant'
 $descendantId=[int][IO.File]::ReadAllText($descendantFile)
 try{$p=[Diagnostics.Process]::GetProcessById($descendantId);try{if(-not $p.HasExited){$p.Kill();[void]$p.WaitForExit(2000)}}finally{$p.Dispose()}}catch{}
 $f=Failure 'bad-utf8';$d=$f.Value
 Check ($d.code -ceq 'transport_error' -and $f.Message -ceq 'Qbrain transport failure.') 'invalid UTF-8 remains an error not replacement text'
 Check ($d.stdout_state -ceq 'faulted') 'stream decoder failure is visible without reading fault text'
 $after=& $bridgePath -FilePath $childPath -ArgumentList @('echo',(Join-Path $root 'after.pid')) -InputJson ''
 Check ($after.ExitCode -eq 7 -and $after.Stdout -ceq '' -and $after.Stderr -ceq 'fixture-stderr') 'a later invocation succeeds after all failure paths'
 # Execute the exact isolated budget helper, without changing a production branch.
 $tokens=$null;$parseErrors=$null
 $ast=[Management.Automation.Language.Parser]::ParseFile($bridgePath,[ref]$tokens,[ref]$parseErrors)
 Check ($parseErrors.Count -eq 0) 'bridge source parses in this actual PowerShell version'
 $functionAst=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Get-QbrainRemainingMilliseconds'},$true)
 . ([scriptblock]::Create($functionAst.Extent.Text))
 Check ((Get-QbrainRemainingMilliseconds 10000 2500) -eq 7500 -and (Get-QbrainRemainingMilliseconds 10000 10000) -eq 0 -and (Get-QbrainRemainingMilliseconds 10000 2147483648) -eq 0) 'elapsed-budget helper clamps expired and large elapsed values'
 $all=ConvertTo-Json -InputObject @($diagnostics) -Depth 6 -Compress
 Check (-not $all.Contains($secret) -and -not $all.Contains($root) -and -not $all.Contains('fixture-stderr')) 'all shareable diagnostics exclude input path argument and output sentinels'
 Check (@($diagnostics|Where-Object {$_.host_consumption_verified -ne $false -or $_.observation -cne 'before_cleanup'}).Count -eq 0) 'diagnostics are observations not proof of host consumption'
 $success=$true
}catch{$failure=$_.Exception.Message}
finally{
 # Test cleanup only, no arbitrary process scan or product process-tree kill.
 foreach($pidFile in Get-ChildItem -LiteralPath $root -Filter '*.pid*' -File){
  try{$childId=[int][IO.File]::ReadAllText($pidFile.FullName);$p=[Diagnostics.Process]::GetProcessById($childId);try{if(-not $p.HasExited){$p.Kill();[void]$p.WaitForExit(2000)}}finally{$p.Dispose()}}catch{}
 }
 $source=(& git -C (Join-Path $PSScriptRoot '..') rev-parse HEAD).Trim()
 $record=[pscustomobject]@{schema='qbrain-n47w-bridge-test-v1';result=$(if($success){'PASS'}else{'FAIL'});source_commit=$source;shell_major=$PSVersionTable.PSVersion.Major;bridge_sha256=(HashFile $bridgePath);prior_bridge_sha256=(HashFile $priorPath);test_sha256=(HashFile $PSCommandPath);child_sha256=(HashFile $childPath);checks=@($checks);diagnostics=@($diagnostics);failure=$failure;real_client_verified=$false}
 [void][IO.Directory]::CreateDirectory((Split-Path -Parent $reportPath))
 $stream=[IO.File]::Open($reportPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
 try{$bytes=$utf8.GetBytes((ConvertTo-Json -InputObject $record -Depth 8));$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
 Remove-Item -LiteralPath $root -Recurse -Force
}
if(-not $success){Write-Error ('Diagnostic test failed: '+$failure);exit 1}
