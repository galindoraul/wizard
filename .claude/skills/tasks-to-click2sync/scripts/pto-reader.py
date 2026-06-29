#!/usr/bin/env python3
"""Reads PTO Tracker from Google Sheets and returns PersonWeekContext for the current week.
Handles weeks that span two months (e.g., Jun 30 - Jul 4)."""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from calendar import monthrange

PTO_SHEET_ID = "1Vae2OUAdYT3pMAQLLSYcNRBFklJ2WybctNia6OjNK_g"
HEADER_ROW = 8
ABSENCE_TYPES = ["pto", "ml", "pto(pa)", "ml(pa)"]


def get_month_name(month_number):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return months[month_number - 1]


def get_week_of_month(date):
    first_day = date.replace(day=1)
    first_monday = first_day
    while first_monday.weekday() != 0:
        first_monday += timedelta(days=1)
    if date < first_monday:
        return 1
    diff = (date - first_monday).days
    return (diff // 7) + 1


def get_current_week_dates():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    friday = monday + timedelta(days=4)
    return monday, friday


def get_week_workdays(monday):
    return [(monday + timedelta(days=i)) for i in range(5)]


def read_sheet_data(sheet_name):
    cmd = [
        "meta", "google.sheets", "read",
        f"--id={PTO_SHEET_ID}",
        f"--range='{sheet_name}'",
        "--no-header", "-o", "json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error reading PTO sheet: {result.stderr}", file=sys.stderr)
        return None
    lines = result.stdout.strip().split('\n')
    json_start = next((i for i, l in enumerate(lines) if l.strip().startswith('[')), None)
    if json_start is None:
        print("Error: No JSON output from PTO sheet read", file=sys.stderr)
        return None
    return json.loads('\n'.join(lines[json_start:]))


def read_header_colors(sheet_name):
    """Read header row background colors to detect holidays (#b4a7d6)."""
    cmd = (
        f'meta google_api_proxy.request --method=GET '
        f'--endpoint="https://sheets.googleapis.com/v4/spreadsheets/{PTO_SHEET_ID}" '
        f"--query-params=\"ranges='{sheet_name}'!A{HEADER_ROW}:AG{HEADER_ROW}"
        f"&includeGridData=true"
        f"&fields=sheets.data.rowData.values(userEnteredFormat.backgroundColor,formattedValue)\" "
        f"-o json"
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return set()
    try:
        lines = result.stdout.strip().split('\n')
        json_start = next((i for i, l in enumerate(lines) if l.strip().startswith('{')), None)
        if json_start is None:
            return set()
        data = json.loads('\n'.join(lines[json_start:]))
        body = data.get("body", data)
        sheets = body.get("sheets", [])
        if not sheets:
            return set()
        row_data = sheets[0].get("data", [{}])[0].get("rowData", [])
        if not row_data:
            return set()
        holiday_days = set()
        for cell in row_data[0].get("values", []):
            fmt_val = cell.get("formattedValue", "")
            bg = cell.get("userEnteredFormat", {}).get("backgroundColor", {})
            try:
                day_num = int(fmt_val)
            except (ValueError, TypeError):
                continue
            r = bg.get("red", 0)
            g = bg.get("green", 0)
            b = bg.get("blue", 0)
            if abs(r - 0.706) < 0.02 and abs(g - 0.655) < 0.02 and abs(b - 0.839) < 0.02:
                holiday_days.add(day_num)
        return holiday_days
    except (ValueError, KeyError, json.JSONDecodeError):
        return set()


def parse_pto_data(rows):
    if not rows or len(rows) < HEADER_ROW:
        return {}, set(), {}

    header = rows[HEADER_ROW - 1]

    day_columns = {}
    for col_idx in range(2, len(header)):
        try:
            day_num = int(header[col_idx])
            day_columns[day_num] = col_idx
        except (ValueError, TypeError):
            continue

    # Parse holidays from text only ("H" or "Holiday" in row 4, index 3)
    holiday_days = set()
    holiday_row = rows[3] if len(rows) > 3 else []
    for day_num, col_idx in day_columns.items():
        if col_idx < len(holiday_row):
            val = str(holiday_row[col_idx]).strip().lower()
            if val in ("h", "holiday"):
                holiday_days.add(day_num)

    # Parse employee absences
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
    """Load PTO data for a given month. Returns (employees, holiday_days) or (None, None) on failure."""
    sheet_name = f"{get_month_name(month)} {year}"
    rows = read_sheet_data(sheet_name)
    if not rows:
        return {}, set()

    employees, holiday_days, _ = parse_pto_data(rows)

    # Also detect holidays by header color
    color_holidays = read_header_colors(sheet_name)
    holiday_days = holiday_days | color_holidays

    return employees, holiday_days


def build_week_context(softtek_pto_name, monday, friday):
    """Build week context handling cross-month weeks."""
    week_workdays = get_week_workdays(monday)  # list of datetime objects

    # Determine which months we need to read
    months_needed = set()
    for day in week_workdays:
        months_needed.add((day.month, day.year))

    # Load data for each month
    all_employees = {}  # name -> absences list
    all_holidays = {}   # (month, day_num) -> True

    for month, year in months_needed:
        employees, holiday_days = load_month_data(month, year)

        # Merge holidays (stored with month context)
        for day_num in holiday_days:
            all_holidays[(month, day_num)] = True

        # Merge employee absences
        for name_key, emp_data in employees.items():
            if name_key not in all_employees:
                all_employees[name_key] = {"name": emp_data["name"], "absences": []}
            for absence in emp_data["absences"]:
                # Tag absence with its month for cross-month matching
                all_employees[name_key]["absences"].append({
                    "dayNumber": absence["dayNumber"],
                    "type": absence["type"],
                    "month": month,
                })

    # Find this user
    user_data = all_employees.get(softtek_pto_name.lower())

    # Calculate absences and holidays for this week
    absence_days = []
    week_holiday_days = []

    for workday in week_workdays:
        day_num = workday.day
        month = workday.month

        # Check if this day is a holiday
        if (month, day_num) in all_holidays:
            week_holiday_days.append(day_num)
            continue

        # Check user absences
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

    # Adjust start/finish dates for holidays/absences at edges
    expected_start = monday
    expected_finish = friday

    if monday.day in set(week_holiday_days) or monday.day in set(absence_days):
        # Find first working day
        for d in week_workdays:
            if d.day not in non_working:
                expected_start = d
                break

    if friday.day in set(week_holiday_days) or friday.day in set(absence_days):
        # Find last working day
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


def get_week_context(softtek_pto_name):
    """Main function: returns PersonWeekContext for the given user."""
    monday, friday = get_current_week_dates()

    try:
        return build_week_context(softtek_pto_name, monday, friday)
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pto-reader.py <softtek_pto_name>", file=sys.stderr)
        sys.exit(1)
    context = get_week_context(sys.argv[1])
    print(json.dumps(context))
