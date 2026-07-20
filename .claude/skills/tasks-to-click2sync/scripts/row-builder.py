#!/usr/bin/env python3
"""Builds C2CRow objects from tasks + PTO context. Reads tasks from stdin.
Groups rows by [Week] and outputs JSON grouped by week tab name.
Runs internal validation before building — refuses to produce output if validation fails.
"""

import json
import os
import sys
from datetime import datetime, timedelta

SKILLS_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
CONFIG_PATH = os.path.join(SKILLS_DIR, "config.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module

pto_reader = import_module("pto-reader")
validator = import_module("validate-tasks")

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
    "Management": ("Project Tracking Activities", "Management"),
    "Training": ("Project Tracking Activities", "Training"),
    "Test Case Execution": ("Test Execution & Reporting", "Test Case Execution"),
    "Adhoc Testing": ("Test Execution & Reporting", "Adhoc Testing"),
    "Defect Verification": ("Test Execution & Reporting", "Defect Verification"),
    "Log in Defect": ("Test Execution & Reporting", "Log in Defect"),
    "Test Summary Report": ("Test Execution & Reporting", "Test Summary Report"),
}

PEER_REVIEW_SUBTYPES = ["Test Case", "Test Script"]
PEER_REVIEW_CHECKLIST_LINK = "https://onesofttek.sharepoint.com/:f:/r/sites/SKPmetap/qanstt/Shared%20Documents/Project%20Tracking/Quality%20Tools/Peer%20Reviews?csf=1&web=1&e=eRpH6D"
ESTIMATION_LINKS = {
    "Test Design": "https://onesofttek.sharepoint.com/:f:/r/sites/SKPmetap/qanstt/Shared%20Documents/Project%20Tracking/Quality%20Tools/Estimations?csf=1&web=1&e=MWJjR3",
    "Test Execution & Reporting": "https://onesofttek.sharepoint.com/:f:/r/sites/SKPmetap/qanstt/Shared%20Documents/Project%20Tracking/Quality%20Tools/Estimations?csf=1&web=1&e=MWJjR3",
}


def get_week_tab_name(iso_week):
    """Convert ISO week number to tab name (e.g. 'Jul 7-13')."""
    monday = validator.iso_week_to_monday(iso_week)
    sunday = monday + timedelta(days=6)
    return f"{monday.strftime('%b')} {monday.day}-{sunday.day}"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def safe_int(value, default=0):
    try:
        return int(float(value)) if value else default
    except (ValueError, TypeError):
        return default


def safe_int_str(value):
    if not value:
        return ""
    try:
        return str(int(float(value)))
    except (ValueError, TypeError):
        return ""


def safe_num_str(value):
    if not value:
        return ""
    try:
        val = float(value)
        if val == int(val):
            return str(int(val))
        return str(val)
    except (ValueError, TypeError):
        return ""


def run_validation(tasks, config):
    """Run validation internally. Returns True if passed, False if failed."""
    has_errors = False
    for task in tasks:
        task_errors, _ = validator.validate_task(task)
        if task_errors:
            has_errors = True

    calendar_errors, _ = validator.validate_effort_per_week(tasks, config)
    if calendar_errors:
        has_errors = True

    return not has_errors


