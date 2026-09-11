# Actual native installation/rollback tests. Python is CI-only for TOML validation.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Binary)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$installer=Join-Path $PSScriptRoot '..\scripts\Install-QbrainMemory.ps1'
$bridge=Join-Path $PSScriptRoot '..\scripts\Invoke-QbrainJson.ps1'
$original=(Resolve-Path -LiteralPath $Binary).ProviderPath
$utf8=New-Object Text.UTF8Encoding($false,$true)
$unicode=[string][char]0x4E2D+[char]0x6587+' '+[char]::ConvertFromUtf32(0x1F600)+" ' project"
$top=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-install-'+[Guid]::NewGuid().ToString('N'))
$root=Join-Path $top $unicode
[void][IO.Directory]::CreateDirectory($root)
$binaryPath=Join-Path $root 'qbrain.exe';[IO.File]::Copy($original,$binaryPath)
$envSaved=@{}
Get-ChildItem Env: | Where-Object {$_.Name -match '^(QBRAIN|OPENAI|ANTHROPIC)' -or $_.Name -in @('HOME','LOCALAPPDATA','USERPROFILE')} | ForEach-Object {
    $envSaved[$_.Name]=$_.Value;[Environment]::SetEnvironmentVariable($_.Name,$null,'Process')
}
$env:HOME=$root;$env:LOCALAPPDATA=$root;$env:USERPROFILE=$root
$script:checks=0
function Check([bool]$Value,[string]$Label){if(-not $Value){throw $Label};$script:checks++;Write-Host "PASS $script:checks : $Label"}
function Write-Json([string]$Path,$Value){[IO.File]::WriteAllText($Path,(ConvertTo-Json -InputObject $Value -Depth 64 -Compress),$utf8)}
function Read-Json([string]$Path){return [IO.File]::ReadAllText($Path,$utf8) | ConvertFrom-Json}
function Has($Map,[string]$Key){return $null -ne $Map.PSObject.Properties[$Key]}
function Set-Key($Map,[string]$Key,$Value){$Map | Add-Member -NotePropertyName $Key -NotePropertyValue $Value -Force}
function Qb([string[]]$Arguments,[string]$Data=''){
    $r=& $bridge -FilePath $binaryPath -ArgumentList $Arguments -InputJson $Data
    if($r.ExitCode -ne 0){throw ($r.Stdout+$r.Stderr)};return $r.Stdout
}
function Rejected([scriptblock]$Call,[string]$Label){$bad=$false;try{$null=& $Call}catch{$bad=$true};Check $bad $Label}
function Hook($Owner,[string]$Event,[string]$Session,[string]$Prompt='') {
    $entry=@($Owner.entries | Where-Object {$_.event -eq $Event})[0].group.hooks[0]
    $payload=@{hook_event_name=$Event;session_id=$Session;turn_id='turn-1';cwd=$Owner.project_root;prompt=$Prompt;last_assistant_message='Assistant-only statement.'}
    $inputJson=ConvertTo-Json -InputObject $payload -Depth 6 -Compress
    if($Owner.host -eq 'claude'){
        $r=& $bridge -FilePath $entry.command -ArgumentList @($entry.args) -InputJson $inputJson
    } else {
        Check ($entry.command -ceq $entry.commandWindows) 'Codex uses the same explicit Windows fallback'
        Check ($entry.commandWindows -match '^powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand ([A-Za-z0-9+/=]+)$') 'Codex command consists only of the static encoded bridge'
        $exe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $r=& $bridge -FilePath $exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',$Matches[1]) -InputJson $inputJson
    }
    Check ($r.ExitCode -eq 0) 'installed hook process exits without blocking host'
    return $r.Stdout | ConvertFrom-Json
}
$starting=Get-Location
try {
    # Preserve a global brain selection to prove project installation never retargets it.
    $null=Qb @('init','--brain','original-default')
    $globalPath=Join-Path $root 'Qbrain\config.json'
    $globalBefore=[IO.File]::ReadAllText($globalPath,$utf8)
    foreach($hostName in @('Claude','Codex')) {
        $project=Join-Path $root ($hostName+' workspace');[void][IO.Directory]::CreateDirectory($project)
        Set-Location -LiteralPath $project
        $target=if($hostName -eq 'Claude'){Join-Path $project '.claude\settings.local.json'}else{Join-Path $project '.codex\hooks.json'}
        [void][IO.Directory]::CreateDirectory((Split-Path -Parent $target))
        $unrelated=[pscustomobject]@{hooks=@([pscustomobject]@{type='command';command='unrelated-existing-tool';timeout=2})}
        $before=[pscustomobject]@{custom_setting='preserve-me';hooks=[pscustomobject]@{SessionStart=@($unrelated)}}
        Write-Json $target $before
        $mcpPath=if($hostName -eq 'Claude'){Join-Path $project '.mcp.json'}else{Join-Path $project '.codex\config.toml'}
        if($hostName -eq 'Claude'){
            Write-Json $mcpPath ([pscustomobject]@{custom=12;mcpServers=[pscustomobject]@{existing=[pscustomobject]@{command='existing';args=@('literal')}}})
            $mcpBefore=[IO.File]::ReadAllText($mcpPath,$utf8)
        }else{
            $mcpBefore="# existing comment`nmodel = 'existing-model'`n[mcp_servers.existing]`ncommand = 'existing'`n"
            [IO.File]::WriteAllText($mcpPath,$mcpBefore,$utf8)
        }
        $brainId=('install-'+$hostName.ToLowerInvariant())
        $null=& $installer -Action Install -HostName $hostName -ProjectPath $project -Binary $binaryPath -BrainId $brainId -EnableCapture
        $status=(& $installer -Action Status -HostName $hostName -ProjectPath $project) | ConvertFrom-Json
        Check ($status.installed -and $status.configuration_matches -and -not $status.host_consumption_confirmed) 'status distinguishes installed definitions from host consumption'
        Check (-not $status.recovery_required) 'successful install leaves no pending file transaction'
        Check ($globalBefore -ceq [IO.File]::ReadAllText($globalPath,$utf8)) 'project init does not change the global default brain'
        $roots=Get-ChildItem -LiteralPath (Join-Path $root 'Qbrain\integrations') -Directory
        $ownedRoot=$null;$owner=$null
        foreach($candidate in $roots){$p=Join-Path $candidate.FullName 'installation.json';if([IO.File]::Exists($p)){$m=Read-Json $p;if($m.project_root -ceq $project){$ownedRoot=$candidate.FullName;$owner=$m;break}}}
        Check ($null -ne $owner -and $owner.entries.Count -eq 5) 'five managed event definitions recorded'
        Check ($owner.mcp.name.StartsWith('qbrain_memory_')) 'compact MCP companion is installed'
        $installed=Read-Json $target
        Check ($installed.custom_setting -eq 'preserve-me' -and $installed.hooks.SessionStart.Count -eq 2) 'existing settings and hook survive install'
        if($hostName -eq 'Claude') {
            $mcp=Read-Json $mcpPath
            Check ($mcp.custom -eq 12 -and (Has $mcp.mcpServers 'existing')) 'existing MCP servers survive install'
            Check ($mcp.mcpServers.($owner.mcp.name).args -contains 'memory') 'MCP uses the compact memory profile'
            Check ($mcp.mcpServers.($owner.mcp.name).args -notcontains '--allow-write') 'MCP writes remain disabled by default'
        } else {
            $code=Join-Path $root 'check_toml.py'
            [IO.File]::WriteAllText($code,"import sys,tomllib`np=tomllib.load(open(sys.argv[1],'rb'))`nassert p['model']=='existing-model'`nassert p['mcp_servers']['existing']['command']=='existing'`nassert p['mcp_servers'][sys.argv[2]]['args']==['serve','--brain',sys.argv[3],'--tool-profile','memory']`n",$utf8)
            & python $code $mcpPath $owner.mcp.name $brainId
            Check ($LASTEXITCODE -eq 0) 'generated Codex TOML parses and preserves existing configuration'
            Check ([IO.File]::ReadAllText($mcpPath,$utf8).StartsWith($mcpBefore)) 'existing TOML bytes are unchanged'
        }
        $null=& $installer -Action Install -HostName $hostName -ProjectPath $project -Binary $binaryPath -BrainId $brainId -EnableCapture
        $owner=Read-Json (Join-Path $ownedRoot 'installation.json')
        Check ((Read-Json $target).hooks.SessionStart.Count -eq 2) 'reinstallation does not duplicate managed hooks'
        $quote='I prefer persistent '+$unicode+' deployment without Docker Hub.'
        $null=Hook $owner 'UserPromptSubmit' 'session-one' $quote
        $null=Hook $owner 'Stop' 'session-one'
        $restored=Hook $owner 'SessionStart' 'session-two'
        $additional=[string]$restored.hookSpecificOutput.additionalContext
        $restoredItems=$additional.Substring($additional.IndexOf("`n")+1) | ConvertFrom-Json
        Check (@($restoredItems | Where-Object {$_.quote -ceq $quote}).Count -eq 1) 'new installed hook process restores earlier user preference'
        $trace=Read-Json (Join-Path $ownedRoot 'last-trace.json')
        Check ($trace.recall_count -ge 1 -and $trace.provider_calls -eq 0 -and -not $trace.host_consumption_confirmed) 'trace records emission without claiming model consumption'
        Check (([IO.File]::ReadAllText((Join-Path $ownedRoot 'last-trace.json'),$utf8)).IndexOf($quote) -lt 0) 'trace does not copy conversation text'
        # Unrelated edits remain allowed and must be preserved by uninstall.
        $edited=Read-Json $target;Set-Key $edited 'new_unrelated_setting' 47;Write-Json $target $edited
        $validRaw=[IO.File]::ReadAllText($target,$utf8)
        $ownedEntry=$owner.entries[0]
        $bad=Read-Json $target
        $bad.hooks.SessionStart[1].hooks[0].timeout=99;Write-Json $target $bad
        $badRaw=[IO.File]::ReadAllText($target,$utf8)
        Rejected {& $installer -Action Uninstall -HostName $hostName -ProjectPath $project} 'uninstall refuses an externally edited owned hook'
        Check ([IO.File]::ReadAllText($target,$utf8) -ceq $badRaw) 'refused uninstall does not overwrite edited configuration'
        [IO.File]::WriteAllText($target,$validRaw,$utf8)
        # Simulate interrupted two-phase file installation, not a hidden test bypass.
        $partial=Read-Json $target;Set-Key $partial 'partial_install_marker' $true
        $partialRaw=ConvertTo-Json -InputObject $partial -Depth 64 -Compress
        $journal=Join-Path $ownedRoot 'pending.json'
        Write-Json $journal ([pscustomobject]@{version=1;changes=@([pscustomobject]@{path=$target;before=$validRaw;after=$partialRaw})})
        [IO.File]::WriteAllText($target,$partialRaw,$utf8)
        $pending=(& $installer -Action Status -HostName $hostName -ProjectPath $project) | ConvertFrom-Json
        Check $pending.recovery_required 'status reports an interrupted configuration transaction'
        $null=& $installer -Action Install -HostName $hostName -ProjectPath $project -Binary $binaryPath -BrainId $brainId -EnableCapture
        Check (-not (Has (Read-Json $target) 'partial_install_marker')) 'next install rolls back only recorded partial images'
        Check (-not [IO.File]::Exists($journal)) 'successful recovery retires journal'
        $validRaw=[IO.File]::ReadAllText($target,$utf8)
        Write-Json $journal ([pscustomobject]@{version=1;changes=@([pscustomobject]@{path=$target;before=$validRaw;after=$partialRaw})})
        [IO.File]::WriteAllText($target,($validRaw+" `n"),$utf8)
        Rejected {& $installer -Action Uninstall -HostName $hostName -ProjectPath $project} 'recovery refuses a third-party change outside recorded images'
        Check ([IO.File]::ReadAllText($target,$utf8) -ceq ($validRaw+" `n")) 'ambiguous recovery leaves all current bytes untouched'
        [IO.File]::Delete($journal);[IO.File]::WriteAllText($target,$validRaw,$utf8)
        $null=& $installer -Action Uninstall -HostName $hostName -ProjectPath $project
        $after=Read-Json $target
        Check ($after.hooks.SessionStart.Count -eq 1 -and $after.hooks.SessionStart[0].hooks[0].command -eq 'unrelated-existing-tool') 'uninstall removes only this installation hook'
        Check ($after.new_unrelated_setting -eq 47) 'uninstall retains unrelated edits made after install'
        if($hostName -eq 'Claude'){
            $mcp=Read-Json $mcpPath;Check (@($mcp.mcpServers.PSObject.Properties).Count -eq 1 -and (Has $mcp.mcpServers 'existing')) 'uninstall preserves other MCP servers'
        }else{Check ([IO.File]::ReadAllText($mcpPath,$utf8) -ceq $mcpBefore) 'uninstall restores unmanaged TOML bytes exactly'}
        Check (-not (Read-Json (Join-Path $ownedRoot 'config.json')).enabled) 'uninstall disables runtime configuration'
        $mem=(Qb @('memory','read','--brain',$brainId)) | ConvertFrom-Json
        Check ($mem.items.Count -ge 1) 'uninstall never deletes user memories'
        Check (@(Get-ChildItem -LiteralPath $ownedRoot -Filter 'settings-backup-*').Count -ge 1) 'settings backups remain available'
        $absent=(& $installer -Action Status -HostName $hostName -ProjectPath $project) | ConvertFrom-Json
        Check (-not $absent.installed) 'uninstall is reflected by status'
        $null=& $installer -Action Uninstall -HostName $hostName -ProjectPath $project
        Check ([IO.File]::ReadAllText($globalPath,$utf8) -ceq $globalBefore) 'repeat uninstall does not change default brain'
    }
    $invalidProject=Join-Path $root 'invalid-settings';[void][IO.Directory]::CreateDirectory((Join-Path $invalidProject '.claude'))
    $badTarget=Join-Path $invalidProject '.claude\settings.local.json';[IO.File]::WriteAllText($badTarget,'{"broken":',$utf8)
    Rejected {& $installer -HostName Claude -ProjectPath $invalidProject -Binary $binaryPath} 'invalid existing settings rejected'
    Check ([IO.File]::ReadAllText($badTarget,$utf8) -ceq '{"broken":') 'invalid settings are not replaced by defaults'
    Write-Host "Native installer: $script:checks checks passed under PowerShell $($PSVersionTable.PSVersion). Host consumption not tested."
} finally {
    Set-Location $starting
    foreach($name in @('HOME','LOCALAPPDATA','USERPROFILE')){[Environment]::SetEnvironmentVariable($name,$null,'Process')}
    foreach($name in $envSaved.Keys){[Environment]::SetEnvironmentVariable($name,$envSaved[$name],'Process')}
    Remove-Item -LiteralPath $top -Recurse -Force
}
