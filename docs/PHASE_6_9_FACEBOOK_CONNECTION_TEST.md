# Phase 6.9 — Facebook Connection Test (Alpha.6l)

## Scope

This build enables the owner-operated CSRN development workstation to complete a genuine Facebook Login authorization-code flow, enumerate manageable Facebook Pages, securely retain the selected Page authorization, and run a read-only connection health check. It does not make the local desktop-secret design the commercial customer architecture.

## Fixed local callback

```text
http://127.0.0.1:5050/api/social/facebook/callback
```

The operator must open CSRN through `http://127.0.0.1:5050` on the production laptop and register the exact callback in the Meta application. Facebook credential actions are rejected over LAN addresses and from remote control devices.

## Test sequence

1. Create or select a Meta development app owned by the CSRN operator.
2. Add Facebook Login and register the exact callback URI.
3. Keep the Meta app in development mode while testing with an app administrator/developer/tester who also has sufficient Page access.
4. In Social Publishing, expand **One-time Meta test-app setup** and enter the App ID and App Secret locally.
5. Save the setup and click **Connect Facebook Page**.
6. Complete Facebook Login and grant the requested Page permissions.
7. Select the Caledonia Sports Radio Network Page from the returned list.
8. Click **Test connection**. This performs a read-only Page identity request and does not create a post.
9. Only after the health check passes, create and approve a clearly labeled test draft. Publication remains a separate explicit operator action.
10. Use **Disconnect** to remove the selected Page token, or remove the test-app configuration to delete both the Page authorization and locally protected App Secret.

## Credential custody

`Data/Social/facebook_credentials.dat` contains only DPAPI-protected bytes tied to the current Windows user. CSRN never returns the App Secret or Page token to the browser. The credential file and credential-like log values are excluded/redacted from support bundles. The entire `Data/Social/` runtime directory is ignored by Git.

## Commercial boundary

A distributed desktop client cannot safely hold a common Meta App Secret. Commercial onboarding therefore requires a PossumFrog-hosted HTTPS OAuth broker that owns the App Secret, completes the code exchange server-side, maintains approved Meta permissions, and issues only the minimum customer-specific authorization material needed by the installed product.
