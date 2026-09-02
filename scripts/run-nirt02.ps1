# NIRT-02 — Real Process Failover Runner

$ErrorActionPreference = "Stop"

$ProductCommit = "c8516db7b1fb694af647c80e1f1b9bc828a60d77"
$ProductTag    = "v2700.0.0-rc1"

$NodeA = "NO-NIRT02-A"
$NodeB = "NO-NIRT02-B"

$HubPort = 8500
$WebA    = 8081
$TcpA    = 9091
$WebB    = 8082
$TcpB    = 9092

$FailoverTimeoutSeconds = 70

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$UtcStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

$EvidenceRoot = Join-Path $Root "nirt\evidence\nirt02"
$EvidenceDir  = Join-Path $EvidenceRoot $UtcStamp

$ProductWorktree = Join-Path `
    ([System.IO.Path]::GetTempPath()) `
    ("nexus-nirt02-product-" + $UtcStamp)

$LogFile        = Join-Path $EvidenceDir "nirt02.log"
$ResultFile     = Join-Path $EvidenceDir "result.txt"
$EnvironmentFile = Join-Path $EvidenceDir "environment.txt"
$InstrumentFile = Join-Path $EvidenceDir "instrument.txt"

$HubStdout = Join-Path $EvidenceDir "hub.stdout.log"
$HubStderr = Join-Path $EvidenceDir "hub.stderr.log"
$AStdout   = Join-Path $EvidenceDir "node-a.stdout.log"
$AStderr   = Join-Path $EvidenceDir "node-a.stderr.log"
$BStdout   = Join-Path $EvidenceDir "node-b.stdout.log"
$BStderr   = Join-Path $EvidenceDir "node-b.stderr.log"

$DbA = Join-Path $EvidenceDir "node-a.db"
$DbB = Join-Path $EvidenceDir "node-b.db"

$AStdin = Join-Path $EvidenceDir "node-a.stdin.txt"
$BStdin = Join-Path $EvidenceDir "node-b.stdin.txt"

$Secret     = "NIRT02_SECRET_$UtcStamp"

$Processes = @()
$ProductExecutionStarted = $false
$FailureEventStarted     = $false
$WorktreeCreated         = $false

$Script:NirtExitCode = 2
$InstrumentationCommit = "UNRESOLVED"

function Log {
    param([string]$Message)

    $Line = "{0} {1}" -f `
        (Get-Date).ToUniversalTime().ToString("o"),
        $Message

    $Line | Tee-Object -FilePath $LogFile -Append
}

function Save-Json {
    param(
        [string]$Name,
        $Object
    )

    $Path = Join-Path $EvidenceDir $Name

    $Object |
        ConvertTo-Json -Depth 20 |
        Set-Content -Path $Path -Encoding UTF8
}

function Get-Json {
    param([string]$Uri)

    return Invoke-RestMethod `
        -Uri $Uri `
        -Method Get `
        -TimeoutSec 5
}

function Wait-Status {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 30
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $Deadline) {
        try {
            return Get-Json "http://127.0.0.1:$Port/status"
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    throw "TIMEOUT aguardando /status na porta $Port"
}

function Wait-Peers {
    param(
        [int]$Minimum,
        [int]$TimeoutSeconds = 60
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $Deadline) {
        try {
            $Peers = Get-Json "http://127.0.0.1:$HubPort/peers"

            $Count = @(
                $Peers.PSObject.Properties
            ).Count

            if ($Count -ge $Minimum) {
                return $Peers
            }
        }
        catch {
        }

        Start-Sleep -Seconds 1
    }

    throw "TIMEOUT aguardando $Minimum peers"
}

function Wait-Role {
    param(
        [int]$Port,
        [string]$Role,
        [int]$TimeoutSeconds
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $Deadline) {
        try {
            $Status = Get-Json "http://127.0.0.1:$Port/status"

            if ($Status.role -eq $Role) {
                return $Status
            }
        }
        catch {
        }

        Start-Sleep -Seconds 1
    }

    throw "TIMEOUT aguardando role=$Role na porta $Port"
}

function Stop-NirtProcess {
    param($Process)

    if ($null -eq $Process) {
        return
    }

    try {
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force
            $Process.WaitForExit()
        }
    }
    catch {
    }
}

