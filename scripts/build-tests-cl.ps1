param(
  [switch]$SkipProductionBuild,
  [string[]]$TestSources,
  [switch]$BuildOnly,
  [switch]$RunOnly,
  [string]$ProductionManifest,
  [string]$PhaseContext,
  [string]$RunReport
)

$ErrorActionPreference = "Stop"

function Find-VcvarsAll {
  $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
  if (Test-Path $vswhere) {
    $install = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($install) {
      $candidate = Join-Path $install "VC\Auxiliary\Build\vcvarsall.bat"
      if (Test-Path $candidate) { return $candidate }
    }
  }
  $known = @(
    "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
    "C:\Program Files\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
    "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
    "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat",
    "C:\Program Files\Microsoft Visual Studio\18\Enterprise\VC\Auxiliary\Build\vcvarsall.bat",
    "C:\Program Files\Microsoft Visual Studio\18\Professional\VC\Auxiliary\Build\vcvarsall.bat"
  )
  foreach ($path in $known) {
    if (Test-Path $path) { return $path }
  }
  throw "MSVC not found: vswhere.exe reported no VC tools and no known BuildTools vcvarsall.bat exists. Install Visual Studio Build Tools with the 'Desktop development with C++' workload."
}

function Find-PgRoot {
  $candidates = New-Object System.Collections.Generic.List[string]
  if ($env:QBRAIN_PG_ROOT) { $candidates.Add($env:QBRAIN_PG_ROOT) }
  foreach ($base in @("D:\PostgreSQL", "C:\Program Files\PostgreSQL")) {
    if (-not (Test-Path $base)) { continue }
    $versioned = Get-ChildItem $base -Directory | Where-Object { $_.Name -match '^\d+' } |
      Sort-Object { [long]($_.Name -replace '^(\d+).*$','$1') } -Descending
    foreach ($d in $versioned) { $candidates.Add($d.FullName) }
  }
  foreach ($c in $candidates) {
    if ((Test-Path (Join-Path $c "include\libpq-fe.h")) -and
        (Test-Path (Join-Path $c "lib\libpq.lib"))) {
      return $c
    }
  }
  return $null
}
function Assert-QbrainPhaseArguments {
  param([System.Collections.IDictionary]$Options, [object[]]$RemainingArguments)
  if ($RemainingArguments.Count) { throw "Unconsumed arguments." }
  foreach ($key in $Options.Keys) {
    if (@('SkipProductionBuild','TestSources','BuildOnly','RunOnly','ProductionManifest','PhaseContext','RunReport') -cnotcontains $key) { throw "Unknown argument." }
  }
  if ($Options.BuildOnly -and $Options.RunOnly) { throw "BuildOnly and RunOnly are exclusive." }
  if ($Options.RunOnly) {
    foreach ($key in @('BuildOnly','SkipProductionBuild','TestSources','ProductionManifest')) {
      if ($Options.ContainsKey($key)) { throw "Invalid RunOnly argument." }
    }
    if (-not $Options.PhaseContext -or -not $Options.RunReport) { throw "RunOnly requires PhaseContext and RunReport." }
  } elseif ($Options.BuildOnly) {
    if (-not $Options.SkipProductionBuild -or -not $Options.ProductionManifest -or -not $Options.PhaseContext) { throw "BuildOnly requires SkipProductionBuild, ProductionManifest and PhaseContext." }
    if ($Options.ContainsKey('TestSources') -or $Options.ContainsKey('RunReport') -or $Options.ContainsKey('RunOnly')) { throw "Invalid BuildOnly argument." }
  } else {
    foreach ($key in @('ProductionManifest','PhaseContext','RunReport')) {
      if ($Options.ContainsKey($key)) { throw "Phase argument requires an explicit mode." }
    }
  }
}

function Get-QbrainFields {
  param($Value, [string[]]$Names)
  if ($null -eq $Value -or $Value.GetType() -ne [System.Management.Automation.PSCustomObject]) { throw "Expected report object." }
  $actual = @($Value.PSObject.Properties.Name)
  if ($actual.Count -ne $Names.Count) { throw "Report key count." }
  foreach ($name in $Names) {
    $found = $false
    foreach ($key in $actual) { if ([StringComparer]::Ordinal.Equals($name,$key)) { $found = $true } }
    if (-not $found) { throw "Report key mismatch." }
  }
}

