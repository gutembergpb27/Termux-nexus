param(
    [string]$OutputDirectory = "nirt\evidence"
)

$ErrorActionPreference = "Stop"
# NIRT prerequisite check
$GitCommand = Get-Command git -ErrorAction SilentlyContinue
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (-not $GitCommand) {
    throw "NIRT prerequisite missing: Git."
}

if (-not $PythonCommand) {
    throw "NIRT prerequisite missing: Python."
}

$PythonVersionText = & python --version 2>&1

if ($LASTEXITCODE -ne 0) {
    throw "NIRT prerequisite failure: Python could not be executed."
}

$PythonVersionMatch = [regex]::Match(
    "$PythonVersionText",
    'Python\s+(\d+)\.(\d+)'
)

if (-not $PythonVersionMatch.Success) {
    throw "NIRT prerequisite failure: unable to determine Python version."
}

$PythonMajor = [int]$PythonVersionMatch.Groups[1].Value
$PythonMinor = [int]$PythonVersionMatch.Groups[2].Value

if (($PythonMajor -lt 3) -or
    (($PythonMajor -eq 3) -and ($PythonMinor -lt 10))) {

    throw "NIRT prerequisite failure: Python 3.10 or newer is required."
}

& python -m pytest --version *> $null

if ($LASTEXITCODE -ne 0) {
    throw "NIRT prerequisite missing: pytest for the selected Python interpreter."
}

git worktree list --porcelain *> $null

if ($LASTEXITCODE -ne 0) {
    throw "NIRT prerequisite failure: git worktree is unavailable."
}

$ExpectedCommit = "c8516db7b1fb694af647c80e1f1b9bc828a60d77"
$ExpectedTag = "v2700.0.0-rc1"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

$EvidenceDir = Join-Path $Root "$OutputDirectory\$Timestamp"
$Worktree = Join-Path $env:TEMP "Nexus-NIRT01-$Timestamp"

New-Item -ItemType Directory -Force $EvidenceDir | Out-Null

$LogFile = Join-Path $EvidenceDir "nirt01.log"
$EnvironmentFile = Join-Path $EvidenceDir "environment.txt"
$InstrumentFile = Join-Path $EvidenceDir "instrument.txt"
$ResultFile = Join-Path $EvidenceDir "result.txt"
$HashFile = Join-Path $EvidenceDir "sha256.txt"

function Write-Evidence {
    param([string]$Text)

    $Text | Tee-Object -FilePath $LogFile -Append
}

$InstrumentationCommit = git rev-parse HEAD
$InstrumentationBranch = git branch --show-current
$InstrumentationStatus = git status --porcelain

Write-Evidence "============================================================"
Write-Evidence "NEXUS INDEPENDENT REPRODUCTION TEST Ã¢â‚¬â€ NIRT-01"
Write-Evidence "============================================================"
Write-Evidence "UTC: $((Get-Date).ToUniversalTime().ToString('o'))"
Write-Evidence "Instrumentation commit: $InstrumentationCommit"
Write-Evidence "Frozen product commit: $ExpectedCommit"

if ($InstrumentationStatus) {
    "FAIL - instrumentation repository is not clean" |
        Set-Content $ResultFile -Encoding UTF8

    throw "Instrumentation repository must be clean before NIRT-01."
}

$TagCommit = git rev-list -n 1 $ExpectedTag

if ($TagCommit -ne $ExpectedCommit) {
    "FAIL - frozen tag does not resolve to expected commit" |
        Set-Content $ResultFile -Encoding UTF8

    throw "Frozen tag mismatch."
}

$ProtocolBlob = git rev-parse "HEAD:nirt/NIRT-01.md"
$RunnerBlob = git rev-parse "HEAD:scripts/run-nirt01.ps1"

$ProtocolHash = (
    Get-FileHash `
        (Join-Path $Root "nirt\NIRT-01.md") `
        -Algorithm SHA256
).Hash

$RunnerHash = (
    Get-FileHash `
        $PSCommandPath `
        -Algorithm SHA256
).Hash

@"
NIRT-01 INSTRUMENT

INSTRUMENTATION COMMIT:
$InstrumentationCommit

INSTRUMENTATION BRANCH:
$InstrumentationBranch

PROTOCOL GIT BLOB:
$ProtocolBlob

RUNNER GIT BLOB:
$RunnerBlob

PROTOCOL LOCAL SHA256:
$ProtocolHash

RUNNER LOCAL SHA256:
$RunnerHash

FROZEN TAG:
$ExpectedTag

FROZEN PRODUCT COMMIT:
$ExpectedCommit
"@ | Set-Content $InstrumentFile -Encoding UTF8

