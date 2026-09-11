# Windows PowerShell 5.1 and PowerShell 7: byte-preserving UTF-8 process bridge.
# No shell interpolation, profile loading, global encoding changes or WSL needed.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][AllowEmptyCollection()][AllowEmptyString()][string[]]$ArgumentList,
    [AllowEmptyString()][string]$InputJson = '',
    [ValidateRange(100,120000)][int]$TimeoutMilliseconds = 10000
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
$clock = [Diagnostics.Stopwatch]::StartNew()
try {
    if (-not $process.Start()) { throw 'Could not start Qbrain.' }
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $writing = $process.StandardInput.BaseStream.WriteAsync($bytes, 0, $bytes.Length)
    if (-not $writing.Wait($TimeoutMilliseconds)) { throw 'Qbrain input timeout.' }
    $process.StandardInput.Close()
    $remaining = [Math]::Max(0, $TimeoutMilliseconds - [int]$clock.ElapsedMilliseconds)
    if (-not $process.WaitForExit($remaining)) { throw 'Qbrain process timeout.' }
    $remaining = [Math]::Max(0, $TimeoutMilliseconds - [int]$clock.ElapsedMilliseconds)
    if (-not [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdout, $stderr), $remaining)) {
        throw 'Qbrain output timeout.'
    }
    [PSCustomObject]@{
        ExitCode = $process.ExitCode
        Stdout = $stdout.GetAwaiter().GetResult()
        Stderr = $stderr.GetAwaiter().GetResult()
    }
} finally {
    $clock.Stop()
    try { if (-not $process.HasExited) { $process.Kill(); [void]$process.WaitForExit(2000) } } catch {}
    $process.Dispose()
}