function Assert-QbrainUInt {
  param($Value, [long]$Minimum = 0, [long]$Maximum = 9007199254740991)
  if ($null -eq $Value -or ($Value.GetType() -ne [int] -and $Value.GetType() -ne [long])) { throw "Expected ordinary integer." }
  if ($Value -lt $Minimum -or $Value -gt $Maximum) { throw "Integer range." }
}

function Assert-QbrainString {
  param($Value, [string]$Pattern)
  if ($Value -isnot [string] -or $Value -cnotmatch $Pattern) { throw "Report string." }
}

function Assert-QbrainDescriptor {
  param($Value, [switch]$PathIdentity)
  if ($PathIdentity) {
    Get-QbrainFields $Value @('bytes','sha256')
    Assert-QbrainUInt $Value.bytes 1 131072
  } else {
    Get-QbrainFields $Value @('size','sha256')
    Assert-QbrainUInt $Value.size 1
  }
  Assert-QbrainString $Value.sha256 '^[0-9a-f]{64}$'
}

function Assert-QbrainIdentity {
  param($Value)
  Get-QbrainFields $Value @('commit','tree','run_id','run_attempt','job_key','job_label')
  Assert-QbrainString $Value.commit '^[0-9a-f]{40}$'
  Assert-QbrainString $Value.tree '^[0-9a-f]{40}$'
  Assert-QbrainString $Value.run_id '^[0-9]{1,20}$'
  Assert-QbrainString $Value.run_attempt '^[0-9]{1,20}$'
  Assert-QbrainString $Value.job_key '^windows-msvc$'
  Assert-QbrainString $Value.job_label '^windows-msvc$'
}

function ConvertTo-QbrainCanonical {
  param($Value)
  if ($null -eq $Value) { return 'null' }
  if ($Value -is [string]) {
    if ($Value.Length -gt 128 -or $Value -cmatch '[^\x20-\x21\x23-\x5b\x5d-\x7e]') { throw "Noncanonical string." }
    return '"' + $Value + '"'
  }
  if ($Value -is [bool]) { if ($Value) { return 'true' }; return 'false' }
  if ($Value.GetType() -eq [int] -or $Value.GetType() -eq [long]) {
    Assert-QbrainUInt $Value
    return $Value.ToString([Globalization.CultureInfo]::InvariantCulture)
  }
  if ($Value.GetType() -eq [object[]]) {
    $items = foreach ($item in $Value) { ConvertTo-QbrainCanonical $item }
    return '[' + ($items -join ',') + ']'
  }
  if ($Value.GetType() -ne [System.Management.Automation.PSCustomObject]) { throw "Noncanonical type." }
  [string[]]$keys = @($Value.PSObject.Properties.Name)
  [Array]::Sort($keys,[StringComparer]::Ordinal)
  $items = foreach ($key in $keys) { (ConvertTo-QbrainCanonical $key) + ':' + (ConvertTo-QbrainCanonical $Value.PSObject.Properties[$key].Value) }
  return '{' + ($items -join ',') + '}'
}