function Assert-Liveness {
    param(
        [int]$Port,
        [string]$ExpectedNode
    )

    $Value = Get-Json "http://127.0.0.1:$Port/liveness"

    if ($Value.alive -ne $true) {
        throw "LIVENESS FAIL: $ExpectedNode alive != true"
    }

    if ($Value.node_id -ne $ExpectedNode) {
        throw "LIVENESS IDENTITY FAIL: esperado=$ExpectedNode obtido=$($Value.node_id)"
    }

    return $Value
}

function Assert-Health {
    param(
        [int]$Port,
        [string]$ExpectedNode
    )

    $Value = Get-Json "http://127.0.0.1:$Port/health"

    if ($Value.healthy -ne $true) {
        throw "HEALTH FAIL: $ExpectedNode healthy != true"
    }

    if ($Value.node_id -ne $ExpectedNode) {
        throw "HEALTH IDENTITY FAIL: esperado=$ExpectedNode obtido=$($Value.node_id)"
    }

    if ($Value.storage.valid -ne $true) {
        throw "STORAGE FAIL: $ExpectedNode storage.valid != true"
    }

    return $Value
}

function Assert-Readiness {
    param(
        [int]$Port,
        [string]$ExpectedNode
    )

    $Value = Get-Json "http://127.0.0.1:$Port/readiness"

    if ($Value.ready -ne $true) {
        throw "READINESS FAIL: $ExpectedNode ready != true"
    }

    if ($Value.node_id -and $Value.node_id -ne $ExpectedNode) {
        throw "READINESS IDENTITY FAIL: esperado=$ExpectedNode obtido=$($Value.node_id)"
    }

    return $Value
}

