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
$csrnRunning = Get-NetTCPConnection -LocalPort 5050 -State Listen -ErrorAction SilentlyContinue

if (-not $csrnRunning) {
    $launcher = Join-Path $Repo "RUN_CSRN_COMMAND_CENTER.bat"

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
$ready = $false

for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $CommandCenter -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
            $ready = $true
            break
        }
    }
    catch {
    }

    Start-Sleep -Seconds 1
}

if (-not $ready) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "CSRN did not become available on port 5050 within 60 seconds.`n`nCheck the CSRN Command Center window for an error.",
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


