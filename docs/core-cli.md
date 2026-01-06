# Core CLI & Migration Logic

Location: `src/core/`

## Purpose
`src/core/` implements the main CloudAhoy → FlySto migration logic used by both
CLI and backend worker.

## Key modules
- `cli.py`: CLI entrypoint.
- `migration.py`: Core migration steps (review generation + import execution).
- `guided.py`: CLI UX helpers and summaries.
- `cloudahoy/`, `flysto/`: API adapters and serializers.

## Migration pipeline
1. **Review**
   - Fetch CloudAhoy flights
   - Normalize data
   - Produce review summary + artifacts
2. **Import**
   - Submit to FlySto
   - Reconcile responses
   - Emit import report

## Fixtures
- Test fixtures live under `tests/fixtures/` and are used by mocks.