function Assert-QbrainPhaseReport {
  param($Value, [ValidateSet('objects','build','run')][string]$Role)
  $common = @('schema','state','identity','failure')
  $extra = switch ($Role) {
    objects { @('produced','consumed','production_executable') }
    build { @('mode','architecture','cwd_role','vcvars','runtime_prefix','production_objects','production_executable','canonical_binary') }
    run { @('mode','build_context','canonical_binary','context_matched','test_exit') }
  }
  Get-QbrainFields $Value ($common + $extra)
  $schema = @{objects='qbrain-n49d-build-objects-v1';build='qbrain-n49d-build-context-v1';run='qbrain-n49d-run-context-v1'}[$Role]
  Assert-QbrainString $Value.schema ('^' + $schema + '$')
  Assert-QbrainString $Value.state '^(ready|prepared|failed)$'
  Assert-QbrainIdentity $Value.identity
  if ($Value.state -ceq 'failed') {
    $reasons = switch ($Role) {
      objects { 'missing-object|object-type|object-inventory|object-changed|binary-unavailable|deadline|storage' }
      build { 'input-invalid|context-mismatch|object-mismatch|compile-failed|copy-failed|binary-unavailable|binary-mismatch|deadline|storage' }
      run { 'input-invalid|context-mismatch|binary-mismatch|launch-failed|test-nonzero|deadline|storage' }
    }
    Assert-QbrainString $Value.failure ('^(' + $reasons + ')$')
  } elseif ($null -ne $Value.failure) { throw "Unexpected failure." }
  $ready = $Value.state -ceq 'ready'
  if ($Role -ceq 'objects') {
    if ($null -eq $Value.produced -or $Value.produced.GetType() -ne [object[]] -or $null -eq $Value.consumed -or $Value.consumed.GetType() -ne [object[]]) { throw "Expected object arrays." }
    if (-not $ready) {
      if ($Value.produced.Count -or $Value.consumed.Count -or $null -ne $Value.production_executable) { throw "Partial object inventory." }
      return
    }
    $inventory = Get-QbrainTestInputs
    [string[]]$produced = @($inventory.Produced | ForEach-Object { $_ + '.obj' })
    [string[]]$consumed = @($inventory.Consumed | ForEach-Object { $_ + '.obj' })
    [Array]::Sort($produced,[StringComparer]::Ordinal); [Array]::Sort($consumed,[StringComparer]::Ordinal)
    if ($Value.produced.Count -ne 53 -or $Value.consumed.Count -ne 51) { throw "Object inventory count." }
    for ($i=0; $i -lt 53; $i++) {
      $d = $Value.produced[$i]
      Get-QbrainFields $d @('name','size','sha256')
      Assert-QbrainString $d.name '^[A-Za-z0-9_]{1,64}\.obj$'
      if ($d.name -cne $produced[$i]) { throw "Produced inventory." }
      Assert-QbrainUInt $d.size 1; Assert-QbrainString $d.sha256 '^[0-9a-f]{64}$'
    }
    for ($i=0; $i -lt 51; $i++) {
      if ($Value.consumed[$i] -isnot [string] -or $Value.consumed[$i] -cne $consumed[$i]) { throw "Consumed inventory." }
    }
    Assert-QbrainDescriptor $Value.production_executable
    return
  }
  if ($Role -ceq 'build') {
    Assert-QbrainString $Value.mode '^build-only$'; Assert-QbrainString $Value.architecture '^x64$'; Assert-QbrainString $Value.cwd_role '^build/cl$'
    if ($null -ne $Value.vcvars) {
      Get-QbrainFields $Value.vcvars @('path','file')
      Assert-QbrainDescriptor $Value.vcvars.path -PathIdentity; Assert-QbrainDescriptor $Value.vcvars.file
    } elseif ($ready) { throw "Missing vcvars observation." }
    if ($null -ne $Value.runtime_prefix) {
      Get-QbrainFields $Value.runtime_prefix @('present','identity')
      if ($Value.runtime_prefix.present -isnot [bool]) { throw "Runtime presence type." }
      if ($Value.runtime_prefix.present) { Assert-QbrainDescriptor $Value.runtime_prefix.identity -PathIdentity }
      elseif ($null -ne $Value.runtime_prefix.identity) { throw "Unexpected runtime identity." }
    } elseif ($ready) { throw "Missing runtime observation." }
    foreach ($key in @('production_objects','production_executable','canonical_binary')) {
      if ($null -ne $Value.$key) { Assert-QbrainDescriptor $Value.$key }
      elseif ($ready) { throw "Missing build descriptor." }
    }
  } else {
    Assert-QbrainString $Value.mode '^run-only$'
    foreach ($key in @('build_context','canonical_binary')) {
      if ($null -ne $Value.$key) { Assert-QbrainDescriptor $Value.$key }
      elseif ($ready) { throw "Missing run descriptor." }
    }
    if ($ready) {
      if ($Value.context_matched -isnot [bool] -or -not $Value.context_matched) { throw "Run context unmatched." }
      Assert-QbrainUInt $Value.test_exit 0 0
    } elseif ($null -ne $Value.context_matched -or $null -ne $Value.test_exit) { throw "Uncompleted run facts." }
  }
}

