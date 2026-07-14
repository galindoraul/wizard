#!/usr/bin/env python3
"""Reads PTO Tracker from Google Sheets and returns PersonWeekContext for a given week.
Handles weeks that span two months. Detects holidays by text only (H/Holiday in row 3).
Caches results in /tmp for 5 minutes to avoid repeated API calls.
Supports arbitrary week via monday parameter."""

import json
import os
import subprocess
import sys
import time
from calendar import monthrange
from datetime import datetime, timedelta

PTO_SHEET_ID = "1Vae2OUAdYT3pMAQLLSYcNRBFklJ2WybctNia6OjNK_g"
HEADER_ROW = 8
ABSENCE_TYPES = ["pto", "ml", "pto(pa)", "ml(pa)"]

CACHE_DIR = "/tmp"
CACHE_TTL = 300  # 5 minutes


def get_month_name(month_number):
    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    return months[month_number - 1]


def get_week_workdays(monday):
    return [(monday + timedelta(days=i)) for i in range(5)]


def read_sheet_data(sheet_name):
    cmd = [
        "meta",
        "google.sheets",
        "read",
        f"--id={PTO_SHEET_ID}",
        f"--range='{sheet_name}'",
        "--no-header",
        "-o",
        "json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(
            f"Error reading PTO sheet '{sheet_name}': {result.stderr}", file=sys.stderr
        )
        return None
    lines = result.stdout.strip().split("\n")
    json_start = next(
        (i for i, l in enumerate(lines) if l.strip().startswith("[")), None
    )
    if json_start is None:
        print(f"Error: No JSON output from PTO sheet '{sheet_name}'", file=sys.stderr)
        return None
    return json.loads("\n".join(lines[json_start:]))


def parse_pto_data(rows):
    """Parse PTO sheet data. Returns (employees, holiday_days, day_columns)."""
    if not rows or len(rows) < HEADER_ROW:
        return {}, set(), {}

    header = rows[HEADER_ROW - 1]

    # Map day numbers to column indices from header row
    day_columns = {}
    for col_idx in range(2, len(header)):
        try:
            day_num = int(header[col_idx])
            day_columns[day_num] = col_idx
        except (ValueError, TypeError):
            continue

    # Parse holidays from row 3 (index 2)
    holiday_days = set()
    holiday_row = rows[2] if len(rows) > 2 else []
    for day_num, col_idx in day_columns.items():
        if col_idx < len(holiday_row):
            val = str(holiday_row[col_idx]).strip().lower()
            if val in ("h", "holiday"):
                holiday_days.add(day_num)

    # Parse employee absences (rows after header)
    employees = {}
    for row_idx in range(HEADER_ROW, len(rows)):
        row = rows[row_idx]
        if len(row) < 2:
            continue
        name = str(row[1]).strip()
        if not name:
            continue

        absences = []
        for day_num, col_idx in day_columns.items():
            if col_idx < len(row):
                val = str(row[col_idx]).strip()
                if not val:
                    continue
                absences.append({"dayNumber": day_num, "type": val})

        employees[name.lower()] = {
            "name": name,
            "absences": absences,
        }

    return employees, holiday_days, day_columns


def load_month_data(month, year):
    """Load PTO data for a given month."""
    sheet_name = f"{get_month_name(month)} {year}"
    rows = read_sheet_data(sheet_name)
    if not rows:
        return {}, set()

    employees, holiday_days, _ = parse_pto_data(rows)
    return employees, holiday_days