New-Item `
    -ItemType Directory `
    -Force `
    -Path $EvidenceDir |
    Out-Null

try {
    Log "NIRT-02 START"

    # --------------------------------------------------------
    # Instrument identity
    # --------------------------------------------------------

    Push-Location $Root

    try {
        $InstrumentationCommit = git rev-parse HEAD
        $Branch = git branch --show-current
        $ProductResolved = git rev-parse "$ProductTag^{commit}"

        if ($ProductResolved -ne $ProductCommit) {
            throw "ABORTED: product tag nao resolve para commit esperado"
        }

        $InstrumentationGitStatus =
            @(git status --porcelain)

        if ($InstrumentationGitStatus.Count -ne 0) {
            throw "ABORTED: instrumentation repository is not clean"
        }

        @(
            "NIRT-02"
            "UTC=$((Get-Date).ToUniversalTime().ToString('o'))"
            "INSTRUMENT_COMMIT=$InstrumentationCommit"
            "INSTRUMENT_BRANCH=$Branch"
            "INSTRUMENT_GIT_STATUS=CLEAN"
            "PRODUCT_TAG=$ProductTag"
            "PRODUCT_COMMIT=$ProductCommit"
        ) | Set-Content $InstrumentFile -Encoding UTF8
    }
    finally {
        Pop-Location
    }

    # --------------------------------------------------------
    # Environment
    # --------------------------------------------------------

    $NexusCli = "UNAVAILABLE"

    try {
        $NexusCli = (nexus version 2>&1 | Out-String).Trim()
    }
    catch {
    }

    @(
        "NIRT-02"
        "UTC=$((Get-Date).ToUniversalTime().ToString('o'))"
        "PRODUCT_COMMIT=$ProductCommit"
        "OS=$([System.Environment]::OSVersion.VersionString)"
        "POWERSHELL=$($PSVersionTable.PSVersion)"
        "PYTHON=$(python --version 2>&1)"
        "GIT=$(git --version)"
        "NEXUS_CLI=$NexusCli"
        "NODE_A=$NodeA"
        "NODE_B=$NodeB"
        "HUB_PORT=$HubPort"
        "WEB_A=$WebA"
        "TCP_A=$TcpA"
        "WEB_B=$WebB"
        "TCP_B=$TcpB"
        "FAILOVER_TIMEOUT_SECONDS=$FailoverTimeoutSeconds"
    ) | Set-Content $EnvironmentFile -Encoding UTF8

    # --------------------------------------------------------
    # Environmental prerequisites
    # --------------------------------------------------------

    Log "ENVIRONMENT PREFLIGHT"

    foreach ($Command in @("git","python","nexus")) {
        if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
            throw "ABORTED: required command unavailable: $Command"
        }
    }

    foreach ($Port in @(
        $HubPort,
        $WebA,
        $TcpA,
        $WebB,
        $TcpB
    )) {
        $Listener = Get-NetTCPConnection `
            -State Listen `
            -LocalPort $Port `
            -ErrorAction SilentlyContinue

        if ($Listener) {
            throw "ABORTED: required port already occupied: $Port"
        }
    }

    # Node A receives exactly one predefined payload through
    # the frozen product MASTER shell intake path.
    #
    # Node B receives EOF if/when it becomes MASTER, preventing
    # any post-promotion operator-generated transaction.
    [System.IO.File]::WriteAllText(
        $AStdin,
        ""
    )

    [System.IO.File]::WriteAllText(
        $BStdin,
        ""
    )

    # --------------------------------------------------------
    # Frozen product worktree
    # --------------------------------------------------------

    Log "CREATE FROZEN PRODUCT WORKTREE"

    git -C $Root worktree add `
        --detach `
        $ProductWorktree `
        $ProductCommit

    if ($LASTEXITCODE -ne 0) {
        throw "ABORTED: falha criando worktree congelado"
    }

    $WorktreeCreated = $true

    $FrozenHead = git -C $ProductWorktree rev-parse HEAD

    if ($FrozenHead -ne $ProductCommit) {
        throw "ABORTED: worktree nao esta no produto congelado"
    }

    # --------------------------------------------------------
    # Seed persistent non-genesis state in Node A
    # Protocol-defined exact transaction.
    # --------------------------------------------------------

    Log "SEED NODE A PERSISTENCE"

    $SeedCode = @"
import sys
sys.path.insert(0, sys.argv[1])
from persistence import NexusPersistence

db = sys.argv[2]
store = NexusPersistence(filepath=db)

store.append_transaction({
    "event": "NIRT02_SEED",
    "data": {
        "payload": "pre-failover-state"
    }
})

summary = store.state_summary()
print(summary["height"])
print(summary["tip_hash"])
"@

    # From this point frozen product code is being executed.
    # Any mandatory product-property failure is FAIL, not ABORTED.
    $ProductExecutionStarted = $true

    $SeedOutput = $SeedCode |
        & python `
            - `
            $ProductWorktree `
            $DbA

    if ($LASTEXITCODE -ne 0) {
        throw "SEED FAIL: falha criando estado inicial"
    }

    if (@($SeedOutput).Count -lt 2) {
        throw "SEED FAIL: state summary incompleto"
    }

    $SeedCreatedHeight = [int]$SeedOutput[0]
    $SeedCreatedTip    = [string]$SeedOutput[1]

    if ($SeedCreatedHeight -le 0) {
        throw "SEED FAIL: height inicial nao positivo"
    }

    if (
        [string]::IsNullOrWhiteSpace($SeedCreatedTip) -or
        $SeedCreatedTip -eq ("0" * 64)
    ) {
        throw "SEED FAIL: tip inicial invalido"
    }

    # --------------------------------------------------------
    # Environment inherited by real product processes
    # --------------------------------------------------------

    $OldSecret = $env:NEXUS_SECRET_KEY
    $OldHub    = $env:NEXUS_HUB_URL
    $OldDb     = $env:NEXUS_DB_PATH

    $env:NEXUS_SECRET_KEY = $Secret
    $env:NEXUS_HUB_URL    = "http://127.0.0.1:$HubPort"

    # --------------------------------------------------------
    # Start real Hub
    # --------------------------------------------------------

    Log "START HUB"

    $Hub = Start-Process `
        -FilePath "python" `
        -WorkingDirectory $ProductWorktree `
        -ArgumentList @("nexus_rendezvous.py") `
        -PassThru `
        -NoNewWindow `
        -RedirectStandardOutput $HubStdout `
        -RedirectStandardError $HubStderr

    $Processes += $Hub

    Start-Sleep -Seconds 1

    if ($Hub.HasExited) {
        throw "HUB FAIL: processo encerrou prematuramente"
    }

    # --------------------------------------------------------
    # Start Node A
    # --------------------------------------------------------

    Log "START NODE A role=MASTER"

    $env:NEXUS_DB_PATH = $DbA

    $A = Start-Process `
        -FilePath "python" `
        -WorkingDirectory $ProductWorktree `
        -ArgumentList @(
            "nexus_distributed_core.py",
            $NodeA,
            "$WebA",
            "$TcpA",
            "MASTER"
        ) `
        -PassThru `
        -NoNewWindow `
        -RedirectStandardInput $AStdin `
        -RedirectStandardOutput $AStdout `
        -RedirectStandardError $AStderr

    $Processes += $A

    $InitialA = Wait-Status -Port $WebA -TimeoutSeconds 30

    # --------------------------------------------------------
    # Start Node B
    # --------------------------------------------------------

    Log "START NODE B role=FOLLOWER"

    $env:NEXUS_DB_PATH = $DbB

    $B = Start-Process `
        -FilePath "python" `
        -WorkingDirectory $ProductWorktree `
        -ArgumentList @(
            "nexus_distributed_core.py",
            $NodeB,
            "$WebB",
            "$TcpB",
            "FOLLOWER"
        ) `
        -PassThru `
        -NoNewWindow `
        -RedirectStandardInput $BStdin `
        -RedirectStandardOutput $BStdout `
        -RedirectStandardError $BStderr

    $Processes += $B

    $InitialB = Wait-Status -Port $WebB -TimeoutSeconds 30

    # --------------------------------------------------------
    # Registration
    # --------------------------------------------------------

    $Peers = Wait-Peers -Minimum 2 -TimeoutSeconds 60
    Save-Json "registered-peers.json" $Peers

    # --------------------------------------------------------
    # Wait for real persistence convergence A -> B
    # --------------------------------------------------------

    Log "WAIT PERSISTENCE CONVERGENCE"

    $ConvergenceDeadline = (Get-Date).AddSeconds(60)
    $PreA = $null
    $PreB = $null

    while ((Get-Date) -lt $ConvergenceDeadline) {

        $CandidateA = Get-Json "http://127.0.0.1:$WebA/status"
        $CandidateB = Get-Json "http://127.0.0.1:$WebB/status"

        $HeightA = [int]$CandidateA.height
        $HeightB = [int]$CandidateB.height

        $TipA = [string]$CandidateA.tip_hash
        $TipB = [string]$CandidateB.tip_hash

        if (
            $HeightA -gt 0 -and
            $HeightA -eq $HeightB -and
            $TipA -eq $TipB -and
            $TipA -ne ("0" * 64)
        ) {
            $PreA = $CandidateA
            $PreB = $CandidateB
            break
        }

        Start-Sleep -Seconds 1
    }

    if ($null -eq $PreA -or $null -eq $PreB) {
        throw "PRECONDITION FAIL: persistence convergence A -> B nao observada"
    }

    if ($PreA.node_id -ne $NodeA) {
        throw "PRECONDITION FAIL: identidade de A incorreta"
    }

    if ($PreB.node_id -ne $NodeB) {
        throw "PRECONDITION FAIL: identidade de B incorreta"
    }

    if ($PreA.role -ne "MASTER") {
        throw "PRECONDITION FAIL: A nao e MASTER"
    }

    if ($PreB.role -ne "FOLLOWER") {
        throw "PRECONDITION FAIL: B nao e FOLLOWER"
    }

    Save-Json "pre-a-status.json" $PreA
    Save-Json "pre-b-status.json" $PreB

    $PrePeers = Get-Json "http://127.0.0.1:$HubPort/peers"
    Save-Json "pre-peers.json" $PrePeers
    $PreACluster =
        Get-Json "http://127.0.0.1:$WebA/cluster"

    $PreAMetrics =
        Get-Json "http://127.0.0.1:$WebA/metrics"

    $PreBCluster =
        Get-Json "http://127.0.0.1:$WebB/cluster"

    $PreBMetrics =
        Get-Json "http://127.0.0.1:$WebB/metrics"

    Save-Json "pre-a-cluster.json" $PreACluster
    Save-Json "pre-a-metrics.json" $PreAMetrics
    Save-Json "pre-b-cluster.json" $PreBCluster
    Save-Json "pre-b-metrics.json" $PreBMetrics

    if ($Hub.HasExited) {
        throw "PRECONDITION FAIL: Hub process is not alive"
    }

    if ($A.HasExited) {
        throw "PRECONDITION FAIL: Node A process is not alive"
    }

    if ($B.HasExited) {
        throw "PRECONDITION FAIL: Node B process is not alive"
    }

    $PreHubA = $PrePeers.PSObject.Properties[$NodeA]
    $PreHubB = $PrePeers.PSObject.Properties[$NodeB]

    if ($null -eq $PreHubA -or $PreHubA.Value.role -ne "MASTER") {
        throw "PRECONDITION FAIL: Hub does not report Node A as MASTER"
    }

    if ($null -eq $PreHubB -or $PreHubB.Value.role -ne "FOLLOWER") {
        throw "PRECONDITION FAIL: Hub does not report Node B as FOLLOWER"
    }

    $PreALive   = Assert-Liveness -Port $WebA -ExpectedNode $NodeA
    $PreAHealth = Assert-Health   -Port $WebA -ExpectedNode $NodeA
    $PreAReady  = Assert-Readiness -Port $WebA -ExpectedNode $NodeA

    $PreBLive   = Assert-Liveness -Port $WebB -ExpectedNode $NodeB
    $PreBHealth = Assert-Health   -Port $WebB -ExpectedNode $NodeB
    $PreBReady  = Assert-Readiness -Port $WebB -ExpectedNode $NodeB

    Save-Json "pre-a-liveness.json"  $PreALive
    Save-Json "pre-a-health.json"    $PreAHealth
    Save-Json "pre-a-readiness.json" $PreAReady

    Save-Json "pre-b-liveness.json"  $PreBLive
    Save-Json "pre-b-health.json"    $PreBHealth
    Save-Json "pre-b-readiness.json" $PreBReady

    $ExpectedHeight = [int]$PreA.height
    $ExpectedTip    = [string]$PreA.tip_hash

    if (
        $ExpectedHeight -ne $SeedCreatedHeight -or
        $ExpectedTip -ne $SeedCreatedTip
    ) {
        throw "PRECONDITION FAIL: converged state differs from predefined seed"
    }

    @(
        "NIRT=NIRT-02"
        "PRODUCT_TAG=$ProductTag"
        "PRODUCT_COMMIT=$ProductCommit"
        "NODE_A=$NodeA"
        "NODE_B=$NodeB"
        "HUB_PORT=$HubPort"
        "NODE_A_WEB=$WebA"
        "NODE_A_TCP=$TcpA"
        "NODE_B_WEB=$WebB"
        "NODE_B_TCP=$TcpB"
        "INITIAL_ROLE_A=MASTER"
        "INITIAL_ROLE_B=FOLLOWER"
        "FAILURE_EVENT=STOP_NODE_A_ONLY"
        "FAILOVER_TIMEOUT_SECONDS=$FailoverTimeoutSeconds"
        "EXPECTED_NEW_MASTER=$NodeB"
        "STATE_HEIGHT=$ExpectedHeight"
        "STATE_TIP=$ExpectedTip"
    ) |
        Set-Content `
            (Join-Path $EvidenceDir "contract.txt") `
            -Encoding UTF8

    @(
        "source=FROZEN_PRODUCT_PERSISTENCE_API"
        "event=NIRT02_SEED"
        "payload=pre-failover-state"
        "created_height=$SeedCreatedHeight"
        "created_tip_hash=$SeedCreatedTip"
        "expected_height=$ExpectedHeight"
        "expected_tip_hash=$ExpectedTip"
    ) |
        Set-Content `
            (Join-Path $EvidenceDir "seed.txt") `
            -Encoding UTF8

    Log "PRECONDITIONS PASS height=$ExpectedHeight tip_hash=$ExpectedTip"

    # --------------------------------------------------------
    # FAILURE EVENT
    # --------------------------------------------------------

    $FailureEventStarted = $true

    # The protocol-wide 70 second window begins immediately
    # before the injected failure action itself.
    $FailoverDeadline =
        (Get-Date).AddSeconds($FailoverTimeoutSeconds)

    Log "FAILURE EVENT: stopping MASTER $NodeA"

    Stop-NirtProcess $A

    if (-not $A.HasExited) {
        throw "FAILURE EVENT FAIL: Node A permaneceu ativo"
    }

    # --------------------------------------------------------
    # Automatic failover — protocol limit = 70 seconds
    # --------------------------------------------------------

    Log "WAIT AUTOMATIC FAILOVER"

    # One and only one protocol-wide observation window.
    # ALL mandatory post-failover observations must succeed
    # before this deadline.

    $PostB       = $null
    $PostPeers   = $null
    $PostBLive   = $null
    $PostBHealth = $null
    $PostBReady  = $null
    $PostBCluster = $null
    $PostBMetrics = $null

    while ((Get-Date) -lt $FailoverDeadline) {

        if ($B.HasExited) {
            throw "FAILOVER FAIL: Node B process terminated"
        }

        if ($Hub.HasExited) {
            throw "FAILOVER FAIL: Hub process terminated"
        }

        try {
            $CandidateStatus =
                Get-Json "http://127.0.0.1:$WebB/status"

            $CandidatePeers =
                Get-Json "http://127.0.0.1:$HubPort/peers"

            $CandidateLive =
                Get-Json "http://127.0.0.1:$WebB/liveness"

            $CandidateHealth =
                Get-Json "http://127.0.0.1:$WebB/health"

            $CandidateReady =
                Get-Json "http://127.0.0.1:$WebB/readiness"
            $CandidateCluster =
                Get-Json "http://127.0.0.1:$WebB/cluster"

            $CandidateMetrics =
                Get-Json "http://127.0.0.1:$WebB/metrics"

            $Properties =
                @($CandidatePeers.PSObject.Properties)

            $HasA = @(
                $Properties |
                    Where-Object { $_.Name -eq $NodeA }
            ).Count -gt 0

            $BPeer =
                $CandidatePeers.PSObject.Properties[$NodeB]

            $HubRoleB = $null

            if ($null -ne $BPeer) {
                $HubRoleB = $BPeer.Value.role
            }

            $MandatoryObserved = (
                (-not $HasA) -and
                $HubRoleB -eq "MASTER" -and
                $CandidateStatus.node_id -eq $NodeB -and
                $CandidateStatus.role -eq "MASTER" -and
                [int]$CandidateStatus.height -eq $ExpectedHeight -and
                [string]$CandidateStatus.tip_hash -eq $ExpectedTip -and
                [string]$CandidateStatus.tip_hash -ne ("0" * 64) -and
                $CandidateLive.alive -eq $true -and
                $CandidateLive.node_id -eq $NodeB -and
                $CandidateHealth.healthy -eq $true -and
                $CandidateHealth.node_id -eq $NodeB -and
                $CandidateHealth.storage.valid -eq $true -and
                $CandidateReady.ready -eq $true
            )

            if ($MandatoryObserved) {
                $PostB       = $CandidateStatus
                $PostPeers   = $CandidatePeers
                $PostBLive   = $CandidateLive
                $PostBHealth = $CandidateHealth
                $PostBReady  = $CandidateReady
                $PostBCluster = $CandidateCluster
                $PostBMetrics = $CandidateMetrics
                break
            }
        }
        catch {
            # Transitional HTTP failures are observed until
            # the single predefined deadline expires.
        }

        Start-Sleep -Milliseconds 500
    }

    if (
        $null -eq $PostB -or
        $null -eq $PostPeers -or
        $null -eq $PostBLive -or
        $null -eq $PostBHealth -or
        $null -eq $PostBReady -or
        $null -eq $PostBCluster -or
        $null -eq $PostBMetrics
    ) {
        throw "FAILOVER FAIL: mandatory post-failover conditions not all observed within 70 seconds"
    }

    Save-Json "post-b-status.json"    $PostB
    Save-Json "post-b-liveness.json"  $PostBLive
    Save-Json "post-b-health.json"    $PostBHealth
    Save-Json "post-b-readiness.json" $PostBReady
    Save-Json "post-peers.json"       $PostPeers
    Save-Json "post-b-cluster.json"   $PostBCluster
    Save-Json "post-b-metrics.json"   $PostBMetrics
    Log "AUTOMATIC FAILOVER PASS: $NodeB promoted to MASTER"
    Log "PERSISTENCE PASS height=$($PostB.height) tip_hash=$($PostB.tip_hash)"

    @(
        "NIRT-02 RESULT: PASS"
        "Product commit: $ProductCommit"
        "Initial MASTER: $NodeA"
        "Initial FOLLOWER: $NodeB"
        "Failure event: MASTER process terminated"
        "Automatic failover: PASS"
        "New MASTER: $NodeB"
        "Height before failure: $ExpectedHeight"
        "Height after failure: $($PostB.height)"
        "Tip hash before failure: $ExpectedTip"
        "Tip hash after failure: $($PostB.tip_hash)"
        "Liveness after failover: PASS"
        "Health after failover: PASS"
        "Readiness after failover: PASS"
    ) | Set-Content $ResultFile -Encoding UTF8

    $Script:NirtExitCode = 0
    Log "NIRT-02 RESULT PASS"
}
catch {
    $Reason = $_.Exception.Message

    if (-not $ProductExecutionStarted) {
        $Classification = "ABORTED"
        $Script:NirtExitCode = 2
    }
    else {
        $Classification = "FAIL"
        $Script:NirtExitCode = 1
    }

    Log "NIRT-02 RESULT $Classification"
    Log $Reason

    @(
        "NIRT-02 RESULT: $Classification"
        "Product commit: $ProductCommit"
        "Reason: $Reason"
        "Failure event started: $FailureEventStarted"
        "Failed/aborted evidence is intentionally preserved."
    ) | Set-Content $ResultFile -Encoding UTF8
}
finally {

    Log "CLEANUP"

    foreach ($Process in $Processes) {
        Stop-NirtProcess $Process
    }

    if ($null -ne $OldSecret) {
        $env:NEXUS_SECRET_KEY = $OldSecret
    }
    else {
        Remove-Item Env:NEXUS_SECRET_KEY -ErrorAction SilentlyContinue
    }

    if ($null -ne $OldHub) {
        $env:NEXUS_HUB_URL = $OldHub
    }
    else {
        Remove-Item Env:NEXUS_HUB_URL -ErrorAction SilentlyContinue
    }

    if ($null -ne $OldDb) {
        $env:NEXUS_DB_PATH = $OldDb
    }
    else {
        Remove-Item Env:NEXUS_DB_PATH -ErrorAction SilentlyContinue
    }

    if ($WorktreeCreated -and (Test-Path $ProductWorktree)) {
        try {
            git -C $Root worktree remove `
                --force `
                $ProductWorktree
        }
        catch {
            Log "WARNING: frozen worktree cleanup failed"
        }
    }

    if (Test-Path $LogFile) {
        Get-Content $LogFile |
            Set-Content `
                (Join-Path $EvidenceDir "timeline.txt") `
                -Encoding UTF8
    }
    Log "CLEANUP COMPLETE"

    $FilesToHash = Get-ChildItem `
        -Path $EvidenceDir `
        -File |
        Where-Object {
            $_.Name -ne "sha256.txt"
        } |
        Sort-Object Name

    $Manifest = foreach ($File in $FilesToHash) {
        $Hash = Get-FileHash `
            $File.FullName `
            -Algorithm SHA256

        "{0}  {1}" -f $Hash.Hash, $File.Name
    }

    $Manifest |
        Set-Content `
            (Join-Path $EvidenceDir "sha256.txt") `
            -Encoding UTF8

    Write-Host ""
    Write-Host "NIRT-02 finished."
    Write-Host "Evidence:"
    Write-Host $EvidenceDir
}

exit $Script:NirtExitCode


