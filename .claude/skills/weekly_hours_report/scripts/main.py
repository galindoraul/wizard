#!/usr/bin/env python3
"""Weekly Hours Report - Main entry point."""
import argparse
from pathlib import Path
from datetime import datetime
from read_pto import read_pto
from read_team import read_team
from build_report import build_report
from export_excel import export_excel
from fetch_sheet import fetch_sheet, DEFAULT_SHEET_ID

# Reports are delivered to this Shared drive folder via the locally-synced Google
# Drive for Desktop mount — the CLI upload API is blocked by corpnet on laptops.
# The GoogleDrive-<account> mount is auto-detected from whoever runs the skill,
# so this works on any team member's computer.
DRIVE_OUTPUTS_REL = "Shared drives/Meta - STK/Project Tracking/Automation/Automation Outputs"
DRIVE_OUTPUT_SUBFOLDER = "Weekly Hours Report"

def resolve_output_path(month, year, override):
    """Save into the Shared drive 'Automation Outputs/Weekly Hours Report' folder."""
    fname = f"Weekly-Hours-{month}-{year}.xlsx"
    if override:
        return Path(override)
    cloud = Path.home() / "Library/CloudStorage"
    if cloud.exists():
        for child in sorted(cloud.iterdir()):
            if not child.name.startswith("GoogleDrive-"):
                continue
            outputs = child / DRIVE_OUTPUTS_REL
            if outputs.exists():
                folder = outputs / DRIVE_OUTPUT_SUBFOLDER
                folder.mkdir(exist_ok=True)  # safe: parent is an already-synced Shared drive folder
                return folder / fname
    print("  WARN: Shared drive 'Automation Outputs' not found locally; saving to scripts/output/ instead")
    return Path(__file__).parent / "output" / fname

def main():
    ap = argparse.ArgumentParser(description="Generate Weekly Hours Report")
    ap.add_argument("--month", help="Month name (Jan-Dec), default current")
    ap.add_argument("--year", type=int, help="Year, default current")
    ap.add_argument("--sheet-id", default=DEFAULT_SHEET_ID, help="Google Sheet ID (collaborators + PTO)")
    ap.add_argument("--sheet-xlsx", help="Use an already-fetched local Sheet xlsx instead of downloading")
    ap.add_argument("--no-cache", action="store_true", help="Force re-download even if a fresh cache exists")
    ap.add_argument("--output", help="Output Excel path (default: local Google Drive 'Weekly Hours Report' folder)")
    args = ap.parse_args()

    now = datetime.now()
    month = args.month or ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][now.month-1]
    year = args.year or now.year

    print(f"Generating Weekly Hours Report for {month} {year}...")

    if args.sheet_xlsx:
        sheet_xlsx = Path(args.sheet_xlsx)
        print(f"Using local Sheet export: {sheet_xlsx}")
    else:
        print("Fetching Google Sheet (collaborators + PTO)...")
        sheet_xlsx = fetch_sheet(month, year, sheet_id=args.sheet_id, force=args.no_cache)
        print(f"  Using local copy: {sheet_xlsx}")

    print("Reading PTO (monthly tab)...")
    pto = read_pto(month, year, pto_path=sheet_xlsx)
    print(f"  Found {len(pto)} employees in PTO")

    print("Reading Team Allocation tab...")
    team = read_team(team_path=sheet_xlsx)
    print(f"  Found {len(team)} collaborators")

    print("Building report...")
    report = build_report(pto, team, month, year)
    total = len(report["q1"]) + len(report["q2"]) + len(report["q3"])
    print(f"  Q1:{len(report['q1'])} Q2:{len(report['q2'])} Q3:{len(report['q3'])} Total:{total}")

    out_path = resolve_output_path(month, year, args.output)
    print("Exporting Excel...")
    export_excel(report, out_path)
    print(f"\nDone! Output: {out_path}")

if __name__ == "__main__":
    main()
