---
name: weekly-hours-report
description:
  Generate weekly hours reports for QA teams from a Google Sheet (collaborators + PTO).
  Reads PTO absences, team assignments, and backup coverage, builds a report grouped by
  QA level (Q1/Q2/Q3), and exports a formatted, color-coded Excel file.
  Use when asked to generate the weekly hours report or process PTO/team data.
---

# Generate Weekly Hours Report

Generate a formatted Weekly Hours Report `.xlsx` from a single Google Sheet that
holds both the **collaborators** (tab "Team allocation 2026") and the **monthly
PTO** (tabs like "Jul 2026"). The script downloads the Sheet, combines the data,
and exports a color-coded workbook grouped by QA level.

## Always ask which month first

Before running anything, **ask the user which month (and year) they want the
report for**, unless they already stated it in their request. Do not assume the
current month. Confirm the target as `{Month} {Year}` (e.g. "Jul 2026"), then
pass it via `--month` / `--year`.

- Accept Spanish or English month names and map them to the English abbreviation
  the script expects: Ene/Enero→`Jan`, Feb/Febrero→`Feb`, Mar/Marzo→`Mar`,
  Abr/Abril→`Apr`, May/Mayo→`May`, Jun/Junio→`Jun`, Jul/Julio→`Jul`,
  Ago/Agosto→`Aug`, Sep/Septiembre→`Sep`, Oct/Octubre→`Oct`, Nov/Noviembre→`Nov`,
  Dic/Diciembre→`Dec`.
- If the user gives a month but no year, ask for the year (or confirm the
  intended one) before running.

## Quick start

```bash
# 1. Make sure openpyxl is available (one-time)
/usr/bin/python3 -c "import openpyxl" || /usr/bin/pip3 install --user openpyxl

# 2. Run for a given month/year (defaults to the current month)
/usr/bin/python3 scripts/main.py --month Jul --year 2026
```

