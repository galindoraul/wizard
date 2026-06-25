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

PEER_REVIEW_SUBTYPES = ["Test Case", "Test Script"]
PEER_REVIEW_CHECKLIST_LINK = "https://onesofttek.sharepoint.com/:f:/r/sites/SKPmetap/qanstt/Shared%20Documents/Project%20Tracking/Quality%20Tools/Peer%20Reviews?csf=1&web=1&e=eRpH6D"
ESTIMATION_LINKS = {
    "Test Design": "https://onesofttek.sharepoint.com/:f:/r/sites/SKPmetap/qanstt/Shared%20Documents/Project%20Tracking/Quality%20Tools/Estimations?csf=1&web=1&e=MWJjR3",
    "Test Execution & Reporting": "https://onesofttek.sharepoint.com/:f:/r/sites/SKPmetap/qanstt/Shared%20Documents/Project%20Tracking/Quality%20Tools/Estimations?csf=1&web=1&e=MWJjR3",
}


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def safe_num(value, default=0):
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def build_rows(tasks, config, week_context, start_request_no):
    rows = []
    counter = start_request_no

    softtek_username = config["softtek_username"]
    start_date = week_context["expected_start_date"]
    finish_date = week_context["expected_finish_date"]
    working_days = str(week_context["working_days"])

    for task in tasks:
        dk = task.get("descriptionKeys", {})
        category = task.get("category", "")
        mapping = CATEGORY_MAP.get(category)
        if not mapping:
            continue

        req_type, req_subtype = mapping
        is_design = req_type == "Test Design"
        is_design_with_peer = is_design and req_subtype in PEER_REVIEW_SUBTYPES
        is_execution = req_type == "Test Execution & Reporting"

        effort = dk.get("Effort", "")
        peer_effort = dk.get("Peer Review Scheduled Effort", "") if is_design_with_peer else ""
        net_effort = effort
        if effort and peer_effort:
            net_effort = str(int(safe_num(effort)) - int(safe_num(peer_effort)))

        tc_pass = dk.get("TC Pass", "") if is_execution else ""
        tc_fail = dk.get("TC Fail", "") if is_execution else ""
        tc_blocked = dk.get("TC Blocked", "") if is_execution else ""
        total = ""
        if is_execution and tc_pass:
            total = str(int(safe_num(tc_pass)) + int(safe_num(tc_fail)) + int(safe_num(tc_blocked)))

        # Short Description with task ID prefix: [TaskID] Description
        task_id = task.get("id", "")
        short_desc = task.get("shortDescription", "")
        if task_id:
            short_description = f"[{task_id}] {short_desc}"
        else:
            short_description = short_desc

        rows.append({
            "projectId": "1-0000029582-3",
            "createdBy": softtek_username,
            "requestNo": f"29582-3-{counter:05d}",
            "assignTo": softtek_username,
            "peerReviewer": softtek_username if is_design_with_peer else "",
            "shortDescription": short_description,
            "requirementType": req_type,
            "requirementSubtype": req_subtype,
            "moduleFeature": task.get("module", ""),
            "team": task.get("team", ""),
            "numberOfDefectiveProducts": "",
            "numberOfProducts": dk.get("Products", "") if not is_execution else "",
            "totalOfTestCases": "",
            "total": total,
            "pass": tc_pass,
            "fail": tc_fail,
            "cantTest": tc_blocked,
            "qtyBugsClosed": dk.get("Qty Bugs Closed", "") if is_execution else "",
            "qtyBugsReopened": dk.get("Qty Bugs Re-opened", "") if is_execution else "",
            "qtyBugsVerified": dk.get("Qty Bugs Verified", "") if is_execution else "",
            "qtyNewBugsFound": dk.get("Qty New Bugs Found", "") if is_execution else "",
            "releaseBuild": "Minor",
            "completePercent": "100",
            "defectsAdviceFlag": "",
            "peerReviewChecklistReviewed1": "",
            "peerReviewChecklistTemplate": "",
            "peerReviewChecklistReviewed2": "",
            "scheduledStartDate": start_date,
            "scheduledFinishDate": finish_date,
            "scheduledDuration": working_days,
            "scheduledEffort": net_effort,
            "peerReviewScheduledEffort": peer_effort,
            "scheduledReworkEffort": "",
            "scheduledUATReworkEffort": "",
            "actualStartDate": start_date,
            "actualFinishDate": finish_date,
            "actualDuration": working_days,
            "actualEffort": net_effort,
            "peerReviewActualEffort": peer_effort,
            "actualReworkEffort": "",
            "actualUATReworkEffort": "",
            "closedOn": "",
            "forClosing": "Closed",
            "action": dk.get("Action", "NA").strip() or "NA",
            "peerReviewChecklist": PEER_REVIEW_CHECKLIST_LINK if is_design else "",
            "estimationLink": ESTIMATION_LINKS.get(req_type, ""),
        })
        counter += 1

    return rows


def main():
    config = load_config()
    tasks = json.loads(sys.stdin.read())

    if not tasks:
        print("[]")
        return

    week_context = pto_reader.get_week_context(config["softtek_pto_name"])
    start_request_no = 10200  # placeholder, sheets-writer adjusts
    rows = build_rows(tasks, config, week_context, start_request_no)
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
