$ErrorActionPreference = "SilentlyContinue"

$Repo = "C:\Users\Darth\My Drive\CSRN\Development\CSRN-Production-Suite"
$CommandCenter = "http://127.0.0.1:5050/?module=pregame"

# --- OBS ---
$obsRunning = Get-Process obs64 -ErrorAction SilentlyContinue

if (-not $obsRunning) {
    $obsCandidates = @(
        "$env:ProgramFiles\obs-studio\bin\64bit\obs64.exe",
        "${env:ProgramFiles(x86)}\obs-studio\bin\64bit\obs64.exe",
        "$env:LOCALAPPDATA\Programs\obs-studio\bin\64bit\obs64.exe"
    )

    $obs = $obsCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($obs) {
        Start-Process -FilePath $obs -WorkingDirectory (Split-Path $obs)
    }
}

# --- CSRN ---
# Distinguish three states instead of only "is port 5050 listening":
#   HEALTHY - port bound AND /api/health answers 200 {"status":"ok"} -> do nothing
#   DOWN    - nothing listening on 5050                              -> start CSRN
#   HUNG    - port bound but /api/health did not answer in time      -> ask to kill+restart
# When HEALTHY the behaviour is unchanged: fall through and open the tabs.
$HealthUrl = "http://127.0.0.1:5050/api/health"
$launcher  = Join-Path $Repo "RUN_CSRN_COMMAND_CENTER.bat"

function Get-CsrnHealth {
    $listener = Get-NetTCPConnection -LocalPort 5050 -State Listen -ErrorAction SilentlyContinue
    if (-not $listener) { return "DOWN" }
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            $body = $response.Content | ConvertFrom-Json
            if ($body.status -eq "ok") { return "HEALTHY" }
        }
        return "HUNG"
    }
    catch {
        # Port is bound but the HTTP layer did not respond in time / errored.
        return "HUNG"
    }
}

function Get-Port5050Owner {
    $connection = Get-NetTCPConnection -LocalPort 5050 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) { return $null }
    return Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
}

$health = Get-CsrnHealth

if ($health -eq "HUNG") {
    $owner = Get-Port5050Owner
    if ($owner) { $ownerText = "PID $($owner.Id) ($($owner.ProcessName))" } else { $ownerText = "an unknown process" }

    Add-Type -AssemblyName PresentationFramework
    $answer = [System.Windows.MessageBox]::Show(
        "Port 5050 is held by $ownerText but CSRN's health check is not responding.`n`nThe previous CSRN instance appears hung. Stop it and start a fresh one?",
        "CSRN Game Day",
        "YesNo",
        "Warning"
    )

    if ($answer -eq "Yes" -and $owner) {
        Stop-Process -Id $owner.Id -Force
        Start-Sleep -Seconds 2
        $health = "DOWN"
    }
    else {
        # Do not open browser tabs pointed at a known-bad instance.
        exit 1
    }
}

if ($health -eq "DOWN") {
    if (-not (Test-Path $launcher)) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "CSRN launcher was not found:`n$launcher",
            "CSRN Game Day",
            "OK",
            "Error"
        ) | Out-Null
        exit 1
    }

    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/k", "`"$launcher`"" `
        -WorkingDirectory $Repo
}

# --- Wait for CSRN to be ready ---
# Require an actual HEALTHY /api/health, not just any 2xx-4xx from the HTML
# page (a half-alive instance can still serve a cached page).
$ready = $false

for ($i = 0; $i -lt 60; $i++) {
    if ((Get-CsrnHealth) -eq "HEALTHY") {
        $ready = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $ready) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "CSRN did not become healthy on port 5050 within 60 seconds.`n`nCheck the CSRN Command Center window for an error.",
        "CSRN Game Day",
        "OK",
        "Warning"
    ) | Out-Null
    exit 1
}

# --- Chrome ---
$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

$FacebookLive = "https://www.facebook.com/live/producer/v2/?target_id=100075470576573"
$YouTubeLive = "https://studio.youtube.com/channel/UCAZZRMpb3HnrSxCnDiQeH7Q/livestreaming"

if ($chrome) {
    Start-Process -FilePath $chrome -ArgumentList "--new-window", $CommandCenter
    Start-Sleep -Milliseconds 750
    Start-Process -FilePath $chrome -ArgumentList $FacebookLive
    Start-Process -FilePath $chrome -ArgumentList $YouTubeLive
}
else {
    Start-Process $CommandCenter
    Start-Process $FacebookLive
    Start-Process $YouTubeLive
}


