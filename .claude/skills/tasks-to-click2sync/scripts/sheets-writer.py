#!/usr/bin/env python3
"""Writes C2CRow data to Click2SyncReport.xlsx using openpyxl. Reads rows from stdin.
Uses a .lock file in Google Drive to prevent concurrent writes.
- If task ID exists for this user: updates the row only if data changed
- If task ID is new: appends at the end
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
except ImportError:
    print("Error: openpyxl not installed. Run: pip3 install openpyxl", file=sys.stderr)
    sys.exit(1)

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

COLUMNS = [
    ("projectId", "Project ID", "default"),
    ("createdBy", "Created By", "default"),
    ("requestNo", "Request No", "default"),
    ("assignTo", "Assigned To", "gold"),
    ("peerReviewer", "Peer Reviewer", "default"),
    ("shortDescription", "Short Description", "default"),
    ("requirementType", "Requirement Type", "default"),
    ("requirementSubtype", "Requirement Subtype", "default"),
    ("moduleFeature", "Module/Feature", "gold"),
    ("team", "Team", "gold"),
    ("numberOfDefectiveProducts", "Number of Defective Products", "default"),
    ("numberOfProducts", "Number of Products (Generated or Modified)", "gold"),
    ("totalOfTestCases", "Total of Test Cases", "default"),
    ("total", "Total", "default"),
    ("pass", "Pass", "default"),
    ("fail", "Fail", "default"),
    ("cantTest", "Cant Test", "default"),
    ("qtyBugsClosed", "Quantity of Bugs Closed", "default"),
    ("qtyBugsReopened", "Quantity of Bugs Re-opened", "default"),
    ("qtyBugsVerified", "Quantity of Bugs Verified", "default"),
    ("qtyNewBugsFound", "Quantity of New Bugs Found", "default"),
    ("releaseBuild", "Release/Build", "gold"),
    ("completePercent", "Complete %", "default"),
    ("defectsAdviceFlag", "Defects Advice Flag", "default"),
    ("peerReviewChecklistReviewed1", "Peer Review Checklist Reviewed", "default"),
    ("peerReviewChecklistTemplate", "Peer Review Checklist Template", "default"),
    ("peerReviewChecklistReviewed2", "Peer Review Checklist Reviewed", "default"),
    ("scheduledStartDate", "Scheduled Start Date", "orange"),
    ("scheduledFinishDate", "Scheduled Finish Date", "orange"),
    ("scheduledDuration", "Scheduled Duration", "default"),
    ("scheduledEffort", "Scheduled Effort", "default"),
    ("peerReviewScheduledEffort", "Peer Review Scheduled Effort (hrs)", "green"),
    ("scheduledReworkEffort", "Scheduled Rework Effort (hrs)", "green"),
    ("scheduledUATReworkEffort", "Scheduled UAT Rework Effort", "green"),
    ("actualStartDate", "Actual Start Date", "default"),
    ("actualFinishDate", "Actual Finish Date", "default"),
    ("actualDuration", "Actual Duration", "default"),
    ("actualEffort", "Actual Effort", "default"),
    ("peerReviewActualEffort", "Peer Review Actual Effort (hrs)", "green"),
    ("actualReworkEffort", "Actual Rework Effort (hrs)", "green"),
    ("actualUATReworkEffort", "Actual UAT Rework Effort", "green"),
    ("closedOn", "Closed On", "default"),
    ("forClosing", "ForClosing", "default"),
    ("action", "Action", "default"),
    ("peerReviewChecklist", "Peer Review Checklist Reviewed", "blueMedium"),
    ("estimationLink", "Estimation", "blueMedium"),
]

COLORS = {
    "default": "1a3a5c",
    "gold": "8b6d1a",
    "green": "2d5a3a",
    "blueMedium": "1a4b6e",
    "orange": "8b4513",
}

GRAYABLE_FIELDS = {
    "estimationLink", "peerReviewer", "peerReviewScheduledEffort",
    "peerReviewActualEffort", "peerReviewChecklist", "numberOfProducts",
    "numberOfDefectiveProducts", "totalOfTestCases", "actualReworkEffort",
    "actualUATReworkEffort", "scheduledReworkEffort", "scheduledUATReworkEffort",
    "defectsAdviceFlag", "peerReviewChecklistReviewed1",
    "peerReviewChecklistTemplate", "peerReviewChecklistReviewed2", "closedOn",
    "total", "pass", "fail", "cantTest", "qtyBugsClosed",
    "qtyBugsReopened", "qtyBugsVerified", "qtyNewBugsFound",
}

THIN_BORDER = Border(
    top=Side(style='thin'), bottom=Side(style='thin'),
    left=Side(style='thin'), right=Side(style='thin')
)

LOCK_MAX_WAIT = 90
LOCK_STALE_TIMEOUT = 30
LOCK_POLL_INTERVAL = 2


def get_week_tab_name():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return f"{monday.strftime('%b')} {monday.day}-{sunday.day}"


def get_xlsx_path(config):
    meta_username = config["meta_username"]
    base = Path.home() / "Library" / "CloudStorage" / f"GoogleDrive-{meta_username}@meta.com"
    return base / "Shared drives" / "Meta - STK" / "Project Tracking" / "Automation" / "Automation Outputs" / "Click2SyncReport.xlsx"


def acquire_lock(lock_path, username):
    waited = 0
    while lock_path.exists():
        try:
            lock_content = lock_path.read_text().strip()
            lock_time = lock_content.split("|")[-1] if "|" in lock_content else ""
            if lock_time:
                lock_dt = datetime.fromisoformat(lock_time)
                age = (datetime.now() - lock_dt).total_seconds()
                if age > LOCK_STALE_TIMEOUT:
                    lock_path.unlink(missing_ok=True)
                    break
        except (ValueError, OSError):
            pass
        if waited >= LOCK_MAX_WAIT:
            return False
        time.sleep(LOCK_POLL_INTERVAL)
        waited += LOCK_POLL_INTERVAL

    lock_path.write_text(f"{username}|{datetime.now().isoformat()}")
    time.sleep(2)
    try:
        content = lock_path.read_text().strip()
        if not content.startswith(f"{username}|"):
            return False
    except OSError:
        return False
    return True


def release_lock(lock_path):
    lock_path.unlink(missing_ok=True)


def get_last_request_no(wb, tab_name):
    if tab_name in wb.sheetnames:
        ws = wb[tab_name]
        for row_idx in range(ws.max_row, 0, -1):
            val = ws.cell(row=row_idx, column=3).value
            if val and str(val).startswith("29582-3-"):
                try:
                    return int(str(val).replace("29582-3-", ""))
                except ValueError:
                    continue

    for tab in reversed(wb.sheetnames):
        if tab == tab_name:
            continue
        ws = wb[tab]
        for row_idx in range(ws.max_row, 0, -1):
            val = ws.cell(row=row_idx, column=3).value
            if val and str(val).startswith("29582-3-"):
                try:
                    return int(str(val).replace("29582-3-", ""))
                except ValueError:
                    continue

    return 10200


def extract_task_id(short_description):
    """Extract task ID from '[T123456] desc' or '[123456] desc'."""
    match = re.match(r'^\[T?(\d+)\]', str(short_description))
    return match.group(1) if match else None


def write_headers(ws):
    for col_idx, (key, label, color_name) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font = Font(bold=True, color="FFFFFF", size=9)
        cell.fill = PatternFill(start_color=COLORS[color_name], end_color=COLORS[color_name], fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER
    ws.row_dimensions[1].height = 30
    last_col_letter = ws.cell(row=1, column=len(COLUMNS)).column_letter
    ws.auto_filter.ref = f"A1:{last_col_letter}1"


def write_row(ws, row_idx, row_data):
    for col_idx, (key, _, _) in enumerate(COLUMNS, 1):
        value = row_data.get(key, "")
        cell = ws.cell(row=row_idx, column=col_idx, value=value)
        cell.font = Font(size=9)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER
        if key in GRAYABLE_FIELDS and not value:
            cell.fill = PatternFill(start_color="d4d4d8", end_color="d4d4d8", fill_type="solid")
            cell.font = Font(size=9, color="71717a")


def set_column_widths(ws):
    for col_idx, (key, label, _) in enumerate(COLUMNS, 1):
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[col_letter].width = len(label) + 4


def row_has_changes(ws, row_idx, row_data):
    """Check if the new data differs from what's already in the sheet."""
    for col_idx, (key, _, _) in enumerate(COLUMNS, 1):
        if key == "requestNo":
            continue
        old_val = str(ws.cell(row=row_idx, column=col_idx).value or "")
        new_val = str(row_data.get(key, ""))
        if old_val != new_val:
            return True
    return False


