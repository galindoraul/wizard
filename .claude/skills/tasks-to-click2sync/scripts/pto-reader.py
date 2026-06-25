#!/usr/bin/env python3
"""Reads PTO Tracker from Google Sheets and returns PersonWeekContext for the current week."""

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


def get_month_workdays(year, month):
    days_in_month = monthrange(year, month)[1]
    workdays = []
    for day in range(1, days_in_month + 1):
        d = datetime(year, month, day)
        if d.weekday() < 5:
            workdays.append(d)
    return workdays


def get_current_week_dates():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    friday = monday + timedelta(days=4)
    return monday, friday


def get_week_workdays(monday):
    return [(monday + timedelta(days=i)).day for i in range(5)]


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

    # Parse employee absences (row 9+, index 8+)
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


def build_week_context(employee_data, holiday_days, year, month):
    monday, friday = get_current_week_dates()
    week_workdays = get_week_workdays(monday)

    absence_days = []
    week_holiday_days = []

    for absence in employee_data["absences"]:
        day_num = absence["dayNumber"]
        if day_num not in week_workdays:
            continue
        normalized_type = absence["type"].strip().lower()
        if normalized_type in ("h", "holiday"):
            week_holiday_days.append(day_num)
        elif normalized_type in ABSENCE_TYPES:
            absence_days.append(day_num)

    for day_num in holiday_days:
        if day_num in week_workdays and day_num not in week_holiday_days:
            week_holiday_days.append(day_num)

    non_working = set(absence_days + week_holiday_days)
    working_days = [d for d in week_workdays if d not in non_working]

    expected_start = monday
    expected_finish = friday

    if monday.day in set(week_holiday_days):
        expected_start = monday + timedelta(days=1)
    if friday.day in set(week_holiday_days):
        expected_finish = friday - timedelta(days=1)

    return {
        "name": employee_data["name"],
        "working_days": len(working_days),
        "expected_hours": len(working_days) * 8,
        "expected_start_date": expected_start.strftime("%m/%d/%Y"),
        "expected_finish_date": expected_finish.strftime("%m/%d/%Y"),
        "absence_days": absence_days,
        "holiday_days": week_holiday_days,
    }


def get_week_context(softtek_pto_name):
    now = datetime.now()
    month_name = get_month_name(now.month)
    year = now.year
    sheet_name = f"{month_name} {year}"
    monday, friday = get_current_week_dates()

    rows = read_sheet_data(sheet_name)
    if not rows:
        return {
            "name": softtek_pto_name,
            "working_days": 5,
            "expected_hours": 40,
            "expected_start_date": monday.strftime("%m/%d/%Y"),
            "expected_finish_date": friday.strftime("%m/%d/%Y"),
            "absence_days": [],
            "holiday_days": [],
        }

    employees, holiday_days, _ = parse_pto_data(rows)

    # Also detect holidays by header color (#b4a7d6)
    color_holidays = read_header_colors(sheet_name)
    holiday_days = holiday_days | color_holidays

    user_data = employees.get(softtek_pto_name.lower())
    if not user_data:
        week_workdays = get_week_workdays(monday)
        working_days = [d for d in week_workdays if d not in holiday_days]
        expected_start = monday
        expected_finish = friday
        if monday.day in holiday_days:
            expected_start = monday + timedelta(days=1)
        if friday.day in holiday_days:
            expected_finish = friday - timedelta(days=1)
        return {
            "name": softtek_pto_name,
            "working_days": len(working_days),
            "expected_hours": len(working_days) * 8,
            "expected_start_date": expected_start.strftime("%m/%d/%Y"),
            "expected_finish_date": expected_finish.strftime("%m/%d/%Y"),
            "absence_days": [],
            "holiday_days": list(holiday_days),
        }

    return build_week_context(user_data, holiday_days, year, now.month)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pto-reader.py <softtek_pto_name>", file=sys.stderr)
        sys.exit(1)
    context = get_week_context(sys.argv[1])
    print(json.dumps(context))
