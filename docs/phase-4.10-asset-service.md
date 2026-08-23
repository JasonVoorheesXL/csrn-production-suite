# Phase 4.10 — Asset Service

Phase 4.10 extracts Asset Manager business behavior from Flask into a dedicated `AssetService` boundary.

## Scope

- Canonical asset-record normalization
- Asset listing and filtering
- Asset creation, updating, reading, and deletion
- Stable ID and timestamp handling
- Supported upload-extension validation
- SHA-256 file hashing
- Active duplicate detection by content hash
- Duplicate prompt, reuse, replace, and keep workflows
- File metadata attachment after Flask stores the upload
- Existing `/api/assets` response contracts

Physical upload writes and file serving remain at the Flask boundary. The service owns record decisions and persistence updates.

## Runtime target

- Version: `1.13.0-alpha.4j`
- Build: `V1.13A4J-ASSET-SERVICE`