def build_week_context(softtek_pto_name, monday):
    """Build week context for a given Monday."""
    friday = monday + timedelta(days=4)
    week_workdays = get_week_workdays(monday)

    # Determine which months we need to read
    months_needed = set()
    for day in week_workdays:
        months_needed.add((day.month, day.year))

    # Load data for each month
    all_employees = {}
    all_holidays = {}

    for month, year in months_needed:
        employees, holiday_days = load_month_data(month, year)

        for day_num in holiday_days:
            all_holidays[(month, day_num)] = True

        for name_key, emp_data in employees.items():
            if name_key not in all_employees:
                all_employees[name_key] = {"name": emp_data["name"], "absences": []}
            for absence in emp_data["absences"]:
                all_employees[name_key]["absences"].append(
                    {
                        "dayNumber": absence["dayNumber"],
                        "type": absence["type"],
                        "month": month,
                    }
                )

    # Find this user
    user_data = all_employees.get(softtek_pto_name.lower())

    # Calculate absences and holidays for this week
    absence_days = []
    week_holiday_days = []

    for workday in week_workdays:
        day_num = workday.day
        month = workday.month

        if (month, day_num) in all_holidays:
            week_holiday_days.append(day_num)
            continue

        if user_data:
            for absence in user_data["absences"]:
                if absence["dayNumber"] == day_num and absence["month"] == month:
                    normalized_type = absence["type"].strip().lower()
                    if normalized_type in ("h", "holiday"):
                        if day_num not in week_holiday_days:
                            week_holiday_days.append(day_num)
                    elif normalized_type in ABSENCE_TYPES:
                        absence_days.append(day_num)
                    break

    # Calculate working days
    non_working = set(absence_days + week_holiday_days)
    working_days_list = [d for d in week_workdays if d.day not in non_working]

    # Adjust start/finish dates
    expected_start = monday
    expected_finish = friday

    if monday.day in non_working:
        for d in week_workdays:
            if d.day not in non_working:
                expected_start = d
                break

    if friday.day in non_working:
        for d in reversed(week_workdays):
            if d.day not in non_working:
                expected_finish = d
                break

    name = user_data["name"] if user_data else softtek_pto_name

    return {
        "name": name,
        "working_days": len(working_days_list),
        "expected_hours": len(working_days_list) * 8,
        "expected_start_date": expected_start.strftime("%m/%d/%Y"),
        "expected_finish_date": expected_finish.strftime("%m/%d/%Y"),
        "absence_days": absence_days,
        "holiday_days": week_holiday_days,
    }


def get_week_context(softtek_pto_name, monday=None):
    """Main function: returns PersonWeekContext. Cached for 5 min.
    Args:
        softtek_pto_name: Name as it appears in PTO sheet.
        monday: datetime of the target Monday. Defaults to current week.
    """
    if monday is None:
        today = datetime.now()
        monday = (today - timedelta(days=today.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    friday = monday + timedelta(days=4)

    # Check cache
    cache_key = (
        f"c2c_pto_{softtek_pto_name.replace(' ', '_')}_{monday.strftime('%Y%m%d')}"
    )
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.json")

    if os.path.exists(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        if age < CACHE_TTL:
            with open(cache_path) as f:
                return json.load(f)

    # Build fresh
    try:
        context = build_week_context(softtek_pto_name, monday)
    except Exception as e:
        print(f"Warning: PTO read failed ({e}), using defaults.", file=sys.stderr)
        return {
            "name": softtek_pto_name,
            "working_days": 5,
            "expected_hours": 40,
            "expected_start_date": monday.strftime("%m/%d/%Y"),
            "expected_finish_date": friday.strftime("%m/%d/%Y"),
            "absence_days": [],
            "holiday_days": [],
        }

    # Save to cache
    with open(cache_path, "w") as f:
        json.dump(context, f)

    return context


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: pto-reader.py  [--week=current|previous|YYYY-MM-DD]",
            file=sys.stderr,
        )
        sys.exit(1)

    name = sys.argv[1]
    # Parse --week from remaining args
    monday = None
    for arg in sys.argv[2:]:
        if arg.startswith("--week="):
            week_value = arg.split("=", 1)[1]
            today = datetime.now()
            current_monday = (today - timedelta(days=today.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            if week_value == "current":
                monday = current_monday
            elif week_value == "previous":
                monday = current_monday - timedelta(days=7)
            else:
                target = datetime.strptime(week_value, "%Y-%m-%d")
                monday = (target - timedelta(days=target.weekday())).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

    context = get_week_context(name, monday)
    print(json.dumps(context))