def main():
    if not os.path.exists(CONFIG_PATH):
        print("Error: config.json not found.", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    rows = json.loads(sys.stdin.read())
    if not rows:
        print("No rows to write.")
        return

    xlsx_path = get_xlsx_path(config)
    tab_name = get_week_tab_name()
    my_username = config["softtek_username"]

    lock_path = xlsx_path.parent / ".c2c_write.lock"

    print("Acquiring write lock...", end=" ", flush=True)
    if not acquire_lock(lock_path, my_username):
        print("TIMEOUT")
        print("Error: Could not acquire write lock. Another user may be writing. Try again in 2 minutes.", file=sys.stderr)
        sys.exit(1)
    print("OK")

    try:
        if xlsx_path.exists():
            wb = load_workbook(str(xlsx_path))
        else:
            wb = Workbook()
            if "Sheet" in wb.sheetnames:
                del wb["Sheet"]

        if tab_name not in wb.sheetnames:
            ws = wb.create_sheet(tab_name)
            write_headers(ws)
        else:
            ws = wb[tab_name]

        # Get last request number
        last_req_no = get_last_request_no(wb, tab_name)
        counter = last_req_no + 1

        # Build index: task_id -> row_number (for this user only)
        existing_task_rows = {}
        for row_idx in range(2, ws.max_row + 1):
            owner = ws.cell(row=row_idx, column=2).value
            desc = ws.cell(row=row_idx, column=6).value
            if owner and str(owner) == my_username and desc:
                task_id = extract_task_id(str(desc))
                if task_id:
                    existing_task_rows[task_id] = row_idx

        # Process rows
        updated_count = 0
        new_rows = []

        for row in rows:
            task_id = extract_task_id(row.get("shortDescription", ""))
            if task_id and task_id in existing_task_rows:
                # Existing task - only update if data changed
                target_row_idx = existing_task_rows[task_id]
                existing_req_no = ws.cell(row=target_row_idx, column=3).value
                if existing_req_no:
                    row["requestNo"] = str(existing_req_no)
                if row_has_changes(ws, target_row_idx, row):
                    write_row(ws, target_row_idx, row)
                    updated_count += 1
            else:
                # New task
                row["requestNo"] = f"29582-3-{counter:05d}"
                new_rows.append(row)
                counter += 1

        # Append new rows at end
        if new_rows:
            start_row = ws.max_row + 1
            for i, row_data in enumerate(new_rows):
                write_row(ws, start_row + i, row_data)

        # Set column widths
        set_column_widths(ws)

        if updated_count == 0 and not new_rows:
            print(f"All rows up to date for '{my_username}' in '{tab_name}'.")
            return

        wb.save(str(xlsx_path))
        parts = []
        if new_rows:
            parts.append(f"{len(new_rows)} new")
        if updated_count:
            parts.append(f"{updated_count} updated")
        print(f"{', '.join(parts)} rows in '{tab_name}' in Click2SyncReport.xlsx")

    finally:
        release_lock(lock_path)


if __name__ == "__main__":
    main()