$Tests = @(
    "tests/test_cluster_manager.py::test_elect_leader_promotes_selected_node",
    "tests/test_cluster_manager.py::test_elect_leader_changes_previous_master",
    "tests/test_compute_distributed_recoordination.py::test_runtime_retry_recoordinates_after_cluster_leader_change",
    "tests/test_rejoin_integration.py::test_rejoined_follower_converges_with_master",
    "tests/test_runtime_identity.py::test_failover_does_not_mutate_node_identity",
    "tests/test_runtime_identity.py::test_failover_keeps_mesh_monitoring_active",
    "tests/test_core_registration.py::test_runtime_readiness_accepts_healthy_master",
    "tests/test_core_registration.py::test_runtime_readiness_accepts_follower_with_recent_master",
    "tests/test_core_registration.py::test_runtime_readiness_rejects_follower_without_master",
    "tests/test_core_registration.py::test_runtime_readiness_rejects_stale_master_heartbeat",
    "tests/test_core_registration.py::test_runtime_readiness_rejects_unhealthy_storage",
    "tests/test_integrity.py::test_recover_state_recovers_consistent_state_after_restart"
)

$ExitCode = 1
$FinalResult = "FAIL"

try {
    Write-Evidence ""
    Write-Evidence "Creating detached frozen worktree..."

    git worktree add --detach $Worktree $ExpectedCommit

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create frozen worktree."
    }

    Set-Location $Worktree

    $ObservedCommit = git rev-parse HEAD
    $FrozenStatus = git status --porcelain

    if ($ObservedCommit -ne $ExpectedCommit) {
        throw "Detached worktree does not match frozen commit."
    }

    if ($FrozenStatus) {
        throw "Frozen product worktree is not clean."
    }

    @"
NIRT-01 ENVIRONMENT

UTC:
$((Get-Date).ToUniversalTime().ToString('o'))

FROZEN PRODUCT COMMIT:
$ObservedCommit

OS:
$([System.Environment]::OSVersion.VersionString)

POWERSHELL:
$($PSVersionTable.PSVersion)

PYTHON:
$(python --version 2>&1)

PYTEST:
$(python -m pytest --version 2>&1)
"@ | Set-Content $EnvironmentFile -Encoding UTF8

    Write-Evidence ""
    Write-Evidence "Frozen worktree confirmed: $ObservedCommit"
    Write-Evidence "Executing 12 predefined tests..."
    Write-Evidence ""

    $PytestOutput = & python -m pytest @Tests -v 2>&1
    $ExitCode = $LASTEXITCODE

    $PytestOutput | ForEach-Object {
        Write-Evidence "$_"
    }

    if ($ExitCode -eq 0) {
        $FinalResult = "PASS"
    }

    @"
NIRT-01 RESULT

RESULT:
$FinalResult

PYTEST EXIT CODE:
$ExitCode

EXPECTED PRODUCT COMMIT:
$ExpectedCommit

OBSERVED PRODUCT COMMIT:
$ObservedCommit

TEST COUNT:
12
"@ | Set-Content $ResultFile -Encoding UTF8
}
catch {
    Write-Evidence ""
    Write-Evidence "EXECUTION ERROR: $($_.Exception.Message)"

    @"
NIRT-01 RESULT

RESULT:
FAIL

EXECUTION ERROR:
$($_.Exception.Message)

EXPECTED PRODUCT COMMIT:
$ExpectedCommit

TEST COUNT:
12
"@ | Set-Content $ResultFile -Encoding UTF8

    $ExitCode = 1
    $FinalResult = "FAIL"
}
finally {
    Set-Location $Root

    if (Test-Path $Worktree) {
        git worktree remove --force $Worktree | Out-Null
    }

    git worktree prune
}

# IMPORTANT:
# The log must be finalized BEFORE evidence hashes are calculated.

Write-Evidence ""
Write-Evidence "FINAL RESULT: $FinalResult"
Write-Evidence "Evidence directory: $EvidenceDir"
Write-Evidence "Frozen product commit: $ExpectedCommit"
Write-Evidence "Instrumentation commit: $InstrumentationCommit"

Get-ChildItem $EvidenceDir -File |
    Where-Object {
        $_.Name -ne "sha256.txt"
    } |
    Sort-Object Name |
    Get-FileHash -Algorithm SHA256 |
    ForEach-Object {
        "$($_.Hash)  $([System.IO.Path]::GetFileName($_.Path))"
    } |
    Set-Content $HashFile -Encoding ASCII

Write-Host ""
Write-Host "============================================================"
Write-Host "NIRT-01 RESULT: $FinalResult"
Write-Host "============================================================"
Write-Host "Frozen product:"
Write-Host $ExpectedCommit
Write-Host ""
Write-Host "Evidence:"
Write-Host $EvidenceDir

exit $ExitCode
