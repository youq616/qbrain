param()
# Additive cross-test linker, using this invocation's original direct-cl objects.
# Run only after build-tests-cl.ps1 completed in the same clean checkout/job.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ObjDir = Join-Path $Root 'build\cl\obj'
$Out = Join-Path $Root 'build\n49c-direct'
if (Test-Path $Out) { throw 'Fresh direct-test output directory required.' }
New-Item -ItemType Directory -Path $Out | Out-Null
$original = Get-Content (Join-Path $Root 'scripts\build-tests-cl.ps1') -Raw
$match = [regex]::Match($original, '(?s)\$prodObjs\s*=\s*@\((.*?)\)\s*\|\s*ForEach-Object')
if (-not $match.Success) { throw 'Original production object array missing.' }
$names = @([regex]::Matches($match.Groups[1].Value, '"([A-Za-z0-9_]+)"') | ForEach-Object { $_.Groups[1].Value })
if ($names.Count -lt 40 -or @($names | Select-Object -Unique).Count -ne $names.Count) { throw 'Invalid object inventory.' }
$objects = @($names | ForEach-Object {
  $p = Join-Path $ObjDir ($_.ToString() + '.obj')
  if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Missing current production object: $_" }
  '"' + $p + '"'
})
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
$vcvars = Join-Path $install 'VC\Auxiliary\Build\vcvarsall.bat'
if (-not (Test-Path -LiteralPath $vcvars)) { throw 'Official MSVC toolchain unavailable.' }
# Same explicit/discovered PG roots as the original scripts; no connection is made.
$candidates = New-Object System.Collections.Generic.List[string]
if ($env:QBRAIN_PG_ROOT) { $candidates.Add($env:QBRAIN_PG_ROOT) }
foreach ($base in @('D:/PostgreSQL', 'C:/Program Files/PostgreSQL')) {
  if (-not (Test-Path $base)) { continue }
  $dirs = Get-ChildItem $base -Directory | Where-Object { $_.Name -match '^\d+' } |
    Sort-Object { [long]($_.Name -replace '^(\d+).*$','$1') } -Descending
  foreach ($d in $dirs) { $candidates.Add($d.FullName) }
}
$pgDefine = ''; $pgLink = ''
foreach ($candidate in $candidates) {
  if ((Test-Path "$candidate/include/libpq-fe.h") -and (Test-Path "$candidate/lib/libpq.lib")) {
    $pgDefine = "/I`"$candidate/include`" /DQBRAIN_WITH_PG=1"
    $pgLink = "/DELAYLOAD:libpq.dll `"$candidate/lib/libpq.lib`" delayimp.lib"
    break
  }
}
$source = Join-Path $Root 'tests\test_client_retrieval_integration.cpp'
$objectList = $objects -join ' '
$batch = @"
@echo off
call "$vcvars" x64
if errorlevel 1 exit /b 1
cd /d "$Out"
cl /nologo /std:c++20 /EHsc /O2 /utf-8 /I"$Root\include" /I"$Root\third_party" /I"$Root\third_party\sqlite\sqlite-amalgamation-3460100" $pgDefine /DUNICODE /D_UNICODE /DNOMINMAX /DWIN32_LEAN_AND_MEAN /DSQLITE_ENABLE_FTS5 /c "$source"
if errorlevel 1 exit /b 1
link /nologo /OUT:qbrain_client_retrieval_integration_tests.exe /MANIFEST:NO $objectList test_client_retrieval_integration.obj winhttp.lib bcrypt.lib shell32.lib ole32.lib advapi32.lib ws2_32.lib $pgLink
if errorlevel 1 exit /b 1
qbrain_client_retrieval_integration_tests.exe
exit /b %ERRORLEVEL%
"@
$batchPath = Join-Path $Out 'run.cmd'
Set-Content -LiteralPath $batchPath -Value $batch -Encoding ASCII
& cmd /d /s /c $batchPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$names | ConvertTo-Json | Set-Content (Join-Path $Out 'linked-production-objects.json')
exit 0
