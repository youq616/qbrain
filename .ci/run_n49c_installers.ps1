# Both-shell installer/transport matrix using only the freshly identified combined EXE.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Binary,[Parameter(Mandatory=$true)][string]$Output)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
# Scrub the driver itself before any external program, then scrub again per row.
$blocked='^(QBRAIN|PG|CURSOR|OPENAI|ANTHROPIC|GH_TOKEN|GITHUB_TOKEN|AWS_|AZURE_|GOOGLE_|GCP_|ZHIPU|GEMINI|COHERE|MISTRAL|DEEPSEEK|HF_|HUGGINGFACE|OPENROUTER|GIT_CONFIG_)|(?:^|_)(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|DSN|DATABASE_URL)(?:_|$)'
Get-ChildItem Env: | Where-Object {$_.Name -match $blocked} | ForEach-Object {[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')}
$driverHome=Join-Path ([IO.Path]::GetTempPath()) ('n49c-driver-'+[Guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($driverHome)
foreach($key in @('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME')){[Environment]::SetEnvironmentVariable($key,$driverHome,'Process')}
$env:PYTHONDONTWRITEBYTECODE='1';$env:PYTHONIOENCODING='utf-8'
$env:GIT_CONFIG_GLOBAL='NUL';$env:GIT_CONFIG_SYSTEM='NUL'
$script:postconditionsComplete=$false;$script:fatalFailure=$false;$script:currentShell='';$script:fixtureSealHash=$null;$fixtureFiles=@()

$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$binaryPath=(Resolve-Path -LiteralPath $Binary).Path
$out=[IO.Path]::GetFullPath($Output)
if(Test-Path -LiteralPath $out){throw 'Fresh output required'}
New-Item -ItemType Directory $out | Out-Null
$rows=New-Object System.Collections.Generic.List[object]
$binaryHash=(Get-FileHash -LiteralPath $binaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
$source=(& git -C $root rev-parse HEAD).Trim()
$fixture=Join-Path $out 'fixtures';New-Item -ItemType Directory $fixture | Out-Null
function Save-Matrix {
 $complete=($script:postconditionsComplete -and -not $script:fatalFailure -and $rows.Count -eq 44 -and @($rows | Where-Object {-not $_.passed}).Count -eq 0)
 $value=[ordered]@{schema='qbrain-n49c-installers-v2';passed=$complete;postconditions_complete=$script:postconditionsComplete;fatal_failure=$script:fatalFailure;expected_rows=44;source=$source;binary=$binaryPath;binary_sha256=$binaryHash;fixture_seal_sha256=$script:fixtureSealHash;rows=@($rows.ToArray());real_client=$false;postgres_executed=$false}
 [IO.File]::WriteAllText((Join-Path $out 'MATRIX.json'),($value|ConvertTo-Json -Depth 30),(New-Object Text.UTF8Encoding($false)))
}
function Run-Gate([string]$Name,[string]$Exe,[object[]]$Arguments,[int]$Expected,[int]$Major){
 $resolved=$Exe
 try {
 $resolved=if(Test-Path -LiteralPath $Exe){(Resolve-Path -LiteralPath $Exe).Path}else{(Get-Command $Exe -CommandType Application).Source}
 $spec=[ordered]@{name=$Name;executable=$resolved;arguments=@($Arguments|ForEach-Object {[string]$_});expected_exit=$Expected;shell_executable=$script:currentShell;expected_shell_major=$Major;binary=$binaryPath;binary_sha256=$binaryHash;prefix=(Join-Path $out $Name);cwd=$root}
 $specPath=Join-Path $out ($Name+'.argv.json');$rowPath=Join-Path $out ($Name+'.row.json')
 [IO.File]::WriteAllText($specPath,($spec|ConvertTo-Json -Depth 20),(New-Object Text.UTF8Encoding($false)))
  & python (Join-Path $root '.ci/test_n49c_process.py') --capture-spec $specPath --capture-result $rowPath 1> (Join-Path $out ($Name+'.controller.stdout')) 2> (Join-Path $out ($Name+'.controller.stderr'))
  $helperExit=$LASTEXITCODE
  if($helperExit -ne 0 -or -not (Test-Path -LiteralPath $rowPath)){throw 'Raw capture helper did not produce a row'}
  $row=Get-Content -LiteralPath $rowPath -Raw -Encoding UTF8 | ConvertFrom-Json
  $rows.Add($row)
 } catch {
  $rows.Add([pscustomobject]@{name=$Name;passed=$false;error=($_|Out-String);expected_exit=$Expected;expected_shell_major=$Major;executable=$resolved;argv=@($Arguments);binary_sha256=$binaryHash})
 }
 Save-Matrix
}

try {
 $materialize=@'
import pathlib,sys,json
root,out=map(pathlib.Path,sys.argv[1:])
sys.path.insert(0,str(root/'.ci'))
from check_n49c_sources import materialize_prior_fixtures
print(json.dumps(materialize_prior_fixtures(root,out),sort_keys=True))
'@
 & python -c $materialize $root $fixture
 if($LASTEXITCODE -ne 0){throw 'Exact fixture materialization failed'}
 $zip=Join-Path $fixture 'recovery-prior.zip'
 Invoke-WebRequest 'https://github.com/youq616/qbrain/releases/download/windows-preview-c26ec5e5/qbrain-windows-x64-reviewed.zip' -OutFile $zip
 if((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -cne 'ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c'){throw 'Recovery ZIP identity mismatch'}
 Expand-Archive $zip (Join-Path $fixture 'recovery-prior')
 $r=Join-Path $fixture 'recovery-prior/scripts/Install-QbrainMemory.ps1'
 if((Get-FileHash $r -Algorithm SHA256).Hash.ToLowerInvariant() -cne '99d864bf1e87c75a2b7c22a7f2c27d3b25210a153ef10516e9fff366313a22a6'){throw 'Recovery installer identity mismatch'}
 $i=Join-Path $root 'scripts/Install-QbrainMemory.ps1';$p=Join-Path $fixture 'P.ps1';$k=Join-Path $fixture 'K.ps1'
 $fixtureFiles=@(Get-ChildItem -LiteralPath $fixture -Recurse -File)+@((Get-Item -LiteralPath $i),(Get-Item -LiteralPath (Join-Path $root 'scripts/Invoke-QbrainJson.ps1')))
 $fixtureFiles=@($fixtureFiles | ForEach-Object {[pscustomobject]@{path=$_.FullName;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}})
 $fixtureSeal=Join-Path $out 'FIXTURE-INPUTS.json'
 [IO.File]::WriteAllText($fixtureSeal,([ordered]@{source=$source;files=$fixtureFiles}|ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))
 $script:fixtureSealHash=(Get-FileHash -LiteralPath $fixtureSeal -Algorithm SHA256).Hash.ToLowerInvariant()
 $priorManifest=Join-Path $fixture 'P-K-INPUTS.json'
 $priorManifestHash=(Get-FileHash -LiteralPath $priorManifest -Algorithm SHA256).Hash.ToLowerInvariant()
 $ps5=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe';$ps7=(Get-Command pwsh).Source
 foreach($shell in @(@(5,$ps5),@(7,$ps7))){
  $major=[int]$shell[0];$program=[string]$shell[1];$label='ps'+$major
  $script:currentShell=$program
  $prefix=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File')
  foreach($test in @('test_cursor_install','test_install_hooks','test_install_consent','test_windows_transport','test_hook_fact_install','test_promotion_install')){
   $args=@($prefix)+@((Join-Path $root ".ci/$test.ps1"),'-Binary',$binaryPath)
   if($test -in @('test_cursor_install','test_hook_fact_install','test_promotion_install')){$args+=@('-Report',(Join-Path $out "$label-$test.json"))}
   Run-Gate "$label-$test" $program $args 0 $major
  }
  foreach($kind in @('recovery','snapshot')){
   foreach($prior in @($false,$true)){
    $name="$label-$kind"+$(if($prior){'-prior'}else{''})
    $installer=if(-not $prior){$i}elseif($kind -eq 'snapshot'){$p}else{$r}
    $report=Join-Path $out "$name.json"
    Run-Gate $name $program (@($prefix)+@((Join-Path $root ".ci/test_installer_$kind.ps1"),'-Installer',$installer,'-Binary',$binaryPath,'-Report',$report)) $(if($prior){1}else{0}) $major
    if($kind -eq 'recovery'){
     $args=@((Join-Path $root '.ci/check_recovery_report.py'),'--report',$report,'--installer',$installer,'--binary',$binaryPath)
    }else{
     $args=@((Join-Path $root '.ci/check_installer_snapshot_report.py'),'--report',$report,'--installer',$installer,'--test',(Join-Path $root '.ci/test_installer_snapshot.ps1'),'--binary',$binaryPath,'--source',$source,'--shell',$major)
    }
    if($prior){$args+='--baseline'}
    Run-Gate "$name-readback" 'python' $args 0 $major
    if($kind -eq 'recovery'){
     Run-Gate "$name-shell-identity" 'python' @('-c','import json,sys;v=json.load(open(sys.argv[1],encoding="utf-8-sig"))["powershell"];sys.exit(0 if int(v.split(".")[0])==int(sys.argv[2]) else 1)',$report,$major) 0 $major
    }
   }
  }
  $report=Join-Path $out "$label-case.json"
  Run-Gate "$label-case" $program (@($prefix)+@((Join-Path $root '.ci/test_installer_case_paths.ps1'),'-Installer',$i,'-BaselineInstaller',$k,'-Binary',$binaryPath,'-Report',$report)) 0 $major
  Run-Gate "$label-case-readback" 'python' @((Join-Path $root '.ci/check_installer_case_paths.py'),'--report',$report,'--installer',$i,'--prior',$k,'--test',(Join-Path $root '.ci/test_installer_case_paths.ps1'),'--binary',$binaryPath,'--source',$source,'--shell',$major,'--log',(Join-Path $out "$label-case.log")) 0 $major
  foreach($test in @('test_check_installer_snapshot_report','test_check_installer_case_paths')){
   Run-Gate "$label-$test" 'python' @((Join-Path $root ".ci/$test.py")) 0 $major
   Run-Gate "$label-$test-optimized" 'python' @('-O',(Join-Path $root ".ci/$test.py")) 0 $major
  }
 }
 $verifyPrior=@'
import pathlib,sys
root,out=map(pathlib.Path,sys.argv[1:3]);sys.path.insert(0,str(root/'.ci'))
from check_n49c_sources import verify_prior_fixtures
verify_prior_fixtures(out,sys.argv[3])
'@
 & python -c $verifyPrior $root $fixture $priorManifestHash
 if($LASTEXITCODE -ne 0){throw 'Pinned prior fixture identity changed'}
 if((Get-FileHash -LiteralPath $fixtureSeal -Algorithm SHA256).Hash.ToLowerInvariant() -cne $script:fixtureSealHash){throw 'Fixture input seal changed'}
 foreach($file in $fixtureFiles){
  if(-not (Test-Path -LiteralPath $file.path -PathType Leaf)){throw 'Fixture input disappeared'}
  if((Get-Item -LiteralPath $file.path).Length -ne $file.bytes -or (Get-FileHash -LiteralPath $file.path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $file.sha256){throw 'Fixture input changed'}
 }
 if((Get-FileHash $binaryPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $binaryHash){throw 'Combined executable changed'}
 if($rows.Count -ne 44 -or @($rows | Where-Object {-not $_.passed}).Count){throw 'Installer matrix contains missing or failed gates'}
 $script:postconditionsComplete=$true
 Save-Matrix
} catch {
 $script:fatalFailure=$true;$script:postconditionsComplete=$false
 Save-Matrix
 [IO.File]::WriteAllText((Join-Path $out 'FAILURE.txt'),($_|Out-String),(New-Object Text.UTF8Encoding($false)))
 throw
} finally {
 Remove-Item -LiteralPath $driverHome -Recurse -Force -ErrorAction SilentlyContinue
}
