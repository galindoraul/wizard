#!/usr/bin/env python3
"""Read tasks and output JSON to stdout.
WEEKS_LOOKBACK controls how many previous weeks to include:
  0 = current week only
  1 = current + 1 previous
  3 = current + 3 previous
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import quote

SKILLS_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
CONFIG_PATH = os.path.join(SKILLS_DIR, "config.json")

# ──────────────────────────────────────────────────────────────────────────────
# WEEKS_LOOKBACK: How many previous weeks to include.
#   0 = current week only
#   1 = current + 1 previous
#   3 = current + 3 previous
# Change this value and push to enable multi-week processing for everyone.
# ──────────────────────────────────────────────────────────────────────────────
WEEKS_LOOKBACK = 1

TEAM_TAG = {"title": "SOFTTEK-PQX-QA", "fbid": "1512046989630466"}
EXCLUDE_TAGS = [
    {"title": "permission request", "fbid": "410788758967895"},
    {"title": "permission requests", "fbid": "630189192353771"},
    {"title": "permission-request", "fbid": "1141017623024532"},
    {"title": "Device Inventory", "fbid": "772502848173513"},
    {"title": "QA-TestRequest", "fbid": "820959891576025"},
    {"title": "QA-testplan", "fbid": "1641304926087302"},
    {"title": "PQX-Automation-Audit", "fbid": "200033036281922"},
    {"title": "PQX-TestCase-Audit", "fbid": "784864703348981"},
    {"title": "bug", "fbid": "483076488425894"},
    {"title": "Bugs", "fbid": "12706673982"},
    {"title": "need clarification", "fbid": "1978360869066800"},
]

# Only these keys are recognized from task descriptions.
KNOWN_DESCRIPTION_KEYS = {
    "Type",
    "Week",
    "Effort",
    "Products",
    "Action",
    "TC Pass",
    "TC Fail",
    "TC Blocked",
    "Qty Bugs Closed",
    "Qty Bugs Re-opened",
    "Qty Bugs Verified",
    "Qty New Bugs Found",
    "Peer Review Scheduled Effort",
}

MAX_RETRIES = 3
RETRY_DELAY = 3  # seconds


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("Error: config.json not found.", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_current_iso_week():
    """Return current ISO week number."""
    return datetime.now().isocalendar()[1]


def get_search_timestamps():
    """Get search window based on WEEKS_LOOKBACK."""
    today = datetime.now()
    lookback_days = (WEEKS_LOOKBACK + 1) * 7 + 7  # extra buffer for tasks created early
    start = (today - timedelta(days=lookback_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = today + timedelta(days=7, hours=23, minutes=59, seconds=59)
    return int(start.timestamp()), int(end.timestamp())


def build_url(ts_start, ts_end, config):
    query = {
        "key": "AND",
        "children": [
            {
                "key": "AFTER_ABSOLUTE_DATE",
                "field": "TASK_TIME_CREATED",
                "value": ts_start,
            },
            {
                "key": "BEFORE_ABSOLUTE_DATE",
                "field": "TASK_TIME_CREATED",
                "value": ts_end,
            },
            {"key": "CONTAINS_ALL_OF_FBIDS", "field": "TASK_TAGS", "value": [TEAM_TAG]},
            {
                "key": "CONTAINS_ANY_OF_FBIDS",
                "field": "TASK_TAGS",
                "value": [
                    {"title": config["person_tag"], "fbid": config["person_tag_fbid"]}
                ],
            },
            {
                "key": "CONTAINS_NONE_OF_FBIDS",
                "field": "TASK_TAGS",
                "value": EXCLUDE_TAGS,
            },
        ],
    }
    return f"https://www.internalfb.com/tasks/search?q={quote(json.dumps(query))}"


def parse_title(title):
    """Parse title format: [STK]_[Team]_[Module]_[Activity]: Description"""
    match = re.match(r"^\[STK\]_\[([^\]]+)\]_\[([^\]]+)\]_\[([^\]]+)\]:\s*(.+)$", title)
    if not match:
        return {"module": "", "team": "", "activity": "", "shortDescription": title}
    return {
        "team": match.group(1).strip(),
        "module": match.group(2).strip(),
        "activity": match.group(3).strip(),
        "shortDescription": match.group(4).strip(),
    }


def parse_description_keys(description):
    """Parse [Key] : Value pairs from task description.
    Only returns KNOWN keys. Unknown keys are silently ignored.
    """
    keys = {}
    clean = re.sub(r"[*_~]+", "", description)
    clean = re.sub(r"[ \t]+", " ", clean)

    for line in clean.split("\n"):
        line = line.strip()
        match = re.match(r"^[-\u2022*]?\s*\[([^\]]+)\]\s*:\s*(.*)", line)
        if not match:
            continue
        key = match.group(1).strip()
        if key == key.upper() and len(key) > 2:
            continue
        if key not in KNOWN_DESCRIPTION_KEYS:
            continue
        raw = match.group(2).strip()
        non_ascii = re.search(r"[^\x00-\x7F]", raw)
        value = (raw[: non_ascii.start()] if non_ascii else raw).strip()
        if value:
            keys[key] = value
    return keys


def guess_week_from_creation(task_raw):
    """Guess ISO week from task creation date (for filtering fallback)."""
    created = (
        task_raw.get("created")
        or task_raw.get("time_created")
        or task_raw.get("dateCreated")
    )
    if created:
        try:
            return datetime.fromtimestamp(int(created)).isocalendar()[1]
        except (ValueError, TypeError, OSError):
            pass
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(str(created), fmt).isocalendar()[1]
            except ValueError:
                continue
    return datetime.now().isocalendar()[1]


def fetch_tasks(url):
    """Fetch tasks from meta CLI with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        result = subprocess.run(
            [
                "meta",
                "tasks.task",
                "list",
                f"--fburl={url}",
                "--columns=number,title,description,created",
                "-l",
                "100",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            if attempt < MAX_RETRIES:
                print(
                    f"Retry {attempt}/{MAX_RETRIES}: meta CLI error, waiting {RETRY_DELAY}s...",
                    file=sys.stderr,
                )
                time.sleep(RETRY_DELAY)
                continue
            print(
                f"Error querying tasks after {MAX_RETRIES} attempts: {result.stderr}",
                file=sys.stderr,
            )
            sys.exit(1)

        stdout_lines = result.stdout.strip().split("\n")
        json_start = next(
            (i for i, line in enumerate(stdout_lines) if line.strip().startswith("[")),
            None,
        )
        if json_start is None:
            if attempt < MAX_RETRIES:
                print(
                    f"Retry {attempt}/{MAX_RETRIES}: No JSON in output, waiting {RETRY_DELAY}s...",
                    file=sys.stderr,
                )
                time.sleep(RETRY_DELAY)
                continue
            print("Error: No JSON output from meta CLI.", file=sys.stderr)
            sys.exit(1)

        json_str = "\n".join(stdout_lines[json_start:])
        tasks_raw = json.loads(json_str)

        if not tasks_raw and attempt < MAX_RETRIES:
            print(
                f"Retry {attempt}/{MAX_RETRIES}: 0 tasks returned, waiting {RETRY_DELAY}s...",
                file=sys.stderr,
            )
            time.sleep(RETRY_DELAY)
            continue

        return tasks_raw

    return []


def main():
    config = load_config()
    ts_start, ts_end = get_search_timestamps()
    url = build_url(ts_start, ts_end, config)

    tasks_raw = fetch_tasks(url)

    if not tasks_raw:
        print("[]")
        return

    current_week = get_current_iso_week()
    valid_weeks = set(range(current_week - WEEKS_LOOKBACK, current_week + 1))

    output = []
    for task in tasks_raw:
        title_parsed = parse_title(task.get("title", ""))
        desc_keys = parse_description_keys(task.get("description", ""))
        category = desc_keys.get("Type", "")
        created_week = guess_week_from_creation(task)

        # Filter by valid weeks
        week_str = desc_keys.get("Week", "").strip()
        try:
            task_week = int(week_str)
        except (ValueError, TypeError):
            task_week = None

        if task_week is not None and task_week not in valid_weeks:
            # Task explicitly tagged for a week outside our range — skip
            continue
        if task_week is None and created_week not in valid_weeks:
            # Task has no [Week] and was created outside our range — skip
            continue

        output.append(
            {
                "id": task["number"],
                "module": title_parsed["module"],
                "team": title_parsed["team"],
                "category": category,
                "shortDescription": title_parsed["shortDescription"],
                "descriptionKeys": desc_keys,
                "createdWeek": created_week,
            }
        )

    print(json.dumps(output))


if __name__ == "__main__":
    main()
