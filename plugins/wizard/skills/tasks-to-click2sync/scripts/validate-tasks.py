#!/usr/bin/env python3
"""Validate tasks from stdin and print report to console.
Two-layer validation:
  Layer 1: Per-row field validation
  Layer 2: Cross-row PTO calendar validation (effort sum)
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
pto_reader = import_module("pto-reader")

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

CATEGORY_MAP = {
    "Roadmap": ("Test Planning", "Test Strategy"),
    "Test request after closure": ("Test Analysis", "Business Requirements"),
    "Peer Review": ("Test Analysis", "Business Requirements"),
    "AIP Review": ("Test Analysis", "Business Requirements"),
    "Documentation creation": ("Test Analysis", "Knowledge Transfer"),
    "Documentation Update": ("Test Analysis", "Knowledge Transfer"),
    "Test Creation": ("Test Design", "Test Case"),
    "Data Request": ("Test Design", "Test Data"),
    "Data preparation": ("Test Design", "Test Data"),
    "Tool": ("Test Implementation", "Set Up & Configure Test Environment"),
    "Access Request": ("Test Implementation", "Set Up & Configure Test Environment"),
    "Test Execution": ("Test Execution & Reporting", "Test Case Execution"),
    "SEV followup": ("Test Execution & Reporting", "Defect Verification"),
    "Bugs followup": ("Test Execution & Reporting", "Defect Verification"),
    "SEV creation": ("Test Execution & Reporting", "Log in Defect"),
    "Reporting": ("Test Execution & Reporting", "Test Summary Report"),
    "Metrics review": ("Project Tracking Activities", "Management"),
    "Support Activities": ("Project Tracking Activities", "Management"),
    "KT": ("Project Tracking Activities", "Training"),
    "Onboarding": ("Project Tracking Activities", "Training"),
    "Training": ("Project Tracking Activities", "Training"),
    "Clarification": ("Project Tracking Activities", "Training"),
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

TIPS = {
    "Productivity": {
        "TEP": "Effort / Total TCs. Reduce effort or execute more test cases",
        "TSE": "Effort / Total TCs. Reduce effort or execute more test scripts",
        "TDP": "Effort / Products. Reduce effort or add more products",
        "TSD": "Effort / Products. Reduce effort or add more products",
    },
    "Peer Review Min 10%": "Add [Peer Review Scheduled Effort] in description (>= 10% of Effort)",
    "Execution Fields": "Add [TC Pass], [TC Fail], [TC Blocked] in the task description",
    "Bugs": "If there are failed TCs, report at least 1 bug: [Qty New Bugs Found] or [Qty Bugs Closed]",
}


def safe_num(value, default=0):
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


# =============================================================================
# LAYER 1: Per-row validation
# =============================================================================

def validate_task(task):
    """Validate a single task (Layer 1). Returns (errors, warnings)."""
    errors = []
    warnings = []
    dk = task.get("descriptionKeys", {})
    category = task.get("category", "")

    mapping = CATEGORY_MAP.get(category)
    if not mapping:
        errors.append(("Type/Subtype", f'Category "{category}" not recognized', "Valid category", "Check title follows STK_[Mod]_[Team]_Category: Desc"))
        return errors, warnings

    req_type, req_subtype = mapping
    action_key = f"{req_type}|{req_subtype}"
    valid_actions = VALID_ACTIONS.get(action_key, [])

    effort = safe_num(dk.get("Effort"))
    products = safe_num(dk.get("Products"))
    action = dk.get("Action", "").strip() or "NA"
    tc_pass = safe_num(dk.get("TC Pass"))
    tc_fail = safe_num(dk.get("TC Fail"))
    tc_blocked = safe_num(dk.get("TC Blocked"))
    total = tc_pass + tc_fail + tc_blocked
    qty_bugs_closed = safe_num(dk.get("Qty Bugs Closed"))
    qty_new_bugs = safe_num(dk.get("Qty New Bugs Found"))
    peer_effort = safe_num(dk.get("Peer Review Scheduled Effort"))

    is_execution = req_type == "Test Execution & Reporting"
    is_design = req_type == "Test Design"
    is_design_with_peer = is_design and req_subtype in PEER_REVIEW_SUBTYPES
    net_effort = effort - peer_effort if is_design_with_peer and peer_effort else effort

    if valid_actions and action not in valid_actions:
        errors.append(("Action", f'"{action}"', ", ".join(valid_actions), ""))

    if effort <= 0:
        errors.append(("Effort", "Empty or 0", "Numeric value > 0", ""))

    if not is_execution and products <= 0:
        errors.append(("Products", "Empty or 0", "Numeric value > 0", ""))

    if is_design_with_peer and effort > 0:
        if peer_effort <= 0:
            errors.append(("Peer Review Min 10%", "No Peer Review Effort", f">= {effort * 0.1:.1f} (10% of {int(effort)})", TIPS["Peer Review Min 10%"]))
        elif peer_effort < effort * 0.1:
            errors.append(("Peer Review Min 10%", f"Peer Review: {int(peer_effort)}", f">= {effort * 0.1:.1f} (10% of {int(effort)})", TIPS["Peer Review Min 10%"]))

    if is_execution:
        missing = []
        if "TC Pass" not in dk:
            missing.append("TC Pass")
        if "TC Fail" not in dk:
            missing.append("TC Fail")
        if "TC Blocked" not in dk:
            missing.append("TC Blocked")
        if missing:
            errors.append(("Execution Fields", f"Missing: {', '.join(missing)}", "Numeric values", TIPS["Execution Fields"]))

    if is_execution and "TC Pass" in dk:
        expected = tc_pass + tc_fail + tc_blocked
        if total != expected:
            errors.append(("Sum O+P+Q", f"Total ({int(total)}) != {int(tc_pass)}+{int(tc_fail)}+{int(tc_blocked)}", f"Total = {int(expected)}", ""))

    if tc_fail > 0 and qty_new_bugs <= 0 and qty_bugs_closed <= 0:
        errors.append(("Bugs", f"Fail={int(tc_fail)} with no bugs reported", "At least 1 bug", TIPS["Bugs"]))

    if req_subtype == "Test Case Execution" and total > 0:
        ratio = net_effort / total
        if ratio > 1:
            warnings.append(("Productivity (TEP)", f"Ratio: {ratio:.2f}", "<= 1.0", TIPS["Productivity"]["TEP"]))
    elif req_subtype == "Test Script Execution" and total > 0:
        ratio = net_effort / total
        if ratio > 0.5:
            warnings.append(("Productivity (TSE)", f"Ratio: {ratio:.2f}", "<= 0.5", TIPS["Productivity"]["TSE"]))
    elif req_subtype == "Test Case" and is_design and products > 0:
        ratio = net_effort / products
        if ratio > 2:
            warnings.append(("Productivity (TDP)", f"Ratio: {ratio:.2f}", "<= 2.0", TIPS["Productivity"]["TDP"]))
    elif req_subtype == "Test Script" and is_design and products > 0:
        ratio = net_effort / products
        if ratio > 4:
            warnings.append(("Productivity (TSD)", f"Ratio: {ratio:.2f}", "<= 4.0", TIPS["Productivity"]["TSD"]))

    return errors, warnings


# =============================================================================
# LAYER 2: Cross-row PTO calendar validation
# =============================================================================

def validate_against_calendar(tasks, week_context):
    """Validate tasks against PTO calendar context (Layer 2).
    Returns (calendar_errors, breakdown).
    """
    working_days = week_context["working_days"]
    expected_hours = week_context["expected_hours"]

    breakdown = []
    total_effort = 0

    for task in tasks:
        dk = task.get("descriptionKeys", {})
        category = task.get("category", "")
        task_id = task.get("id", "?")

        mapping = CATEGORY_MAP.get(category)
        if not mapping:
            continue

        req_type, req_subtype = mapping
        is_design_with_peer = (req_type == "Test Design" and req_subtype in PEER_REVIEW_SUBTYPES)

        effort = safe_num(dk.get("Effort"))
        peer_effort = safe_num(dk.get("Peer Review Scheduled Effort")) if is_design_with_peer else 0
        net_effort = effort - peer_effort if is_design_with_peer and peer_effort else effort

        total_effort += net_effort
        label = f"{category}: {task.get('shortDescription', '')}"
        breakdown.append((task_id, label, int(net_effort)))

    calendar_errors = []
    if total_effort != expected_hours and total_effort > 0:
        diff = expected_hours - total_effort
        tip = f"Missing {int(diff)}hrs" if diff > 0 else f"Exceeds by {int(abs(diff))}hrs"
        calendar_errors.append((
            "Effort (Sum)",
            f"Sum is {int(total_effort)}hrs",
            f"{expected_hours}hrs ({working_days} days x 8)",
            tip
        ))

    return calendar_errors, breakdown


# =============================================================================
# OUTPUT
# =============================================================================

def print_table(rows, headers):
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    separator = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, col_widths)) + " |"
    print(separator)
    print(header_line)
    print(separator)
    for row in rows:
        print("| " + " | ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths)) + " |")
    print(separator)


def main():
    raw = sys.stdin.read().strip()
    if not raw or raw == "[]":
        print("0 tasks found for this week.")
        return

    tasks = json.loads(raw)

    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_str = f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d, %Y')}"

    config = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    week_context = None
    if config.get("softtek_pto_name"):
        week_context = pto_reader.get_week_context(config["softtek_pto_name"])

    # Layer 1
    error_tasks = []
    warning_tasks = []
    ok_count = 0

    for task in tasks:
        task_errors, task_warnings = validate_task(task)
        task_id = task["id"]
        url = f"https://www.internalfb.com/{task_id}"
        label = f"{task['category']}: {task['shortDescription']}"

        if task_errors:
            error_tasks.append((task_id, url, label, task_errors))
        if task_warnings:
            warning_tasks.append((task_id, url, label, task_warnings))
        if not task_errors and not task_warnings:
            ok_count += 1

    # Layer 2
    calendar_errors = []
    breakdown = []
    if week_context:
        calendar_errors, breakdown = validate_against_calendar(tasks, week_context)

    # Output
    print("")
    print("=" * 60)
    print("  VALIDATION REPORT")
    print("=" * 60)
    print(f"  Week:   {week_str}")
    if week_context:
        print(f"  PTO Tracker:    {week_context['working_days']} working days, {week_context['expected_hours']}hrs expected")
        if week_context.get("holiday_days"):
            print(f"  Holidays: days {week_context['holiday_days']}")
        if week_context.get("absence_days"):
            print(f"  Absences: days {week_context['absence_days']}")
    print(f"  Result: {len(tasks)} tasks | {len(error_tasks)} errors | {len(warning_tasks)} warnings | {ok_count} ok")
    print("=" * 60)

    if error_tasks:
        print("")
        print("  ERRORS (per task)")
        print("-" * 60)
        for task_id, url, label, issues in error_tasks:
            print(f"")
            print(f"  {task_id} \u2014 {label}")
            print(f"  {url}")
            print("")
            rows = [(rule, issue, expected, tip) for rule, issue, expected, tip in issues]
            print_table(rows, ["Rule", "Issue", "Expected", "How to fix"])

    if calendar_errors:
        print("")
        print("  ERRORS (calendar / effort)")
        print("-" * 60)
        for rule, issue, expected, tip in calendar_errors:
            print(f"  {rule}: {issue}, expected {expected}. {tip}")
        print("")
        print("  Breakdown:")
        for task_id, label, effort in breakdown:
            print(f"    {task_id} - {label:<45} -> {effort}hrs")
        total = sum(e for _, _, e in breakdown)
        print(f"    {'':.<45}    -----")
        print(f"    {'Total':<45}    {total}hrs")

    if warning_tasks:
        print("")
        print("  WARNINGS")
        print("-" * 60)
        for task_id, url, label, issues in warning_tasks:
            print(f"")
            print(f"  {task_id} \u2014 {label}")
            print(f"  {url}")
            print("")
            rows = [(rule, issue, expected, tip) for rule, issue, expected, tip in issues]
            print_table(rows, ["Rule", "Issue", "Threshold", "How to fix"])

    print("")
    print("=" * 60)
    has_errors = error_tasks or calendar_errors
    if has_errors:
        print("  Fix the errors in your tasks and run the skill again.")
    else:
        print("  Validation passed. Ready to continue.")
    print("=" * 60)
    print("")


if __name__ == "__main__":
    main()
