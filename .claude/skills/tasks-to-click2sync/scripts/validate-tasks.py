#!/usr/bin/env python3
"""Validate tasks from stdin and print structured JSON report.
Two-layer validation:
  Layer 1: Per-row field validation
  Layer 2: Cross-row PTO calendar validation (effort sum)

Supports --week=current|previous|YYYY-MM-DD for PTO context.

EXIT CODES:
  0 = validation passed (no errors)
  1 = validation failed (errors found — DO NOT proceed to write)

OUTPUT: JSON object with validation results for the agent to format.
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

# Fields that MUST be integers
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

# Fields that allow decimals
DECIMAL_FIELDS = [
    "Effort",
    "Peer Review Scheduled Effort",
]


def parse_week_arg(args):
    """Parse --week argument. Returns the Monday of the target week."""
    week_value = "current"
    for arg in args:
        if arg.startswith("--week="):
            week_value = arg.split("=", 1)[1]

    today = datetime.now()
    current_monday = (today - timedelta(days=today.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if week_value == "current":
        return current_monday
    elif week_value == "previous":
        return current_monday - timedelta(days=7)
    else:
        try:
            target = datetime.strptime(week_value, "%Y-%m-%d")
            target_monday = target - timedelta(days=target.weekday())
            return target_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            print(f"Error: Invalid --week value: {week_value}.", file=sys.stderr)
            sys.exit(1)


def safe_num(value, default=0):
    """Parse as float. Use for decimal-allowed fields."""
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """Parse as integer. Handles '2.0' -> 2. Use for INT_FIELDS."""
    try:
        return int(float(value)) if value else default
    except (ValueError, TypeError):
        return default


def check_int_field(dk, field_name):
    """Check if an INT_FIELD has a non-integer decimal value."""
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

    # Type validation
    if not category:
        errors.append(
            {
                "field": "Type",
                "value": "Missing",
                "expected": "Add [Type]:  in description",
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
        elif peer_effort < min_peer:
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
                    "value": f"Missing: {\', \'.join(missing)}",
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

    if tc_fail > 0 and qty_new_bugs <= 0 and qty_bugs_closed <= 0:
        errors.append(
            {
                "field": "Bug Counts",
                "value": f"Fail={tc_fail}, no bugs reported",
                "expected": "Add [Qty New Bugs Found] or [Qty Bugs Closed]",
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
# LAYER 2: Cross-row PTO calendar validation
# =============================================================================


def validate_against_calendar(tasks, week_context):
    working_days = week_context["working_days"]
    expected_hours = week_context["expected_hours"]

    breakdown = []
    total_effort = 0

    for task in tasks:
        dk = task.get("descriptionKeys", {})
        category = task.get("category", "")
        module = task.get("module", "")

        if not module:
            continue
        mapping = TYPE_MAP.get(category)
        if not mapping:
            continue

        effort = safe_num(dk.get("Effort"))
        total_effort += effort

        short_desc = task.get("shortDescription", "")
        breakdown.append(
            {
                "taskId": task.get("id", "?"),
                "label": f"{category}: {short_desc}",
                "effort": effort,
            }
        )

    calendar_errors = []
    if total_effort != expected_hours and total_effort > 0:
        diff = expected_hours - total_effort
        calendar_errors.append(
            {
                "field": "Effort Total",
                "actual": total_effort,
                "expected": expected_hours,
                "working_days": working_days,
                "difference": diff,
            }
        )

    return calendar_errors, breakdown, total_effort


# =============================================================================
# MAIN
# =============================================================================


def main():
    raw = sys.stdin.read().strip()
    if not raw or raw == "[]":
        print(
            json.dumps({"status": "empty", "message": "0 tasks found for this week."})
        )
        return

    tasks = json.loads(raw)

    monday = parse_week_arg(sys.argv[1:])
    sunday = monday + timedelta(days=6)
    week_str = f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d, %Y')}"

    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    week_context = None
    if config.get("softtek_pto_name"):
        week_context = pto_reader.get_week_context(config["softtek_pto_name"], monday)

    # Layer 1
    task_results = []
    for task in tasks:
        task_errors, task_warnings = validate_task(task)
        task_results.append(
            {
                "taskId": task["id"],
                "category": task["category"],
                "shortDescription": task["shortDescription"],
                "errors": task_errors,
                "warnings": task_warnings,
            }
        )

    # Layer 2
    calendar_errors = []
    breakdown = []
    total_effort = 0
    if week_context:
        calendar_errors, breakdown, total_effort = validate_against_calendar(
            tasks, week_context
        )

    # Build report
    all_errors = [t for t in task_results if t["errors"]]
    all_warnings = [t for t in task_results if t["warnings"]]
    has_errors = bool(all_errors) or bool(calendar_errors)

    report = {
        "status": "fail" if has_errors else "pass",
        "week": week_str,
        "totalTasks": len(tasks),
        "errorCount": len(all_errors),
        "warningCount": len(all_warnings),
        "okCount": len(tasks) - len(all_errors) - len(all_warnings),
        "pto": (
            {
                "workingDays": week_context["working_days"],
                "expectedHours": week_context["expected_hours"],
                "holidays": week_context.get("holiday_days", []),
                "absences": week_context.get("absence_days", []),
            }
            if week_context
            else None
        ),
        "taskErrors": all_errors,
        "taskWarnings": all_warnings,
        "calendarErrors": calendar_errors,
        "effortBreakdown": breakdown,
        "totalEffort": total_effort,
    }

    print(json.dumps(report))

    if has_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
