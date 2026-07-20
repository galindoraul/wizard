#!/usr/bin/env python3
"""Validate tasks from stdin and print structured JSON report.
Two-layer validation:
  Layer 1: Per-row field validation
  Layer 2: Per-week PTO calendar validation (effort sum per week)

Groups errors by [Week] for clear presentation.

EXIT CODES:
  0 = validation passed (no errors)
  1 = validation failed (errors found — DO NOT proceed to write)

OUTPUT: JSON object with validation results grouped by week.
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module

pto_reader = import_module("pto-reader")

SKILLS_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
CONFIG_PATH = os.path.join(SKILLS_DIR, "config.json")

# Maps [Type] value from description -> (Requirement Type, Requirement Subtype)
TYPE_MAP = {
    "Test Plan": ("Test Planning", "Test Plan"),
    "Test Strategy": ("Test Planning", "Test Strategy"),
    "Business Requirements": ("Test Analysis", "Business Requirements"),
    "Functional Requirements": ("Test Analysis", "Functional Requirements"),
    "Knowledge Transfer": ("Test Analysis", "Knowledge Transfer"),
    "Test Case": ("Test Design", "Test Case"),
    "Test Data": ("Test Design", "Test Data"),
    "Set Up & Configure Test Environment": (
        "Test Implementation",
        "Set Up & Configure Test Environment",
    ),
    "Test Case Execution": ("Test Execution & Reporting", "Test Case Execution"),
    "Adhoc Testing": ("Test Execution & Reporting", "Adhoc Testing"),
    "Defect Verification": ("Test Execution & Reporting", "Defect Verification"),
    "Log in Defect": ("Test Execution & Reporting", "Log in Defect"),
    "Test Summary Report": ("Test Execution & Reporting", "Test Summary Report"),
    "Management": ("Project Tracking Activities", "Management"),
    "Training": ("Project Tracking Activities", "Training"),
}

VALID_ACTIONS = {
    "Test Planning|Test Plan": ["Create", "Update"],
    "Test Planning|Test Strategy": ["Create", "Update"],
    "Test Analysis|Business Requirements": ["Review"],
    "Test Analysis|Functional Requirements": ["Review"],
    "Test Analysis|Knowledge Transfer": ["Create", "Review"],
    "Test Design|Test Case": ["Create", "Update"],
    "Test Design|Test Data": ["Create", "Update"],
    "Test Design|Test Matrix": ["Create", "Update"],
    "Test Design|Test Script": ["Create", "Update"],
    "Test Design|Traceability Matrix": ["Create", "Update"],
    "Test Implementation|Set Up & Configure Test Environment": ["Create", "Update"],
    "Test Execution & Reporting|Adhoc Testing": ["NA"],
    "Test Execution & Reporting|Defect Verification": ["NA"],
    "Test Execution & Reporting|Log in Defect": ["NA"],
    "Test Execution & Reporting|Test Case Execution": ["NA"],
    "Test Execution & Reporting|Test Script Execution": ["NA"],
    "Test Execution & Reporting|Test Summary Report": ["NA"],
    "Project Tracking Activities|Management": ["NA"],
    "Project Tracking Activities|Personal Time": ["NA"],
    "Project Tracking Activities|Training": ["NA"],
    "Project Tracking Activities|Waiting for Assignation": ["NA"],
}

PEER_REVIEW_SUBTYPES = ["Test Case", "Test Script"]

INT_FIELDS = [
    "Products",
    "TC Pass",
    "TC Fail",
    "TC Blocked",
    "Qty Bugs Closed",
    "Qty Bugs Re-opened",
    "Qty Bugs Verified",
    "Qty New Bugs Found",
]

DECIMAL_FIELDS = [
    "Effort",
    "Peer Review Scheduled Effort",
]

FLOAT_TOLERANCE = 0.001


def iso_week_to_monday(iso_week):
    """Convert ISO week number to Monday date (current year)."""
    today = datetime.now()
    year = today.year
    jan4 = datetime(year, 1, 4)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    monday = start_of_week1 + timedelta(weeks=iso_week - 1)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def get_week_label(iso_week):
    """Get human label: 'Semana 28 (Jul 07 - Jul 11)'."""
    monday = iso_week_to_monday(iso_week)
    friday = monday + timedelta(days=4)
    return (
        f"Semana {iso_week} ({monday.strftime('%b %d')} - {friday.strftime('%b %d')})"
    )


def safe_num(value, default=0):
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    try:
        return int(float(value)) if value else default
    except (ValueError, TypeError):
        return default


def check_int_field(dk, field_name):
    raw = str(dk.get(field_name, "")).strip()
    if not raw:
        return None
    try:
        val = float(raw)
        if val != int(val):
            return {
                "field": field_name,
                "value": raw,
                "expected": "Must be integer (whole number)",
            }
    except (ValueError, TypeError):
        return {"field": field_name, "value": raw, "expected": "Must be a number"}
    return None


# =============================================================================
# LAYER 1: Per-row validation
# =============================================================================


def validate_task(task):
    """Validate a single task (Layer 1). Returns (errors, warnings)."""
    errors = []
    warnings = []
    dk = task.get("descriptionKeys", {})
    category = task.get("category", "")
    module = task.get("module", "")
    team = task.get("team", "")

    # Structure validation (title)
    if not module or not team:
        errors.append(
            {
                "field": "Title",
                "value": "Bad format",
                "expected": "[STK]_[Team]_[Module]_[Activity]: Description",
            }
        )
        return errors, warnings

    # Week validation (required field)
    week_value = dk.get("Week", "").strip()
    if not week_value:
        errors.append(
            {
                "field": "Week",
                "value": "Missing",
                "expected": "Add [Week]: <number> in description",
            }
        )
    else:
        try:
            int(week_value)
        except ValueError:
            errors.append(
                {
                    "field": "Week",
                    "value": f'"{week_value}"',
                    "expected": "Must be a number (ISO week)",
                }
            )

    # Type validation
    if not category:
        errors.append(
            {
                "field": "Type",
                "value": "Missing",
                "expected": "Add [Type]: <value> in description",
            }
        )
    elif category not in TYPE_MAP:
        errors.append(
            {
                "field": "Type",
                "value": f'"{category}"',
                "expected": "Valid types: " + ", ".join(sorted(TYPE_MAP.keys())),
            }
        )

    mapping = TYPE_MAP.get(category)
    req_type = mapping[0] if mapping else ""
    req_subtype = mapping[1] if mapping else ""
    action_key = f"{req_type}|{req_subtype}" if mapping else ""
    valid_actions = VALID_ACTIONS.get(action_key, [])

    is_execution = req_type == "Test Execution & Reporting"
    is_design = req_type == "Test Design"
    is_design_with_peer = is_design and req_subtype in PEER_REVIEW_SUBTYPES

    # Check INT_FIELDS for non-integer decimals
    for field_name in INT_FIELDS:
        if field_name in dk:
            int_err = check_int_field(dk, field_name)
            if int_err:
                errors.append(int_err)

    # Data validation
    effort = safe_num(dk.get("Effort"))
    products = safe_int(dk.get("Products"))
    action = dk.get("Action", "").strip() or "NA"
    tc_pass = safe_int(dk.get("TC Pass"))
    tc_fail = safe_int(dk.get("TC Fail"))
    tc_blocked = safe_int(dk.get("TC Blocked"))
    total = tc_pass + tc_fail + tc_blocked
    qty_bugs_closed = safe_int(dk.get("Qty Bugs Closed"))
    qty_bugs_verified = safe_int(dk.get("Qty Bugs Verified"))
    qty_new_bugs = safe_int(dk.get("Qty New Bugs Found"))
    peer_effort = safe_num(dk.get("Peer Review Scheduled Effort"))

    if valid_actions and action not in valid_actions:
        errors.append(
            {
                "field": "Action",
                "value": f'"{action}"',
                "expected": " or ".join(valid_actions),
            }
        )

    if effort <= 0:
        errors.append(
            {"field": "Effort", "value": "Empty or 0", "expected": "Number > 0"}
        )

    if mapping and not is_execution and products <= 0:
        errors.append(
            {"field": "Products", "value": "Empty or 0", "expected": "Number > 0"}
        )

    if is_design_with_peer and effort > 0:
        min_peer = effort * 0.1
        if peer_effort <= 0:
            errors.append(
                {
                    "field": "Peer Review",
                    "value": "Missing",
                    "expected": f">= {min_peer:.2f} (10% of {effort})",
                }
            )
        elif peer_effort < min_peer - FLOAT_TOLERANCE:
            errors.append(
                {
                    "field": "Peer Review",
                    "value": str(peer_effort),
                    "expected": f">= {min_peer:.2f} (10% of {effort})",
                }
            )

    if is_execution:
        missing = []
        if "TC Pass" not in dk:
            missing.append("TC Pass")
        if "TC Fail" not in dk:
            missing.append("TC Fail")
        if "TC Blocked" not in dk:
            missing.append("TC Blocked")
        if missing:
            errors.append(
                {
                    "field": "TC Fields",
                    "value": f"Missing: {', '.join(missing)}",
                    "expected": "Add [TC Pass], [TC Fail], [TC Blocked]",
                }
            )

    if is_execution and "TC Pass" in dk:
        expected = tc_pass + tc_fail + tc_blocked
        if total != expected:
            errors.append(
                {
                    "field": "TC Sum",
                    "value": f"{total}",
                    "expected": f"{tc_pass}+{tc_fail}+{tc_blocked} = {expected}",
                }
            )

    if (
        tc_fail > 0
        and qty_new_bugs <= 0
        and qty_bugs_closed <= 0
        and qty_bugs_verified <= 0
    ):
        errors.append(
            {
                "field": "Bug Counts",
                "value": f"Fail={tc_fail}, no bugs reported",
                "expected": "Add [Qty New Bugs Found], [Qty Bugs Closed], or [Qty Bugs Verified]",
            }
        )

    # Productivity warnings
    if req_subtype in ("Test Case Execution", "Adhoc Testing") and total > 0:
        ratio = effort / total
        if ratio > 1:
            warnings.append(
                {
                    "field": "Productivity TEP",
                    "value": f"Ratio {ratio:.2f}",
                    "threshold": "<= 1.0",
                }
            )
    elif req_subtype == "Test Script Execution" and total > 0:
        ratio = effort / total
        if ratio > 0.5:
            warnings.append(
                {
                    "field": "Productivity TSE",
                    "value": f"Ratio {ratio:.2f}",
                    "threshold": "<= 0.5",
                }
            )
    elif req_subtype == "Test Case" and is_design and products > 0:
        ratio = effort / products
        if ratio > 2:
            warnings.append(
                {
                    "field": "Productivity TDP",
                    "value": f"Ratio {ratio:.2f}",
                    "threshold": "<= 2.0",
                }
            )
    elif req_subtype == "Test Script" and is_design and products > 0:
        ratio = effort / products
        if ratio > 4:
            warnings.append(
                {
                    "field": "Productivity TSD",
                    "value": f"Ratio {ratio:.2f}",
                    "threshold": "<= 4.0",
                }
            )

    return errors, warnings


# =============================================================================
# LAYER 2: Per-week PTO calendar validation
# =============================================================================


def validate_effort_per_week(tasks, config):
    """Validate effort totals per week against PTO calendar."""
    tasks_by_week = {}
    for task in tasks:
        dk = task.get("descriptionKeys", {})
        week_str = dk.get("Week", "").strip()
        try:
            week_num = int(week_str)
        except (ValueError, TypeError):
            continue
        if week_num not in tasks_by_week:
            tasks_by_week[week_num] = []
        tasks_by_week[week_num].append(task)

    calendar_errors = []
    effort_by_week = {}

    softtek_pto_name = config.get("softtek_pto_name", "")
    if not softtek_pto_name:
        return calendar_errors, effort_by_week

    for week_num, week_tasks in sorted(tasks_by_week.items()):
        monday = iso_week_to_monday(week_num)
        week_context = pto_reader.get_week_context(softtek_pto_name, monday)
        expected_hours = week_context["expected_hours"]
        working_days = week_context["working_days"]

        total_effort = 0
        task_breakdown = []
        for task in week_tasks:
            dk = task.get("descriptionKeys", {})
            category = task.get("category", "")
            mapping = TYPE_MAP.get(category)
            if not mapping:
                continue
            effort = safe_num(dk.get("Effort"))
            total_effort += effort
            task_breakdown.append(
                {
                    "taskId": task.get("id", "?"),
                    "effort": effort,
                    "description": task.get("shortDescription", "")[:40],
                }
            )

        effort_by_week[week_num] = {
            "total": total_effort,
            "expected": expected_hours,
            "working_days": working_days,
            "tasks": task_breakdown,
        }

        if total_effort != expected_hours and total_effort > 0:
            diff = expected_hours - total_effort
            excess = abs(diff)

            # Mark suspicious tasks: effort >= excess (likely wrong [Week])
            for t in task_breakdown:
                t["suspicious"] = diff < 0 and t["effort"] >= excess

            calendar_errors.append(
                {
                    "field": "Effort Total",
                    "week": week_num,
                    "weekLabel": get_week_label(week_num),
                    "actual": total_effort,
                    "expected": expected_hours,
                    "working_days": working_days,
                    "difference": diff,
                    "tasks": task_breakdown,
                }
            )

    return calendar_errors, effort_by_week


# =============================================================================
# MAIN
# =============================================================================


def main():
    raw = sys.stdin.read().strip()
    if not raw or raw == "[]":
        print(json.dumps({"status": "empty", "message": "0 tasks found."}))
        return

    tasks = json.loads(raw)

    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    # Layer 1: per-task validation
    task_results = []
    for task in tasks:
        task_errors, task_warnings = validate_task(task)
        dk = task.get("descriptionKeys", {})
        week_str = dk.get("Week", "").strip()
        try:
            display_week = int(week_str)
        except (ValueError, TypeError):
            display_week = task.get("createdWeek", datetime.now().isocalendar()[1])

        task_results.append(
            {
                "taskId": task["id"],
                "category": task["category"],
                "shortDescription": task["shortDescription"],
                "displayWeek": display_week,
                "errors": task_errors,
                "warnings": task_warnings,
            }
        )

    # Layer 2: per-week calendar validation
    calendar_errors, effort_by_week = validate_effort_per_week(tasks, config)

    # Group errors by week
    all_errors = [t for t in task_results if t["errors"]]
    all_warnings = [t for t in task_results if t["warnings"]]
    has_errors = bool(all_errors) or bool(calendar_errors)

    errors_by_week = {}
    for t in all_errors:
        w = t["displayWeek"]
        if w not in errors_by_week:
            errors_by_week[w] = []
        errors_by_week[w].append(t)

    # Build week labels for all weeks that have errors
    week_labels = {}
    all_weeks = set(errors_by_week.keys())
    for ce in calendar_errors:
        all_weeks.add(ce["week"])
    for w in all_weeks:
        week_labels[str(w)] = get_week_label(w)

    report = {
        "status": "fail" if has_errors else "pass",
        "totalTasks": len(tasks),
        "errorCount": len(all_errors),
        "warningCount": len(all_warnings),
        "okCount": len(tasks) - len(all_errors) - len(all_warnings),
        "taskErrors": all_errors,
        "taskWarnings": all_warnings,
        "errorsByWeek": {str(w): errors_by_week[w] for w in sorted(errors_by_week)},
        "weekLabels": {
            str(w): week_labels[str(w)]
            for w in sorted(week_labels, key=lambda x: int(x))
        },
        "calendarErrors": calendar_errors,
        "effortByWeek": {str(w): effort_by_week[w] for w in sorted(effort_by_week)},
    }

    print(json.dumps(report))

    if has_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
