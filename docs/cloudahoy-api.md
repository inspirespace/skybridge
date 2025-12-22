# CloudAhoy API Contract (Placeholder)

Fill in these details once available. This file is used to keep context in-repo.

## Auth
- Method: (header/query)
- Header name:
- Token format:

Observed web login form posts to `/api/signin.cgi?form`.
Observed JSON APIs in debrief app:
- `POST https://www.cloudahoy.com/api/t-flights.cgi` (list flights)
- `POST https://www.cloudahoy.com/api/t-debrief.cgi` (full flight data with `flt.points` and `flt.KML`)

## Endpoints
### List Flights
- Method: POST (JSON)
- URL: `https://www.cloudahoy.com/api/t-flights.cgi`
- Pagination:
- Example response:

### Flight Detail / Export
- Method: POST (JSON)
- URL: `https://www.cloudahoy.com/api/t-debrief.cgi`
- Supported formats (JSON/CSV/IGC/GPX):
- Example response:

Observed request payload fields:
- `flight` (flight key from `t-flights.cgi`)
- `EMAIL3`, `SID3`, `USER3`
- `BI`, `PH`, `wlh`

## Rate Limits
- Limits:
- Backoff guidance:

## Notes
- Dedupe keys:
- Metadata fields needed by FlySto:
