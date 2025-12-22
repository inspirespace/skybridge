# FlySto API Contract (Placeholder)

Fill in these details once available. This file is used to keep context in-repo.

## Auth
- Method: (header/query)
- Header name:
- Token format:

Observed public bundle references `/api/profile` and `/api/koulouraki-consent`.
Observed upload-related endpoints in bundle:
- `POST /api/log-upload`
- `POST /api/log-files-to-process`
UI flow: Logs page → `Load logs` → `Browse files` (file input appears after click)
Accepted extensions (from UI): `.CSV`, `.ALD`, `.ONFLIGHT`, `.KML`, `.GPX`, `.LOG`, `.TXT`, `.XLSX`

## Endpoints
### Upload Flight
- Method:
- URL:
- Accepted formats (JSON/CSV/IGC/GPX):
- Example request:
- Example response:

### List / Lookup Flights (optional)
- Method:
- URL:
- Response fields:

## Rate Limits
- Limits:
- Backoff guidance:

## Notes
- Dedupe keys:
- Required metadata:
