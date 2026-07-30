# Facebook HTTPS Connection Test

Meta requires HTTPS for the OAuth callback used by the current CSRN test app.

For the development test only, CSRN uses a temporary Cloudflare Quick Tunnel:

1. Start CSRN normally and keep it running on `http://127.0.0.1:5050`.
2. Install `cloudflared` once with `winget install --id Cloudflare.cloudflared --exact`.
3. In a separate terminal, start a temporary local-only test tunnel:

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:5050
   ```

   Install Cloudflare Tunnel first with
   `winget install --id Cloudflare.cloudflared --exact` if needed.
4. Copy the generated `https://...trycloudflare.com` address.
5. Append `/api/social/facebook/callback`.
6. Save that exact HTTPS callback in both Meta Facebook Login settings and CSRN's one-time Meta test-app setup.
7. Keep the tunnel window open while clicking **Connect Facebook Page**.
8. After Page selection and **Test connection** succeed, stop the tunnel with `Ctrl+C`.

Quick Tunnels are for development testing only. Commercial release will use a stable PossumFrog-hosted HTTPS connection broker.
