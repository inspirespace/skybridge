## Remarks + Import Tagging Plan

### Goal
- Import CloudAhoy remarks into an appropriate FlySto field per log.
- Mark each imported flight in FlySto so we can detect duplicates later using compact tags per import run:
  - `cloudahoy`
  - `cloudahoy:<timestamp>` (import run timestamp, ISO UTC, minute precision)

### Current Unknowns / Discovery Needed
- CloudAhoy: exact field(s) for remarks in the flight detail payload (likely in `flt.Meta` or a top-level notes field).
- FlySto: API endpoint/payload for:
  - Setting per-log remarks/notes.
  - Adding or editing tags per log.

### Proposed Mapping
- **Remarks source:** extract a single remarks string from CloudAhoy payload.
  - Prefer a dedicated remarks/notes field if present.
  - Fallback: combine multiple fields (if any) with separators.
  - Normalize whitespace; skip if empty.
- **FlySto destination:** per-log remarks/notes field if available; otherwise create a `Remarks` tag with the text (last-resort).
- **Import marker:** `cloudahoy` + `cloudahoy:<timestamp>` (import run time, UTC ISO minute).

### Idempotency Strategy
- Store a per-flight marker in FlySto (tag) so repeated imports can detect and skip or update in-place.
- Additionally, record the marker in `data/migration.db` so local re-runs avoid duplicate API calls.

### Current Implementation Notes
- Uses `PUT /api/log-annotations/{logIdString}` to update `remarks` and `tags` for a log.
- Sends only `cloudahoy` and `cloudahoy:<timestamp>` tags derived from the import run (CloudAhoy tags are ignored).
- Repairs common UTF-8 mojibake in remarks (e.g., `Ãœ` → `Ü`).
- Does not merge existing FlySto tags (endpoint appears write-only).

### Implementation Outline
1) Locate CloudAhoy remarks in the raw payload (add extraction in `src/migration.py` / metadata helper).
2) Add FlySto client calls for remarks and tags:
   - `assign_remarks_for_file(filename, remarks)` (or per-log ID if required).
   - `assign_tags_for_file(filename, tags)` (include `cloudahoy:<id>`).
3) Wire into migration flow after upload (and after aircraft/crew assignment).
4) Add offline tests covering:
   - Remarks extraction/normalization.
   - Tag generation.
   - Avoiding duplicate tags in repeated runs.

### Open Questions
- Does FlySto allow free-text remarks via API, or only tags?
- Are tags unique or multi-valued, and how are they represented in the API?
- If FlySto only allows editing via log ID (not filename), do we need to map filename → log ID first?