Output → the Shared drive **Automation Outputs / Weekly Hours Report** folder (see
[Output location](#output-location)).

> Use `/usr/bin/python3` — NOT the bare `python3` (that resolves to the fbcode
> Python which lacks openpyxl; there is no `python`).

## Before running — authentication

Collaborators AND PTO come from a Google Sheet, so the `meta` CLI must be
authenticated. Quick check:

```bash
meta google.sheets get --id 1Vae2OUAdYT3pMAQLLSYcNRBFklJ2WybctNia6OjNK_g
```

If it lists tabs, you're good. If it fails with OAuth / 401 / auth errors, see
[Error: Auth expired](#error-auth-expired) below.

## How it runs (`scripts/main.py`)

1. **Fetch** — `fetch_sheet.py` pulls the "Team allocation 2026" tab and the
   month's PTO tab via `meta google.sheets read` (concurrently), and writes a
   local copy to `scripts/cache/sheet-{Month}-{Year}.xlsx`. Reuses the cache when
   possible — see [Caching & performance](#caching--performance).
2. **Read PTO** — `read_pto.py` parses the monthly tab (absences + holidays + backups).
3. **Read Team** — `read_team.py` parses "Team allocation 2026" (roles, products, QA grouping).
4. **Build** — `build_report.py` combines PTO + team into Q1/Q2/Q3 structures.
5. **Export** — `export_excel.py` writes the formatted, color-coded workbook.

> All **input data** (collaborators, absences, backups) comes from the single
> Google Sheet below — no other source is read. The finished report is then
> *written* to Google Drive (see [Output location](#output-location)).

### Flags

| Flag | Purpose |
|------|---------|
| `--month` | Month name (Jan–Dec). Default: current month. |
| `--year` | Year. Default: current year. |
| `--sheet-id <id>` | Override the Google Sheet ID (default baked into `fetch_sheet.py`). |
| `--sheet-xlsx <path>` | Reuse an already-downloaded Sheet copy instead of downloading again. |
| `--no-cache` | Force a fresh download even if a valid cache exists. |
| `--output <path>` | Override the output `.xlsx` path. |

### Caching & performance

~95% of a run is network time on `meta google.sheets`. To keep reruns fast,
`fetch_sheet.py`:

- Reads the **team tab and month tab concurrently** (one round-trip's worth of
  wall-clock instead of two).
- Caches the download at `scripts/cache/sheet-{Month}-{Year}.xlsx`:
  - **Within 2 minutes** → reuse the cache with **zero network** (~0.2s total).
  - **After 2 minutes** → check the Sheet's `modifiedTime` (via
    `google.sheets describe`); reuse the cache if unchanged, else re-download.
- Use `--no-cache` to bypass all of this and always re-download.

## Data source — one Google Sheet ("PTO Tracker Softtek")

ID `1Vae2OUAdYT3pMAQLLSYcNRBFklJ2WybctNia6OjNK_g`
https://docs.google.com/spreadsheets/d/1Vae2OUAdYT3pMAQLLSYcNRBFklJ2WybctNia6OjNK_g

This single document is the **only** source of truth — collaborators, absences
(PTO/ML), holidays, backups and everything used to compute worked hours. Monthly
tabs are named in English abbreviations (`Jun 2026`, `Jul 2026`, `Aug 2026`),
**not** Spanish (there is no "Junio 2026").

### PTO — monthly tab
- Tab name format: `{Month} {Year}` (e.g. `Jul 2026`; September also matches `Sept 2026`).
- **Row 8** is the header: `QA3 | Collab | <day numbers…> | Backup | Notes`.
- **Row 9+**: one row per collaborator; the name lives in the **Collab** column
  and is the key used to match against the team tab.
- Absence codes: `PTO`, `PTO(PA)`, `ML`, `ML(PA)`, `H` (holiday), `Bench`.

### Collaborators — tab "Team allocation 2026"
- **Header on row 1.** Columns: `App | Feature | QA Lead | Role | QA Analyst | QA Analyst (Full Name) | New QA3`.
- Column mapping used by the report:

  | Sheet column | Used as |
  |--------------|---------|
  | `QA Analyst` | collaborator short name (match key vs PTO **Collab**, shown as Employee) |
  | `QA Analyst (Full Name)` | full name |
  | `App` | Product |
  | `Feature` | Pilar |
  | `Role` | QA grouping (`QA 1`→Q1, `QA 2`→Q2, `QA 3`→Q3) |
  | `QA Lead` / `New QA3` | reference only |

- **Tag** = `QA Analyst - App - Feature` (e.g. `Arath De la Cruz - Central Products - MAA`).
- A collaborator present in the PTO tab but **not** in "Team allocation 2026" is
  skipped with a `WARN … not in team allocation` message (this is expected).

## Business rules

- **Worked hours are computed**, not read: 8h × working days (Mon–Fri), minus
  absences, holidays and bench days. There is no worked-hours column in the Sheet.
- Standard day = **8 hours**; only **Mon–Fri** count as working days.
- **Holidays** (`H`) do not count as worked hours or as absences.
- **Bench** days (from a `TEAM: Bench | Bench <range>` note) subtract worked hours
  but are not absences.
- **Backups** (`↳` rows) show who covers an absent collaborator. A backup is only
  credited on the covered person's **actual PTO/ML days**. Any backup day that is
  a weekend, a holiday, or a bench day (no PTO/ML) is **skipped** with a `WARN`
  instead of failing — e.g. `Jonathan Lopez 2-6` over a holiday on the 3rd, or a
  backup during someone's bench period. Skipped bench/holiday days earn no hours.
- **Emergency** highlight (red) when a collaborator's total absence hours exceed 80.
- Collaborators are grouped into Q1/Q2/Q3 by their `Role`.

### Expected warnings (not errors)

- `WARN <name> not in team allocation, skipping` — the collaborator is in a PTO
  tab but not in "Team allocation 2026"; they are intentionally excluded.
- `WARN <name>: backup <person> on day <n> without PTO/ML, skipping that day` — a
  backup range covers a non-PTO/ML day (e.g. a bench period); that day is ignored.

## Output location

The report is saved into the team's **Shared drive**, via the locally-synced
Google Drive for Desktop mount:

```
Shared drives/Meta - STK/Project Tracking/Automation/Automation Outputs/Weekly Hours Report/
  └─ Weekly-Hours-{Month}-{Year}.xlsx
```

- The `GoogleDrive-<account>` mount is **auto-detected** from whoever runs the
  skill (`~/Library/CloudStorage/GoogleDrive-*`), so it works on any team
  member's computer without editing paths.
- We write to the **local synced folder** and let Google Drive for Desktop push
  it to the cloud. The `meta google.drive upload` API is **not** used — it is
  blocked by corpnet policy and disabled on laptops.
- If the Shared drive isn't mounted locally, the script falls back to
  `scripts/output/` and prints a `WARN`.
- Override the destination with `--output <path>` if needed.

## Output format

- Sections: **Q1, Q2, Q3** (dark-blue headers).
- Columns: Employee, Role, Wave, Product, Pilar, per-week day breakdown + Hrs,
  Abs Hrs, Work Hrs, Comments, Tag.
- Cell colors: PTO (blue), PTO(PA)/ML (yellow), Holiday (purple), Bench (gray),
  Emergency (red), Backup rows (cream), Totals (green).

## Error: Auth expired

If any step fails with "OAuth", "401", or "auth" errors:

1. Run `jf auth`. On x2p devservers this reports success but may not write a token —
   if reads still fail, use the legacy flow below.
2. Go to https://www.internalfb.com/intern/jf/authenticate/
3. Open the **"Legacy Options"** section and copy the **UID** and **NONCE**.
4. Run: `jf auth --skip-legacy-auth-upgrade <UID> <NONCE>`
5. Re-run the skill.