function ConvertFrom-QbrainPhaseBytes {
  param([byte[]]$Bytes, [ValidateSet('objects','build','run')][string]$Role)
  $cap = if ($Role -ceq 'objects') { 12288 } else { 2048 }
  if ($Bytes.Length -lt 3 -or $Bytes.Length -gt $cap) { throw "Report byte cap." }
  foreach ($b in $Bytes) { if ($b -gt 126 -or $b -eq 92 -or ($b -lt 32 -and $b -ne 10 -and $b -ne 13)) { throw "Report byte alphabet." } }
  $text = [Text.Encoding]::ASCII.GetString($Bytes)
  $suffix = if ($text.EndsWith("`r`n",[StringComparison]::Ordinal)) { "`r`n" } else { "`n" }
  if (-not $text.EndsWith($suffix,[StringComparison]::Ordinal)) { throw "Report newline." }
  $body = $text.Substring(0,$text.Length-$suffix.Length)
  if ($body.Contains("`r") -or $body.Contains("`n")) { throw "Report newline form." }
  $quoted=$false; $length=0; $depth=0; $containers=0; $number=0
  foreach ($c in $body.ToCharArray()) {
    if ($quoted) {
      if ($c -ceq '"') { $quoted=$false } else { $length++; if ($length -gt 128) { throw "String token limit." } }
    } elseif ($c -ceq '"') { $quoted=$true; $length=0; $number=0 }
    elseif ($c -ceq '{' -or $c -ceq '[') { $depth++; $containers++; $number=0; if ($depth -gt 6 -or $containers -gt 256) { throw "Container limit." } }
    elseif ($c -ceq '}' -or $c -ceq ']') { $depth--; $number=0; if ($depth -lt 0) { throw "Container syntax." } }
    elseif ('0123456789+-.eE'.Contains([string]$c)) { $number++; if ($number -gt 16) { throw "Numeric token limit." } }
    else { $number=0 }
  }
  if ($quoted -or $depth -ne 0) { throw "Report syntax." }
  $value = ConvertFrom-Json -InputObject $body -ErrorAction Stop
  Assert-QbrainPhaseReport $value $Role
  $canonical = (ConvertTo-QbrainCanonical $value) + $suffix
  $expected = [Text.Encoding]::ASCII.GetBytes($canonical)
  if ($expected.Length -ne $Bytes.Length) { throw "Noncanonical report." }
  for ($i=0; $i -lt $Bytes.Length; $i++) { if ($Bytes[$i] -ne $expected[$i]) { throw "Noncanonical report." } }
  return $value
}

