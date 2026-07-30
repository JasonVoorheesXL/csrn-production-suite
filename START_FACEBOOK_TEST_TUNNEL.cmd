@echo off
setlocal
where cloudflared >nul 2>&1
if errorlevel 1 (
  echo.
  echo cloudflared is not installed.
  echo Install it from Command Prompt with:
  echo   winget install --id Cloudflare.cloudflared --exact
  echo.
  exit /b 1
)
echo ============================================================
echo CSRN Facebook HTTPS Test Tunnel
echo ============================================================
echo Keep this window open until Facebook Page connection finishes.
echo Copy the https://...trycloudflare.com address shown below.
echo Append: /api/social/facebook/callback
echo Press Ctrl+C after the Facebook connection and read-only test pass.
echo ============================================================
echo.
cloudflared tunnel --url http://127.0.0.1:5050
endlocal
