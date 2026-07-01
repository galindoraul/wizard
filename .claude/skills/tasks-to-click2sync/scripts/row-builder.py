#!/usr/bin/env python3
"""Builds C2CRow objects from tasks + PTO context. Reads tasks from stdin, outputs rows as JSON."""

import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
pto_reader = import_module("pto-reader")

TYPE_MAP = {
    "Test Plan": ("Test Planning", "Test Plan"),
    "Test Strategy": ("Test Planning", "Test Strategy"),
    "Business Requirements": ("Test Analysis", "Business Requirements"),
    "Functional Requirements": ("Test Analysis", "Functional Requirements"),
    "Knowledge Transfer": ("Test Analysis", "Knowledge Transfer"),
    "Test Case": ("Test Design", "Test Case"),
    "Test Data": ("Test Design", "Test Data"),
    "Set Up & Configure Test Environment": ("Test Implementation", "Set Up & Configure Test Environment"),
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

# ─── Fields that MUST be integers (keep in sync with validate-tasks.py) ───
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

# ─── Fields that allow decimals ───
DECIMAL_FIELDS = [
    "Effort",
    "Peer Review Scheduled Effort",
]


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def safe_int(value, default=0):
    """Parse as integer. Handles '2.0' -> 2."""
    try:
        return int(float(value)) if value else default
    except (ValueError, TypeError):
        return default


def safe_int_str(value):
    """Parse as integer, return as string. Empty if no value."""
    if not value:
        return ""
    try:
        return str(int(float(value)))
    except (ValueError, TypeError):
        return ""


def safe_num_str(value):
    """Parse as number, return as clean string. Removes trailing .0 if integer."""
    if not value:
        return ""
    try:
        val = float(value)
        if val == int(val):
            return str(int(val))
        return str(val)
    except (ValueError, TypeError):
        return ""


def build_rows(tasks, config, week_context):
    rows = []
    softtek_username = config["softtek_username"]
    start_date = week_context["expected_start_date"]
    finish_date = week_context["expected_finish_date"]
    working_days = str(week_context["working_days"])

    for task in tasks:
        dk = task.get("descriptionKeys", {})
        category = task.get("category", "")
        mapping = TYPE_MAP.get(category)
        if not mapping:
            continue

        req_type, req_subtype = mapping
        is_design = req_type == "Test Design"
        is_design_with_peer = is_design and req_subtype in PEER_REVIEW_SUBTYPES
        is_execution = req_type == "Test Execution & Reporting"

        effort = safe_num_str(dk.get("Effort", ""))
        peer_effort = safe_num_str(dk.get("Peer Review Scheduled Effort", "")) if is_design_with_peer else ""

        tc_pass = safe_int_str(dk.get("TC Pass", "")) if is_execution else ""
        tc_fail = safe_int_str(dk.get("TC Fail", "")) if is_execution else ""
        tc_blocked = safe_int_str(dk.get("TC Blocked", "")) if is_execution else ""
        total = ""
        if is_execution and tc_pass:
            total = str(safe_int(tc_pass) + safe_int(tc_fail) + safe_int(tc_blocked))

        rows.append({
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
            "numberOfProducts": safe_int_str(dk.get("Products", "")) if not is_execution else "",
            "totalOfTestCases": "",
            "total": total,
            "pass": tc_pass,
            "fail": tc_fail,
            "cantTest": tc_blocked,
            "qtyBugsClosed": safe_int_str(dk.get("Qty Bugs Closed", "")) if is_execution else "",
            "qtyBugsReopened": safe_int_str(dk.get("Qty Bugs Re-opened", "")) if is_execution else "",
            "qtyBugsVerified": safe_int_str(dk.get("Qty Bugs Verified", "")) if is_execution else "",
            "qtyNewBugsFound": safe_int_str(dk.get("Qty New Bugs Found", "")) if is_execution else "",
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
        })

    return rows


def main():
    config = load_config()
    tasks = json.loads(sys.stdin.read())

    if not tasks:
        print("[]")
        return

    week_context = pto_reader.get_week_context(config["softtek_pto_name"])
    rows = build_rows(tasks, config, week_context)
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
