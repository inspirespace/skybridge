# Skybridge Import Flow — Wireframe Specification

This document describes the final wireframe in `design/final/skybridge-import-flow-wireframe.html` and the static exports in `design/final/exports/` for frontend implementation.

## Contents
- App structure and layout
- Step flow and states
- UI components (per section)
- Mobile vs desktop behavior
- Exported PNG references

## App Structure
- **Layout**: two-column on desktop (left sticky step nav + right content). On mobile, left nav is hidden and replaced by a top bar + bottom stepper.
- **Header (mobile)**: sticky top bar with logo and session actions (Start over, Sign out) when applicable.
- **Footer**: sticky bottom for the page (not viewport). Includes quick links and copyright.
- **Main content**: accordion sections for each step. Only one section open at a time.

## Step Flow (Overall)
1. **Sign in**
2. **Connect accounts + Import filters**
3. **Review**
4. **Import + Results**

Progress rules:
- The left nav (desktop) shows checkmarks for completed steps.
- Locked steps are visible but collapsed and read-only.
- Only the active step is open; previous steps can be opened but are read-only (inputs disabled).
- The active step is also indicated by the mobile stepper.

## Step 1 — Sign in
**Purpose**: authenticate user before any import action.

**Key UI**:
- Intro hero copy (bold paragraph).
- **Trust panel (info/blue)** with bullet list:
  - Why sign-in is required (identify job, protect data, resume later).
  - Privacy assurance (credentials used for this job only, not stored; results retained for 10 days).
  - What gets imported + “you can review before importing.”
- CTA buttons:
  - Primary: “Sign in with email”
  - Secondary: “Continue with Google”, “Continue with Apple”

**State**:
- Pill on header right: `Required` (grey) → `Signed in` (green) once authenticated.

## Step 2 — Connect accounts + Import filters
**Purpose**: provide CloudAhoy + FlySto credentials and set import filters.

**Key UI**:
- Info notice (blue): “Credentials are used only for this job and not stored.”
- Two credential cards:
  - CloudAhoy: Username + Password
  - FlySto: Username + Password
- Import filters card (below credentials):
  - Date range (Start, End)
  - Max flights to import
  - Helper text: “Leave empty to import all available flights. Caps the total number of flights that will be imported.”
- CTA: “Connect and review”

**State**:
- Pill: `Sign in required` until signed in, then `Connected` after successful input + click.
- When editing filters after Review, this section re-opens and inputs become active again.

## Step 3 — Review
**Purpose**: show review progress, preview flights, and approve for import.

**Key UI**:
- Info notice at top: “Flights are fetched from CloudAhoy first so you can check them before running the actual import.”
- Unified progress card:
  - Status label (e.g., “Review running…”, “Review complete”)
  - Elapsed time + last update
  - Progress bar (green tint when complete)
- Review summary banner (neutral background with warning color when missing registrations)
- Review table (horizontal scroll on mobile):
  - Columns: Status (pill), Flight ID (truncated), Date, Registration, Origin, Destination
  - Status pill uses OK / Needs review styling
- Buttons:
  - “Show more flights” (tertiary link-style); becomes “All flights shown” when exhausted
  - “Accept and start import” (enabled only when review is complete and import not finished)
  - “Edit import filters” (visible only after review complete; returns to Step 2)

**State**:
- Pill: `Connect accounts to continue` → `Running review…` → `Review ready` → `Approved`
- Review inputs are disabled after completion (read-only)

## Step 4 — Import + Results
**Purpose**: run import and display outcome summary.

**Key UI**:
- Unified progress card:
  - Status label (e.g., “Import running”, “Import completed”)
  - Elapsed time + last update
  - Progress bar (green tint when complete)
- **Import results card** (non-tabular)
  - 3 rows with status pill + label + description + “Total:” count:
    - Imported flights
    - Skipped or pending
    - Registration missing
- Download report button (only visible after import completes)
- Conclusion panel with next steps + actions:
  - “Open FlySto”
  - “Delete results now” (danger style)

**State**:
- Pill: `Approve review to continue` → `Ready` → `Running` → `Completed`
- Summary card appears once import completes

## Component Behaviors
- **Accordions**: only one open at a time; closed steps are compact and stacked without extra whitespace. Locked steps are visually muted with a dashed border (including the status pill) and lighter header weight to signal preview-only.
- **Progress cards**: green text + progress bar tint for completed state.
- **Status pills**: rounded pill, color-coded (OK = green, Needs review = orange).
- **Tables**: horizontally scrollable on mobile; zebra rows; consistent status column on left.
- **Buttons**:
  - Primary (dark): main action
  - Secondary (bordered): alternative action
  - Tertiary (link style): “Show more flights”
  - Danger: destructive actions

## Mobile vs Desktop
- **Desktop**: left sticky nav with checkmarks; right content with accordions.
- **Mobile**:
  - Top bar with logo + action buttons (visible only when applicable)
  - Bottom stepper with progress bar and “Next: …” label
  - Import filters fields stack vertically
  - Tables scroll horizontally

## Exported Wireframes (PNG)
Static PNG exports are currently removed. When regenerated, capture per‑step states for both desktop and mobile and document the filenames here.

## Notes for Implementation
- Use IBM Plex Sans for body typography.
- Maintain subtle radius on panels; pills fully rounded.
- Match spacing and layout from the wireframe HTML + PNG exports.