function Assert-QbrainRegularPath {
  param([string]$Path, [switch]$Directory, [switch]$AllowMissingLeaf)
  $full = [IO.Path]::GetFullPath($Path)
  $item = $null
  if ([IO.File]::Exists($full) -or [IO.Directory]::Exists($full)) {
    $item = Get-Item -LiteralPath $full -Force -ErrorAction Stop
    if (($Directory -and -not $item.PSIsContainer) -or (-not $Directory -and $item.PSIsContainer)) { throw "Path kind." }
  } elseif (-not $AllowMissingLeaf) { throw "Missing path." }
  $cursor = $full
  while ($cursor) {
    if ($cursor -ne $full -or $null -ne $item) {
      $part = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
      if (($part.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Reparse path." }
    }
    $cursor = [IO.Path]::GetDirectoryName($cursor)
  }
}

function Get-QbrainFileDescriptor {
  param([string]$Path)
  Assert-QbrainRegularPath $Path
  $stream = [IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  $hash = [Security.Cryptography.SHA256]::Create()
  try {
    $size = $stream.Length
    if ($size -le 0 -or $size -gt 9007199254740991) { throw "File size." }
    $digest = [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-','').ToLowerInvariant()
    if ($stream.Length -ne $size) { throw "File changed." }
    return [pscustomobject]@{size=[long]$size;sha256=$digest}
  } finally { $hash.Dispose(); $stream.Dispose() }
}

function Get-QbrainPathIdentity {
  param([string]$Path)
  $bytes = [Text.Encoding]::UTF8.GetBytes($Path)
  if ($bytes.Length -lt 1 -or $bytes.Length -gt 131072) { throw "Path identity size." }
  $hash = [Security.Cryptography.SHA256]::Create()
  try { return [pscustomobject]@{bytes=[long]$bytes.Length;sha256=[BitConverter]::ToString($hash.ComputeHash($bytes)).Replace('-','').ToLowerInvariant()} }
  finally { $hash.Dispose() }
}

function Read-QbrainPhaseReport {
  param([string]$Path, [ValidateSet('objects','build','run')][string]$Role)
  Assert-QbrainRegularPath $Path
  $cap = if ($Role -ceq 'objects') { 12288 } else { 2048 }
  $stream = [IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
  try {
    if ($stream.Length -gt $cap) { throw "Report byte cap." }
    $bytes = New-Object byte[] ([int]$stream.Length)
    $offset=0
    while ($offset -lt $bytes.Length) { $n=$stream.Read($bytes,$offset,$bytes.Length-$offset); if ($n -eq 0) { throw "Short report read." }; $offset += $n }
    if ($stream.ReadByte() -ne -1) { throw "Growing report." }
    return ConvertFrom-QbrainPhaseBytes $bytes $Role
  } finally { $stream.Dispose() }
}

function Write-QbrainPhaseReport {
  param([string]$Path, $Value, [ValidateSet('objects','build','run')][string]$Role)
  Assert-QbrainPhaseReport $Value $Role
  $bytes = [Text.Encoding]::ASCII.GetBytes((ConvertTo-QbrainCanonical $Value) + "`n")
  $null = ConvertFrom-QbrainPhaseBytes $bytes $Role
  Assert-QbrainRegularPath $Path -AllowMissingLeaf
  $temporary = $Path + '.tmp-' + $PID
  $stream = [IO.File]::Open($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  try { $stream.Write($bytes,0,$bytes.Length); $stream.Flush() } finally { $stream.Dispose() }
  try {
    if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temporary,$Path,[System.Management.Automation.Language.NullString]::Value) } else { [IO.File]::Move($temporary,$Path) }
    $observed = Read-QbrainPhaseReport $Path $Role
    if ((ConvertTo-QbrainCanonical $observed) -cne (ConvertTo-QbrainCanonical $Value)) { throw "Report readback mismatch." }
  } finally { if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) } }
}

function Assert-QbrainReportPaths {
  param($Options)
  $names = @{ProductionManifest='direct-production-objects.json';PhaseContext='direct-tests-build-context.json';RunReport='direct-tests-run-context.json'}
  $parent = $null
  foreach ($key in @('ProductionManifest','PhaseContext','RunReport')) {
    if (-not $Options.ContainsKey($key)) { continue }
    $path = $Options[$key]
    if (-not [IO.Path]::IsPathRooted($path)) { throw "Absolute report path required." }
    $full = [IO.Path]::GetFullPath($path)
    if (-not [StringComparer]::OrdinalIgnoreCase.Equals($path,$full) -or [IO.Path]::GetFileName($full) -cne $names[$key]) { throw "Report role path." }
    $directory = [IO.Path]::GetDirectoryName($full)
    if ([IO.Path]::GetFileName($directory) -cne 'reports') { throw "Report directory role." }
    Assert-QbrainRegularPath $directory -Directory
    Assert-QbrainRegularPath $full -AllowMissingLeaf
    if ($null -ne $parent -and -not [StringComparer]::OrdinalIgnoreCase.Equals($parent,$directory)) { throw "Report roots differ." }
    $parent=$directory
  }
}

function Get-QbrainSelectedContext {
  param($Context)
  $runtime = [pscustomobject]@{present=[bool]$Context.PgRoot;identity=$null}
  if ($runtime.present) { $runtime.identity = Get-QbrainPathIdentity ($Context.PgRoot + '\bin;') }
  return [pscustomobject]@{vcvars=[pscustomobject]@{path=(Get-QbrainPathIdentity $Context.Vcvars);file=(Get-QbrainFileDescriptor $Context.Vcvars)};runtime_prefix=$runtime}
}

function Assert-QbrainEqual {
  param($Actual,$Expected)
  if ((ConvertTo-QbrainCanonical $Actual) -cne (ConvertTo-QbrainCanonical $Expected)) { throw "Descriptor mismatch." }
}

function Assert-QbrainProductionInputs {
  param($Context,$Manifest)
  Assert-QbrainEqual (Get-QbrainFileDescriptor (Join-Path $Context.Out 'qbrain.exe')) $Manifest.production_executable
  foreach ($entry in $Manifest.produced) {
    if ($Manifest.consumed -ccontains $entry.name) {
      $expected=[pscustomobject]@{size=$entry.size;sha256=$entry.sha256}
      Assert-QbrainEqual (Get-QbrainFileDescriptor (Join-Path $Context.ObjDir $entry.name)) $expected
    }
  }
}

function Invoke-QbrainNativeBatch {
  param([string]$Batch, $Result)
  $batPath = Join-Path ([IO.Path]::GetTempPath()) "qbrain-tests-cl-$PID.bat"
  Set-Content -LiteralPath $batPath -Value $Batch -Encoding ASCII
  try {
    cmd /d /s /c $batPath
    $Result.ExitCode = $LASTEXITCODE
  } finally { Remove-Item -LiteralPath $batPath -Force -ErrorAction SilentlyContinue }
}

function Invoke-QbrainProductionBuild {
  param($Context, $Result)
  & (Join-Path $Context.Root 'scripts\build-cl.ps1')
  $Result.ExitCode = $LASTEXITCODE
}

function Resolve-QbrainBuildContext {
  $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
  $Out = Join-Path $Root "build\cl"
  return [pscustomobject]@{
    Root=$Root; Out=$Out; ObjDir=(Join-Path $Out 'obj'); Vcvars=(Find-VcvarsAll)
    Sqlite=(Join-Path $Root 'third_party\sqlite\sqlite-amalgamation-3460100')
    Inc=(Join-Path $Root 'include'); Third=(Join-Path $Root 'third_party'); PgRoot=(Find-PgRoot)
  }
}

function Get-QbrainTestInputs {
$defaultTestSources = @(
  "tests\test_main.cpp",
  "tests\test_n43.cpp",
  "tests\test_n45.cpp",
  "tests\test_n46b.cpp",
  "tests\test_n46c.cpp",
  "tests\test_n46d.cpp",
  "tests\test_n47a.cpp",
  "tests\test_n47b.cpp",
  "tests\test_n47c.cpp",
  "tests\test_n47d.cpp",
  "tests\test_n47e.cpp",
  "tests\test_n47f.cpp",
  "tests\test_n47g.cpp",
  "tests\test_n47h.cpp",
  "tests\test_n47i.cpp",
  "tests\test_n47j.cpp",
  "tests\test_n47k.cpp",
  "tests\test_n47l.cpp",
  "tests\test_n46f.cpp",
  "tests\test_rrf.cpp",
  "tests\test_vector.cpp",
  "tests\test_chunker.cpp",
  "tests\test_extract.cpp",
  "tests\test_storage.cpp",
  "tests\test_mcp.cpp",
  "tests\test_rerank.cpp",
  "tests\test_minions.cpp",
  "tests\test_migration_v6.cpp",
  "tests\test_n12_dream.cpp",
  "tests\test_live_sync.cpp",
  "tests\test_n13.cpp",
  "tests\test_codeintel.cpp",
  "tests\test_analytics.cpp",
  "tests\test_n19.cpp",
  "tests\test_n20.cpp",
  "tests\test_n22.cpp",
  "tests\test_n23.cpp",
  "tests\test_n20_23.cpp",
  "tests\test_n24_25.cpp",
  "tests\test_n26_27.cpp",
  "tests\test_wave4.cpp",
  "tests\test_wave5.cpp",
  "tests\test_doctor.cpp",
  "tests\test_n14.cpp",
  "tests\test_n15.cpp",
  "tests\test_n16.cpp",
  "tests\test_n17.cpp",
  "tests\test_n18.cpp",
  "tests\test_n30.cpp",
  "tests\test_n31.cpp",
  "tests\test_n32.cpp",
  "tests\test_n34.cpp",
  "tests\test_n33.cpp",
  "tests\test_n35.cpp",
  "tests\test_n36.cpp",
  "tests\test_n37.cpp",
  "tests\test_n38.cpp",
  "tests\test_n39.cpp",
  "tests\n42\test_foundation.cpp"
)
$prodObjNames = @(
  "paths","hash","log","string_util","time_util","database","migrate","pg_backend","transaction_state","types","brain",
  "extract","traverse","analytics","scan","astlite","packs","lint","store","image_meta","vector","rrf","hybrid","directory","rerank","minions","embedding_queue","dream",
  "chunker","markdown","import","http_client","embed","chat","registry","handlers","memory_ops","session_memory","fact_store","hook","diagnostics","context","context_ops",
  "inbox_watch","live_sync","jsonrpc","server","auth","http_server","commands","sqlite3"
)
  return [pscustomobject]@{TestSources=[object[]]$defaultTestSources;Consumed=[object[]]$prodObjNames;Produced=[object[]]($prodObjNames + @('app','main'))}
}

function New-QbrainTestsBatch {
  param($Context, [string]$RunDir, [string[]]$TestSources, [switch]$BuildOnly)
  $Root=$Context.Root; $Out=$Context.Out; $ObjDir=$Context.ObjDir; $vcvars=$Context.Vcvars
  $sqlite=$Context.Sqlite; $inc=$Context.Inc; $third=$Context.Third; $PgRoot=$Context.PgRoot
  $inputs=Get-QbrainTestInputs
  $selected=New-Object System.Collections.Generic.List[string]
  foreach ($s in $inputs.TestSources) { $selected.Add($s) }
  if ($TestSources) {
    foreach ($s in $TestSources) {
      $rel=if ([IO.Path]::IsPathRooted($s)) { $s.Substring($Root.Length + 1) } else { $s }
      if (-not $selected.Contains($rel)) { $selected.Add($rel) }
    }
  }
  $tests=$selected | ForEach-Object { Join-Path $Root $_ }
  $testList=($tests | ForEach-Object { "`"$_`"" }) -join ' '
  $testObjList=($selected | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_) + '.obj' }) -join ' '
  $prodObjs=$inputs.Consumed | ForEach-Object { "`"$ObjDir\$_.obj`"" }
  $prodObjList=$prodObjs -join ' '
  $pgDefine=''; $pgLink=''; $pgPath=''
  if ($PgRoot) {
    $pgDefine="/I`"$PgRoot\include`" /DQBRAIN_WITH_PG=1"
    $pgLink="/DELAYLOAD:libpq.dll `"$PgRoot\lib\libpq.lib`" delayimp.lib"
    $pgPath="set PATH=$PgRoot\bin;%PATH%`r`n"
  }
  $runTail='exit /b 0'
  if (-not $BuildOnly) {
    $runTail=@"
cd /d "$Out"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
$($pgPath)qbrain_tests.exe
exit /b
"@
  }
$bat = @"
@echo off
call "$vcvars" x64
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
cd /d "$RunDir"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
cl /nologo /std:c++20 /EHsc /O2 /utf-8 /I"$inc" /I"$third" /I"$sqlite" $pgDefine /DUNICODE /D_UNICODE /DNOMINMAX /DWIN32_LEAN_AND_MEAN /DSQLITE_ENABLE_FTS5 /c $testList
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
link /nologo /OUT:qbrain_tests.exe /MANIFEST:NO $prodObjList $testObjList winhttp.lib bcrypt.lib shell32.lib ole32.lib advapi32.lib ws2_32.lib $pgLink
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
copy /y qbrain_tests.exe "$Out\qbrain_tests.exe" >nul
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
echo TESTS_BUILD_OK
$runTail
"@
  return $bat
}

function Invoke-QbrainBuildPhase {
  param($Options,$Context,[scriptblock]$NativeExecutor,[scriptblock]$ProductionBuilder,$Result)
  $report=$null; $reason='input-invalid'
  $runDir=$null
  try {
    if ($Options.BuildOnly) {
      Assert-QbrainReportPaths $Options
      $manifest=Read-QbrainPhaseReport $Options.ProductionManifest objects
      if ($manifest.state -cne 'ready') { throw "Production not ready." }
      $report=[pscustomobject]@{schema='qbrain-n49d-build-context-v1';state='prepared';identity=$manifest.identity;mode='build-only';architecture='x64';cwd_role='build/cl';vcvars=$null;runtime_prefix=$null;production_objects=$null;production_executable=$null;canonical_binary=$null;failure=$null}
      Write-QbrainPhaseReport $Options.PhaseContext $report build
      $report.production_objects=Get-QbrainFileDescriptor $Options.ProductionManifest
      $selected=Get-QbrainSelectedContext $Context
      $report.vcvars=$selected.vcvars; $report.runtime_prefix=$selected.runtime_prefix
      $reason='object-mismatch'; Assert-QbrainProductionInputs $Context $manifest
      $report.production_executable=$manifest.production_executable
      Write-QbrainPhaseReport $Options.PhaseContext $report build
    } elseif (-not $Options.SkipProductionBuild) {
      & $ProductionBuilder $Context $Result
      if ($Result.ExitCode -ne 0) { return }
    }
    if (-not (Test-Path (Join-Path $Context.ObjDir 'commands.obj'))) { throw "Production objects missing. Run scripts\build-cl.ps1 (or drop -SkipProductionBuild)." }
    $runDir=Join-Path ([IO.Path]::GetTempPath()) "qbrain-tests-cl-$PID-$([DateTime]::UtcNow.Ticks)"
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
    $batch=New-QbrainTestsBatch $Context $runDir $Options.TestSources -BuildOnly:([bool]$Options.BuildOnly)
    $reason='compile-failed'
    & $NativeExecutor $batch $Result
    if ($Result.ExitCode -ne 0) { throw "Native build/test failed." }
    if ($Options.BuildOnly) {
      $reason='object-mismatch'; Assert-QbrainProductionInputs $Context $manifest
      Assert-QbrainEqual (Get-QbrainFileDescriptor $Options.ProductionManifest) $report.production_objects
      $reason='binary-unavailable'; $report.canonical_binary=Get-QbrainFileDescriptor (Join-Path $Context.Out 'qbrain_tests.exe')
      $reason='storage'; Write-QbrainPhaseReport $Options.PhaseContext $report build
    }
  } catch {
    if ($Result.ExitCode -eq 0) { $Result.ExitCode=1 }
    if ($null -ne $report) {
      $report.state='failed'; $report.failure=$reason
      try { Write-QbrainPhaseReport $Options.PhaseContext $report build } catch { Write-Error 'Build context publication unavailable.' -ErrorAction Continue }
    }
    Write-Error 'Build phase failed.' -ErrorAction Continue
  } finally {
    if ($null -ne $runDir) { Remove-Item -LiteralPath $runDir -Recurse -Force -ErrorAction SilentlyContinue }
  }
}

function Invoke-QbrainRunPhase {
  param($Options,$Context,[scriptblock]$NativeExecutor,$Result)
  $report=$null; $reason='input-invalid'
  try {
    Assert-QbrainReportPaths $Options
    $prepared=Read-QbrainPhaseReport $Options.PhaseContext build
    if ($prepared.state -cne 'ready') { throw "Build context not ready." }
    $report=[pscustomobject]@{schema='qbrain-n49d-run-context-v1';state='prepared';identity=$prepared.identity;mode='run-only';build_context=(Get-QbrainFileDescriptor $Options.PhaseContext);canonical_binary=$prepared.canonical_binary;context_matched=$null;test_exit=$null;failure=$null}
    Write-QbrainPhaseReport $Options.RunReport $report run
    $reason='context-mismatch'; $selected=Get-QbrainSelectedContext $Context
    Assert-QbrainEqual $selected.vcvars $prepared.vcvars
    Assert-QbrainEqual $selected.runtime_prefix $prepared.runtime_prefix
    $binary=Join-Path $Context.Out 'qbrain_tests.exe'
    $reason='binary-mismatch'; Assert-QbrainEqual (Get-QbrainFileDescriptor $binary) $prepared.canonical_binary
    Assert-QbrainEqual (Get-QbrainFileDescriptor $Options.PhaseContext) $report.build_context
    $vcvars=$Context.Vcvars; $out=$Context.Out; $pgPath=''
    if ($Context.PgRoot) { $pgPath="set PATH=$($Context.PgRoot)\bin;%PATH%`r`n" }
    $batch=@"
@echo off
call "$vcvars" x64
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
cd /d "$out"
if errorlevel 1 exit /b 1
if not errorlevel 0 exit /b 1
$($pgPath)"$binary"
exit /b
"@
    $reason='launch-failed'; & $NativeExecutor $batch $Result
    $reason='test-nonzero'
    if ($Result.ExitCode -ne 0) { throw "Canonical test nonzero." }
    $reason='binary-mismatch'; Assert-QbrainEqual (Get-QbrainFileDescriptor $binary) $prepared.canonical_binary
    $report.state='ready'; $report.context_matched=$true; $report.test_exit=0
    $reason='storage'; Write-QbrainPhaseReport $Options.RunReport $report run
  } catch {
    if ($Result.ExitCode -eq 0) { $Result.ExitCode=1 }
    if ($null -ne $report) {
      $report.state='failed'; $report.context_matched=$null; $report.test_exit=$null; $report.failure=$reason
      try { Write-QbrainPhaseReport $Options.RunReport $report run } catch { Write-Error 'Run context publication unavailable.' -ErrorAction Continue }
    }
    Write-Error 'Run phase failed.' -ErrorAction Continue
  }
}

function Invoke-QbrainTestsDispatcher {
  param([System.Collections.IDictionary]$Options,[object[]]$RemainingArguments,[scriptblock]$ResolveContext,[scriptblock]$NativeExecutor,[scriptblock]$ProductionBuilder,$Result)
  Assert-QbrainPhaseArguments $Options $RemainingArguments
  $context=& $ResolveContext
  if ($Options.RunOnly) { Invoke-QbrainRunPhase $Options $context $NativeExecutor $Result }
  else { Invoke-QbrainBuildPhase $Options $context $NativeExecutor $ProductionBuilder $Result }
}

$result=[pscustomobject]@{ExitCode=0}
Invoke-QbrainTestsDispatcher -Options $PSBoundParameters -RemainingArguments $args -ResolveContext { Resolve-QbrainBuildContext } -NativeExecutor { param($batch,$result) Invoke-QbrainNativeBatch $batch $result } -ProductionBuilder { param($context,$result) Invoke-QbrainProductionBuild $context $result } -Result $result
exit $result.ExitCode
