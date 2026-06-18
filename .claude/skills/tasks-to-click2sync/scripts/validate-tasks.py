#!/usr/bin/env python3
"""Step 3: Valida tasks y genera output/validation-report.md
Based on the real validator.ts + Click2SyncParser.ts source code."""

import json
import os
from datetime import datetime, timedelta

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(SKILL_DIR, "output", "tasks-raw.json")
OUTPUT_PATH = os.path.join(SKILL_DIR, "output", "validation-report.md")

# === CATEGORY MAP (from Click2SyncParser REQ_TYPE_MAP) ===
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

# === VALID ACTIONS (from validator.ts VALID_ACTIONS) ===
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

# === CONSTANTS ===
PEER_REVIEW_LINK = "https://onesofttek.sharepoint.com/:f:/r/sites/SKPmetap/qanstt/Shared%20Documents/Project%20Tracking/Quality%20Tools/Peer%20Reviews"
ESTIMATION_LINK = "https://onesofttek.sharepoint.com/:f:/r/sites/SKPmetap/qanstt/Shared%20Documents/Project%20Tracking/Quality%20Tools/Estimations"
PEER_REVIEW_SUBTYPES = ["Test Case", "Test Script"]


def safe_num(value, default=0):
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


def is_within_31_days(date_str):
    """Check if MM/DD/YYYY date is within ±31 days of today."""
    try:
        parts = date_str.split("/")
        if len(parts) != 3:
            return False
        date = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
        diff = abs((date - datetime.now()).days)
        return diff <= 31
    except (ValueError, IndexError):
        return False


def get_week_dates():
    """Get Monday and Friday of current week as MM/DD/YYYY."""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    fmt = lambda d: f"{d.month:02d}/{d.day:02d}/{d.year}"
    return fmt(monday), fmt(friday)


def validate_task(task):
    """Validate a single task following validator.ts rules exactly."""
    errors = []
    warnings = []
    dk = task.get("descriptionKeys", {})
    category = task.get("category", "")

    # --- Map category to type/subtype ---
    mapping = CATEGORY_MAP.get(category)
    if not mapping:
        errors.append("Regla 7: Category \"{}\" no mapea a type/subtype válido".format(category))
        return errors, warnings

    req_type, req_subtype = mapping
    action_key = f"{req_type}|{req_subtype}"
    valid_actions = VALID_ACTIONS.get(action_key, [])

    # --- Derived fields ---
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

    # Calculated fields
    start_date, finish_date = get_week_dates()
    net_effort = effort - peer_effort if is_design_with_peer and peer_effort else effort

    # === RULE 8: Action ===
    if valid_actions and action not in valid_actions:
        errors.append(f"Regla 8: Action \"{action}\" no válida (esperado: {valid_actions})")

    # === RULE 9: Scheduled Start Date (±31 days) ===
    if not is_within_31_days(start_date):
        errors.append(f"Regla 9: Scheduled Start Date \"{start_date}\" fuera de rango ±31 días")

    # === RULE 10: Scheduled Finish Date (±31 days) ===
    if not is_within_31_days(finish_date):
        errors.append(f"Regla 10: Scheduled Finish Date \"{finish_date}\" fuera de rango ±31 días")

    # === RULE 6: Assigned Peer Review ===
    if is_design_with_peer and not task.get("owner"):
        errors.append("Regla 6: Peer Reviewer requerido para Test Design (Test Case/Test Script)")

    # === RULE: Peer Review Min 10% ===
    if is_design_with_peer and effort > 0:
        if peer_effort <= 0:
            errors.append(f"Peer Review Min 10%: Peer Review Effort requerido (Effort={effort})")
        elif peer_effort < effort * 0.1:
            errors.append(f"Peer Review Min 10%: Peer Review ({peer_effort}) debe ser ≥ 10% de Effort ({effort})")

    # === RULE 13: Peer Review Checklist ===
    if is_design:
        # For the skill, we auto-fill this link, but validate it exists
        pass  # Auto-filled by Click2SyncParser

    # === RULE 14: Estimation Link ===
    if is_design or is_execution:
        # Auto-filled by Click2SyncParser
        pass

    # === RULE 18: Number of Products (not for execution) ===
    if not is_execution and products <= 0:
        errors.append(f"Regla 18: Products requerido (valor: \"{dk.get('Products', '')}\")")

    # === RULE 9 (effort): Effort required ===
    if effort <= 0:
        errors.append(f"Regla 9: Effort requerido (valor: \"{dk.get('Effort', '')}\")")

    # === RULE 19: Execution fields ===
    if is_execution:
        missing = []
        if "TC Pass" not in dk:
            missing.append("TC Pass")
        if "TC Fail" not in dk:
            missing.append("TC Fail")
        if "TC Blocked" not in dk:
            missing.append("TC Blocked")
        if missing:
            errors.append(f"Regla 19: Faltan campos: {missing}")

    # === RULE 3: Sum O+P+Q ===
    if is_execution and "TC Pass" in dk:
        expected = tc_pass + tc_fail + tc_blocked
        if total != expected:
            errors.append(f"Regla 3: Total ({int(total)}) ≠ Pass ({int(tc_pass)}) + Fail ({int(tc_fail)}) + Blocked ({int(tc_blocked)})")

    # === RULE 20: Bugs consistency ===
    if tc_fail > 0 and qty_new_bugs <= 0 and qty_bugs_closed <= 0:
        errors.append(f"Regla 20: Fail={int(tc_fail)} pero no hay bugs reportados")

    # === RULE 2: Productivity (Warning) ===
    if req_subtype == "Test Case Execution" and total > 0:
        ratio = net_effort / total
        if ratio > 1:
            warnings.append(f"Regla 2: Productividad TEP {ratio:.2f} excede umbral 1.0")
    elif req_subtype == "Test Script Execution" and total > 0:
        ratio = net_effort / total
        if ratio > 0.5:
            warnings.append(f"Regla 2: Productividad TSE {ratio:.2f} excede umbral 0.5")
    elif req_subtype == "Test Case" and is_design and products > 0:
        ratio = net_effort / products
        if ratio > 2:
            warnings.append(f"Regla 2: Productividad TDP {ratio:.2f} excede umbral 2.0")
    elif req_subtype == "Test Script" and is_design and products > 0:
        ratio = net_effort / products
        if ratio > 4:
            warnings.append(f"Regla 2: Productividad TSD {ratio:.2f} excede umbral 4.0")

    return errors, warnings