def build_row(task, config, week_context):
    """Build a single C2CRow from a task."""
    dk = task.get("descriptionKeys", {})
    category = task.get("category", "")
    mapping = TYPE_MAP.get(category)
    if not mapping:
        return None

    softtek_username = config["softtek_username"]
    start_date = week_context["expected_start_date"]
    finish_date = week_context["expected_finish_date"]
    working_days = str(week_context["working_days"])

    req_type, req_subtype = mapping
    is_design = req_type == "Test Design"
    is_design_with_peer = is_design and req_subtype in PEER_REVIEW_SUBTYPES
    is_execution = req_type == "Test Execution & Reporting"

    effort = safe_num_str(dk.get("Effort", ""))
    peer_effort = (
        safe_num_str(dk.get("Peer Review Scheduled Effort", ""))
        if is_design_with_peer
        else ""
    )

    tc_pass = safe_int_str(dk.get("TC Pass", "")) if is_execution else ""
    tc_fail = safe_int_str(dk.get("TC Fail", "")) if is_execution else ""
    tc_blocked = safe_int_str(dk.get("TC Blocked", "")) if is_execution else ""
    total = ""
    if is_execution and tc_pass:
        total = str(safe_int(tc_pass) + safe_int(tc_fail) + safe_int(tc_blocked))

    return {
        "taskId": task.get("id", ""),
        "projectId": "1-0000029582-3",
        "createdBy": softtek_username,
        "requestNo": "",
        "assignTo": softtek_username,
        "peerReviewer": softtek_username if is_design_with_peer else "",
        "shortDescription": task.get("shortDescription", ""),
        "requirementType": req_type,
        "requirementSubtype": req_subtype,
        "moduleFeature": task.get("module", ""),
        "team": task.get("team", ""),
        "numberOfDefectiveProducts": "",
        "numberOfProducts": (
            safe_int_str(dk.get("Products", "")) if not is_execution else ""
        ),
        "totalOfTestCases": "",
        "total": total,
        "pass": tc_pass,
        "fail": tc_fail,
        "cantTest": tc_blocked,
        "qtyBugsClosed": (
            safe_int_str(dk.get("Qty Bugs Closed", "")) if is_execution else ""
        ),
        "qtyBugsReopened": (
            safe_int_str(dk.get("Qty Bugs Re-opened", "")) if is_execution else ""
        ),
        "qtyBugsVerified": (
            safe_int_str(dk.get("Qty Bugs Verified", "")) if is_execution else ""
        ),
        "qtyNewBugsFound": (
            safe_int_str(dk.get("Qty New Bugs Found", "")) if is_execution else ""
        ),
        "releaseBuild": "Minor",
        "completePercent": "100",
        "defectsAdviceFlag": "",
        "peerReviewChecklistReviewed1": "",
        "peerReviewChecklistTemplate": "",
        "peerReviewChecklistReviewed2": "",
        "scheduledStartDate": start_date,
        "scheduledFinishDate": finish_date,
        "scheduledDuration": working_days,
        "scheduledEffort": effort,
        "peerReviewScheduledEffort": peer_effort,
        "scheduledReworkEffort": "",
        "scheduledUATReworkEffort": "",
        "actualStartDate": start_date,
        "actualFinishDate": finish_date,
        "actualDuration": working_days,
        "actualEffort": effort,
        "peerReviewActualEffort": peer_effort,
        "actualReworkEffort": "",
        "actualUATReworkEffort": "",
        "closedOn": "",
        "forClosing": "Closed",
        "action": dk.get("Action", "NA").strip() or "NA",
        "peerReviewChecklist": PEER_REVIEW_CHECKLIST_LINK if is_design else "",
        "estimationLink": ESTIMATION_LINKS.get(req_type, ""),
    }


def main():
    config = load_config()
    tasks = json.loads(sys.stdin.read())

    if not tasks:
        print("{}")
        return

    # Internal validation gate
    if not run_validation(tasks, config):
        print("Error: Validation failed. Cannot build rows.", file=sys.stderr)
        sys.exit(1)

    # Group tasks by [Week]
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

    # Build rows grouped by week tab name
    softtek_pto_name = config["softtek_pto_name"]
    output = {}  # {tab_name: [rows]}

    for week_num in sorted(tasks_by_week):
        monday = validator.iso_week_to_monday(week_num)
        week_context = pto_reader.get_week_context(softtek_pto_name, monday)
        tab_name = get_week_tab_name(week_num)

        rows = []
        for task in tasks_by_week[week_num]:
            row = build_row(task, config, week_context)
            if row:
                rows.append(row)

        if rows:
            output[tab_name] = rows

    print(json.dumps(output))


if __name__ == "__main__":
    main()
