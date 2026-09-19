# Windows PowerShell 5.1 and PowerShell 7: byte-preserving UTF-8 process bridge.
# No shell interpolation, profile loading, global encoding changes or WSL needed.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][AllowEmptyCollection()][AllowEmptyString()][string[]]$ArgumentList,
    [AllowEmptyString()][string]$InputJson = '',
    [ValidateRange(100,120000)][int]$TimeoutMilliseconds = 10000,
    [switch]$IncludeDiagnostics
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'This bridge requires native Windows.'
}
# Quote each argument according to the MSVC CRT command-line rules. Arguments
# never pass through cmd.exe, Invoke-Expression or a PowerShell command string.
function ConvertTo-CrtArgument([AllowEmptyString()][string]$Value) {
    if ($Value.IndexOf([char]0) -ge 0) { throw 'NUL is not a valid process argument.' }
    $builder = New-Object System.Text.StringBuilder
    [void]$builder.Append('"')
    $slashes = 0
    foreach ($ch in $Value.ToCharArray()) {
        if ($ch -eq [char]92) { $slashes++; continue }
        if ($ch -eq [char]34) {
            [void]$builder.Append(('\' * (2 * $slashes + 1)))
            [void]$builder.Append('"')
        } else {
            if ($slashes) { [void]$builder.Append(('\' * $slashes)) }
            [void]$builder.Append($ch)
        }
        $slashes = 0
    }
    if ($slashes) { [void]$builder.Append(('\' * (2 * $slashes))) }
    [void]$builder.Append('"')
    return $builder.ToString()
}
if ($InputJson.Length -gt 262144) { throw 'Input JSON exceeds the transport bound.' }
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
$bytes = $utf8.GetBytes($InputJson)
if ($bytes.Length -gt 262144) { throw 'Input JSON exceeds the UTF-8 byte bound.' }
$resolved = (Resolve-Path -LiteralPath $FilePath -ErrorAction Stop).ProviderPath
$location = Get-Location
if ($location.Provider.Name -ne 'FileSystem') {
    throw 'A filesystem working directory is required.'
}
$start = New-Object System.Diagnostics.ProcessStartInfo
$start.FileName = $resolved
# Set-Location is runspace-local; Process.Start otherwise inherits the .NET
# process directory, which can differ from PowerShell's current directory.
# Do not derive this from untrusted hook JSON or modify global CurrentDirectory.
$start.WorkingDirectory = $location.ProviderPath
$start.Arguments = (($ArgumentList | ForEach-Object { ConvertTo-CrtArgument $_ }) -join ' ')
$start.UseShellExecute = $false
$start.CreateNoWindow = $true
$start.RedirectStandardInput = $true
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $true
$start.StandardOutputEncoding = $utf8
$start.StandardErrorEncoding = $utf8
$process = New-Object System.Diagnostics.Process
$process.StartInfo = $start
# Timings begin immediately before Process.Start, as before. Synchronous OS
# startup and the finite cleanup below are not a cancellable wall-clock deadline.
$stdout=$null; $stderr=$null; $writing=$null
$started=$false; $inputClosed=$false
$phase='start'; $failureCode='start_failed'
$stageMilliseconds=[ordered]@{start=$null;input=$null;process=$null;output=$null}
$waitBudgets=[ordered]@{input=$null;process=$null;output=$null}
$clock = [Diagnostics.Stopwatch]::StartNew()
$phaseStart=[long]0
function Get-QbrainRemainingMilliseconds([long]$Budget,[long]$Elapsed) {
    return [int][Math]::Max([long]0,$Budget-$Elapsed)
}
function Get-QbrainTaskState($Task) {
    if($null -eq $Task){return 'not_started'}
    if($Task.IsCanceled){return 'canceled'}
    if($Task.IsFaulted){return 'faulted'}
    if($Task.IsCompleted){return 'completed'}
    return 'running'
}
function Get-QbrainTransportDiagnostic([string]$Code) {
    # Capture before cleanup; do not inspect task results or exception messages.
    # These labels and primitives are the whole shareable payload. No raw data.
    $exited=$null; $exitCode=$null
    if($started){try{$exited=[bool]$process.HasExited;if($exited){$exitCode=[int]$process.ExitCode}}catch{}}
    return [PSCustomObject][ordered]@{
        schema='qbrain-transport-diagnostic-v1';code=$Code;phase=$phase
        timeout_ms=$TimeoutMilliseconds;elapsed_ms=[long]$clock.ElapsedMilliseconds
        stage_ms=[PSCustomObject]$stageMilliseconds;wait_budget_ms=[PSCustomObject]$waitBudgets
        process_started=$started;input_closed=$inputClosed;process_exited=$exited;exit_code=$exitCode
        input_state=(Get-QbrainTaskState $writing);stdout_state=(Get-QbrainTaskState $stdout)
        stderr_state=(Get-QbrainTaskState $stderr);observation='before_cleanup';host_consumption_verified=$false
    }
}
try {
    if (-not $process.Start()) { throw 'Could not start Qbrain.' }
    $started=$true
    $stageMilliseconds.start=[long]$clock.ElapsedMilliseconds
    $phase='input'; $phaseStart=[long]$clock.ElapsedMilliseconds; $failureCode='transport_error'
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $writing = $process.StandardInput.BaseStream.WriteAsync($bytes, 0, $bytes.Length)
    $remaining=Get-QbrainRemainingMilliseconds $TimeoutMilliseconds $clock.ElapsedMilliseconds
    $waitBudgets.input=$remaining
    if (-not $writing.Wait($remaining)) { $failureCode='input_timeout'; throw 'Qbrain input timeout.' }
    $process.StandardInput.Close(); $inputClosed=$true
    $stageMilliseconds.input=[long]($clock.ElapsedMilliseconds-$phaseStart)
    $phase='process'; $phaseStart=[long]$clock.ElapsedMilliseconds
    $remaining=Get-QbrainRemainingMilliseconds $TimeoutMilliseconds $clock.ElapsedMilliseconds
    $waitBudgets.process=$remaining
    if (-not $process.WaitForExit($remaining)) { $failureCode='process_timeout'; throw 'Qbrain process timeout.' }
    $stageMilliseconds.process=[long]($clock.ElapsedMilliseconds-$phaseStart)
    $phase='output'; $phaseStart=[long]$clock.ElapsedMilliseconds
    $remaining=Get-QbrainRemainingMilliseconds $TimeoutMilliseconds $clock.ElapsedMilliseconds
    $waitBudgets.output=$remaining
    if (-not [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdout, $stderr), $remaining)) {
        $failureCode='output_timeout'; throw 'Qbrain output timeout.'
    }
    $result=[PSCustomObject]@{
        ExitCode = $process.ExitCode
        Stdout = $stdout.GetAwaiter().GetResult()
        Stderr = $stderr.GetAwaiter().GetResult()
    }
    $stageMilliseconds.output=[long]($clock.ElapsedMilliseconds-$phaseStart)
    $phase='complete'
    if($IncludeDiagnostics){
        $result | Add-Member -MemberType NoteProperty -Name Transport -Value (Get-QbrainTransportDiagnostic 'completed')
    }
    $result
} catch {
    if($stageMilliseconds.Contains($phase)){$stageMilliseconds[$phase]=[long]($clock.ElapsedMilliseconds-$phaseStart)}
    # Preserve legacy timeout text, normalize other process/stream exceptions.
    # Do not chain the original exception: native messages can contain paths.
    $messages=@{start_failed='Could not start Qbrain.';input_timeout='Qbrain input timeout.';
        process_timeout='Qbrain process timeout.';output_timeout='Qbrain output timeout.';
        transport_error='Qbrain transport failure.'}
    $failure=New-Object System.InvalidOperationException -ArgumentList $messages[$failureCode]
    $failure.Data['QbrainTransport']=(ConvertTo-Json -InputObject (Get-QbrainTransportDiagnostic $failureCode) -Depth 4 -Compress)
    throw $failure
} finally {
    $clock.Stop()
    try { if (-not $process.HasExited) { $process.Kill(); [void]$process.WaitForExit(2000) } } catch {}
    $process.Dispose()
}