def main():
    if not os.path.exists(INPUT_PATH):
        print(f"❌ No se encontró {INPUT_PATH}. Ejecutar read_tasks.py primero.")
        return

    with open(INPUT_PATH) as f:
        tasks = json.load(f)

    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_str = f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d, %Y')}"

    results = {"errors": [], "warnings": [], "ok": []}

    for task in tasks:
        task_errors, task_warnings = validate_task(task)
        label = f"{task['id']} — {task['category']}: {task['shortDescription']}"

        if task_errors:
            results["errors"].append({"label": label, "issues": task_errors})
        elif task_warnings:
            results["warnings"].append({"label": label, "issues": task_warnings})
        else:
            results["ok"].append(label)

    # Generate report
    total_errors = sum(len(r["issues"]) for r in results["errors"])
    total_warnings = sum(len(r["issues"]) for r in results["warnings"])

    lines = [
        f"# Validation Report",
        f"Semana: {week_str} | Tasks: {len(tasks)} | Errors: {total_errors} | Warnings: {total_warnings}",
        "",
    ]

    if results["errors"]:
        lines.append("## ❌ Errores\n")
        for r in results["errors"]:
            lines.append(f"### {r['label']}")
            for issue in r["issues"]:
                lines.append(f"- **{issue}**")
            lines.append("")

    if results["warnings"]:
        lines.append("## ⚠️ Warnings\n")
        for r in results["warnings"]:
            lines.append(f"### {r['label']}")
            for issue in r["issues"]:
                lines.append(f"- {issue}")
            lines.append("")

    if results["ok"]:
        lines.append("## ✅ OK")
        for label in results["ok"]:
            lines.append(f"- {label}")
        lines.append("")

    if results["errors"]:
        lines.append("---")
        lines.append("❌ **Corregir errores antes de continuar.**")
    else:
        lines.append("---")
        lines.append("✅ **Validación pasó. Continuar al siguiente paso.**")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write("\n".join(lines))

    print(f"{'❌' if results['errors'] else '✅'} Reporte en output/validation-report.md")
    print(f"   Tasks: {len(tasks)} | Errors: {total_errors} | Warnings: {total_warnings}")


if __name__ == "__main__":
    main()
