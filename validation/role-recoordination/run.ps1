$ErrorActionPreference = "Stop"

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

Set-Location $Repo

$ExpectedBranch = "feat/role-recoordination"
$ExpectedBase = "fa375b38b75bd91101d8b4594da3beed08fe6694"

$ExpectedCore =
    "B24845F8E8480CEAB40791F1ED5C3CA379F181D8C39CA4D981BA6850643D25A3"

$Core = Join-Path $Repo "nexus_distributed_core.py"
$HubScript = Join-Path $Repo "nexus_rendezvous.py"

$EvidenceRoot =
    Join-Path $Repo "validation\role-recoordination\evidence"

$RunId =
    (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

$Evidence =
    Join-Path $EvidenceRoot $RunId

$ProductExecutionStarted = $false
$Result = "ABORTED"
$Reason = "precondition"

$HubProcess = $null
$AProcess = $null
$ZProcess = $null

$OldHub = $env:NEXUS_HUB_URL
$OldSecret = $env:NEXUS_SECRET_KEY
$OldDb = $env:NEXUS_DB_PATH
$OldUtf8 = $env:PYTHONUTF8
$OldIo = $env:PYTHONIOENCODING

function UtcNow {
    return (Get-Date).ToUniversalTime().ToString("o")
}

function Append-Timeline([string]$Text) {
    Add-Content `
        -Path (Join-Path $Evidence "timeline.txt") `
        -Encoding UTF8 `
        -Value "$(UtcNow) | $Text"
}

function Get-Peers {
    $Response =
        Invoke-RestMethod `
            -Uri "http://127.0.0.1:8500/peers" `
            -Method Get `
            -TimeoutSec 2

    return $Response
}

function Save-Json(
    [object]$Value,
    [string]$Path
) {
    $Value |
        ConvertTo-Json -Depth 20 |
        Set-Content -Path $Path -Encoding UTF8
}

function Get-Role(
    [object]$Peers,
    [string]$Node
) {
    $Property =
        $Peers.PSObject.Properties[$Node]

    if ($null -eq $Property) {
        return $null
    }

    return [string]$Property.Value.role
}

function Is-Alive($Process) {
    if ($null -eq $Process) {
        return $false
    }

    try {
        return -not $Process.HasExited
    } catch {
        return $false
    }
}

function Require-Processes {
    if (-not (Is-Alive $HubProcess)) {
        throw "Hub exited unexpectedly"
    }

    if (-not (Is-Alive $AProcess)) {
        throw "Node A exited unexpectedly"
    }

    if (-not (Is-Alive $ZProcess)) {
        throw "Node Z exited unexpectedly"
    }
}

New-Item `
    -ItemType Directory `
    -Force `
    -Path $Evidence |
    Out-Null

"" |
    Set-Content `
        -Path (Join-Path $Evidence "timeline.txt") `
        -Encoding UTF8

try {

    # --------------------------------------------------------
    # PRECONDITIONS
    # --------------------------------------------------------

    Append-Timeline "PRECONDITION START"

    if ((git branch --show-current) -ne $ExpectedBranch) {
        throw "unexpected branch"
    }

    if ((git rev-parse HEAD) -ne $ExpectedBase) {
        throw "unexpected baseline"
    }

    $CoreHash =
        (Get-FileHash $Core -Algorithm SHA256).Hash

    if ($CoreHash -ne $ExpectedCore) {
        throw "unexpected core SHA256"
    }

    $Status =
        @(git status --porcelain)

    # Four development files plus protocol + runner directory state.
    # We intentionally do not prescribe raw line count here because
    # the untracked validation directory may collapse to one status
    # entry. Candidate identity is protected by core hash + baseline.
    if ($Status.Count -lt 5) {
        throw "unexpectedly small candidate working state"
    }

    foreach ($Port in @(8500,8081,8082,9091,9092)) {
        $Listener = @(
            Get-NetTCPConnection `
                -State Listen `
                -LocalPort $Port `
                -ErrorAction SilentlyContinue
        )

        if ($Listener.Count -ne 0) {
            throw "port $Port already in use"
        }
    }

    $Related =
        @(
            Get-CimInstance Win32_Process |
            Where-Object {
                $_.ProcessId -ne $PID -and
                $_.CommandLine -match
                    'nexus_distributed_core|nexus_rendezvous'
            }
        )

    if ($Related.Count -ne 0) {
        throw "related Nexus runtime process already active"
    }

    @(
        "utc=$(UtcNow)"
        "branch=$(git branch --show-current)"
        "baseline=$(git rev-parse HEAD)"
        "core_sha256=$CoreHash"
        "python=$(python --version 2>&1)"
        "powershell=$($PSVersionTable.PSVersion)"
    ) |
        Set-Content `
            -Path (Join-Path $Evidence "environment.txt") `
            -Encoding UTF8

    @(
        "expected_winner=NO-9L-Z"
        "expected_loser=NO-9L-A"
        "rule=lexicographically greatest stable node_id retains MASTER"
        "core_sha256=$CoreHash"
    ) |
        Set-Content `
            -Path (Join-Path $Evidence "candidate.txt") `
            -Encoding UTF8

    Append-Timeline "PRECONDITION PASS"

    # --------------------------------------------------------
    # PROCESS ENVIRONMENT
    # --------------------------------------------------------

    $env:NEXUS_HUB_URL = "http://127.0.0.1:8500"
    $env:NEXUS_SECRET_KEY = "nexus-role-recoordination-validation"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"

    $EmptyA = Join-Path $Evidence "A.stdin.txt"
    $EmptyZ = Join-Path $Evidence "Z.stdin.txt"

    [System.IO.File]::WriteAllText($EmptyA, "")
    [System.IO.File]::WriteAllText($EmptyZ, "")

    # --------------------------------------------------------
    # START HUB
    # --------------------------------------------------------

    $ProductExecutionStarted = $true
    $Result = "FAIL"
    $Reason = "product execution incomplete"

    Append-Timeline "PRODUCT EXECUTION START"

    $HubOut = Join-Path $Evidence "hub.stdout.txt"
    $HubErr = Join-Path $Evidence "hub.stderr.txt"

    $HubProcess =
        Start-Process `
            -FilePath "python" `
            -ArgumentList @($HubScript) `
            -RedirectStandardOutput $HubOut `
            -RedirectStandardError $HubErr `
            -PassThru `
            -WindowStyle Hidden

    Append-Timeline "HUB START pid=$($HubProcess.Id)"

    $HubDeadline = (Get-Date).AddSeconds(10)

    do {
        if (-not (Is-Alive $HubProcess)) {
            throw "Hub exited during startup"
        }

        try {
            $null = Get-Peers
            $HubReady = $true
        } catch {
            $HubReady = $false
        }

        if (-not $HubReady) {
            Start-Sleep -Milliseconds 250
        }

    } until (
        $HubReady -or
        (Get-Date) -ge $HubDeadline
    )

    if (-not $HubReady) {
        throw "Hub startup timeout"
    }

    Append-Timeline "HUB READY"

    # --------------------------------------------------------
    # START BOTH AS MASTER
    # --------------------------------------------------------

    $AOut = Join-Path $Evidence "A.stdout.txt"
    $AErr = Join-Path $Evidence "A.stderr.txt"

    $ZOut = Join-Path $Evidence "Z.stdout.txt"
    $ZErr = Join-Path $Evidence "Z.stderr.txt"

    $env:NEXUS_DB_PATH =
        (Join-Path $Evidence "A.db")

    $AProcess =
        Start-Process `
            -FilePath "python" `
            -ArgumentList @(
                $Core,
                "NO-9L-A",
                "8081",
                "9091",
                "MASTER"
            ) `
            -RedirectStandardInput $EmptyA `
            -RedirectStandardOutput $AOut `
            -RedirectStandardError $AErr `
            -PassThru `
            -WindowStyle Hidden

    Append-Timeline "NODE A START MASTER pid=$($AProcess.Id)"

    $env:NEXUS_DB_PATH =
        (Join-Path $Evidence "Z.db")

    $ZProcess =
        Start-Process `
            -FilePath "python" `
            -ArgumentList @(
                $Core,
                "NO-9L-Z",
                "8082",
                "9092",
                "MASTER"
            ) `
            -RedirectStandardInput $EmptyZ `
            -RedirectStandardOutput $ZOut `
            -RedirectStandardError $ZErr `
            -PassThru `
            -WindowStyle Hidden

    Append-Timeline "NODE Z START MASTER pid=$($ZProcess.Id)"

    # --------------------------------------------------------
    # OBSERVE REAL MASTER/MASTER CONFLICT
    # --------------------------------------------------------

    $ConflictDeadline =
        (Get-Date).AddSeconds(15)

    $ConflictObserved = $false
    $LastPeers = $null

    while ((Get-Date) -lt $ConflictDeadline) {

        Require-Processes

        try {
            $Peers = Get-Peers
            $LastPeers = $Peers

            $ARole = Get-Role $Peers "NO-9L-A"
            $ZRole = Get-Role $Peers "NO-9L-Z"

            if (
                $ARole -eq "MASTER" -and
                $ZRole -eq "MASTER"
            ) {
                $ConflictObserved = $true

                Save-Json `
                    $Peers `
                    (Join-Path $Evidence "peers.conflict.json")

                Append-Timeline "CONFLICT OBSERVED A=MASTER Z=MASTER"
                break
            }

        } catch {
            # Hub may be between registration updates.
        }

        Start-Sleep -Milliseconds 100
    }

    if (-not $ConflictObserved) {

        if ($null -ne $LastPeers) {
            Save-Json `
                $LastPeers `
                (Join-Path $Evidence "peers.last-before-conflict-fail.json")
        }

        throw "simultaneous MASTER conflict not observed"
    }

    # --------------------------------------------------------
    # WAIT FOR DETERMINISTIC CONVERGENCE
    # --------------------------------------------------------

    $ConvergenceDeadline =
        (Get-Date).AddSeconds(30)

    $Converged = $false

    while ((Get-Date) -lt $ConvergenceDeadline) {

        Require-Processes

        $Peers = Get-Peers

        $ARole = Get-Role $Peers "NO-9L-A"
        $ZRole = Get-Role $Peers "NO-9L-Z"

        if (
            $ARole -eq "FOLLOWER" -and
            $ZRole -eq "MASTER"
        ) {
            $Converged = $true

            Save-Json `
                $Peers `
                (Join-Path $Evidence "peers.converged.json")

            Append-Timeline "CONVERGENCE PASS A=FOLLOWER Z=MASTER"
            break
        }

        Start-Sleep -Milliseconds 250
    }

    if (-not $Converged) {
        throw "deterministic convergence timeout"
    }

    # --------------------------------------------------------
    # STABILITY â€” THREE SNAPSHOTS
    # --------------------------------------------------------

    for ($i = 1; $i -le 3; $i++) {

        Start-Sleep -Seconds 5

        Require-Processes

        $Peers = Get-Peers

        $ARole = Get-Role $Peers "NO-9L-A"
        $ZRole = Get-Role $Peers "NO-9L-Z"

        Save-Json `
            $Peers `
            (Join-Path $Evidence "peers.stability.$i.json")

        Append-Timeline (
            "STABILITY $i A=$ARole Z=$ZRole"
        )

        if ($ARole -ne "FOLLOWER") {
            throw "A role instability at snapshot $i"
        }

        if ($ZRole -ne "MASTER") {
            throw "Z role instability at snapshot $i"
        }
    }

    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    $Result = "PASS"
    $Reason =
        "real MASTER/MASTER conflict converged and remained stable"

    Append-Timeline "RESULT PASS"

} catch {

    $Reason = $_.Exception.Message

    if ($ProductExecutionStarted) {
        $Result = "FAIL"
    } else {
        $Result = "ABORTED"
    }

    try {
        Append-Timeline "RESULT $Result reason=$Reason"
    } catch {
    }

} finally {

    # --------------------------------------------------------
    # CLEANUP
    # --------------------------------------------------------

    foreach ($Process in @(
        $AProcess,
        $ZProcess,
        $HubProcess
    )) {
        if ($null -ne $Process) {
            try {
                if (-not $Process.HasExited) {
                    Stop-Process `
                        -Id $Process.Id `
                        -Force `
                        -ErrorAction SilentlyContinue
                }
            } catch {
            }
        }
    }

    # Explicitly wait for child termination before hashing
    # redirected stdout/stderr evidence.
    foreach ($Process in @(
        $AProcess,
        $ZProcess,
        $HubProcess
    )) {
        if ($null -ne $Process) {
            try {
                $Process.WaitForExit()
            } catch {
            }
        }
    }

    Start-Sleep -Milliseconds 250

    # Restore caller environment.
    if ($null -eq $OldHub) {
        Remove-Item Env:NEXUS_HUB_URL -ErrorAction SilentlyContinue
    } else {
        $env:NEXUS_HUB_URL = $OldHub
    }

    if ($null -eq $OldSecret) {
        Remove-Item Env:NEXUS_SECRET_KEY -ErrorAction SilentlyContinue
    } else {
        $env:NEXUS_SECRET_KEY = $OldSecret
    }

    if ($null -eq $OldDb) {
        Remove-Item Env:NEXUS_DB_PATH -ErrorAction SilentlyContinue
    } else {
        $env:NEXUS_DB_PATH = $OldDb
    }

    if ($null -eq $OldUtf8) {
        Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONUTF8 = $OldUtf8
    }

    if ($null -eq $OldIo) {
        Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONIOENCODING = $OldIo
    }

    try {
        @(
            "ROLE RECOORDINATION REAL-PROCESS RESULT: $Result"
            "reason=$Reason"
            "baseline=$ExpectedBase"
            "core_sha256=$ExpectedCore"
            "expected_A=FOLLOWER"
            "expected_Z=MASTER"
        ) |
            Set-Content `
                -Path (Join-Path $Evidence "result.txt") `
                -Encoding UTF8

        $Manifest =
            Get-ChildItem `
                -Path $Evidence `
                -File |
            Where-Object {
                $_.Name -ne "sha256.txt"
            } |
            Sort-Object Name |
            ForEach-Object {
                $Hash =
                    (Get-FileHash $_.FullName -Algorithm SHA256).Hash

                "$Hash  $($_.Name)"
            }

        $Manifest |
            Set-Content `
                -Path (Join-Path $Evidence "sha256.txt") `
                -Encoding UTF8

    } catch {
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host " ROLE RECOORDINATION REAL-PROCESS RESULT"
Write-Host "============================================================"
Write-Host "Result   : $Result"
Write-Host "Reason   : $Reason"
Write-Host "Evidence : $Evidence"
Write-Host "============================================================"

if ($Result -eq "PASS") {
    exit 0
}

if ($Result -eq "FAIL") {
    exit 1
}

exit 2
