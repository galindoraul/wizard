#!/usr/bin/env python3
"""Read tasks from the current week. Prints JSON to stdout for piping to validate.py."""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from urllib.parse import quote

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

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


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("Error: config.json not found.", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_week_timestamps():
    today = datetime.now()
    monday = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return int(monday.timestamp()), int(sunday.timestamp())


def build_url(ts_start, ts_end, config):
    query = {
        "key": "AND",
        "children": [
            {"key": "AFTER_ABSOLUTE_DATE", "field": "TASK_TIME_CREATED", "value": ts_start},
            {"key": "BEFORE_ABSOLUTE_DATE", "field": "TASK_TIME_CREATED", "value": ts_end},
            {"key": "CONTAINS_ALL_OF_FBIDS", "field": "TASK_TAGS", "value": [TEAM_TAG]},
            {"key": "CONTAINS_ANY_OF_FBIDS", "field": "TASK_TAGS", "value": [
                {"title": config["person_tag"], "fbid": config["person_tag_fbid"]}
            ]},
            {"key": "CONTAINS_NONE_OF_FBIDS", "field": "TASK_TAGS", "value": EXCLUDE_TAGS},
        ],
    }
    return f"https://www.internalfb.com/tasks/search?q={quote(json.dumps(query))}"


def parse_title(title):
    """Parse title format: [STK]_[Product]_[Team]_[Activity]: Description """
    match = re.match(r'^\[STK\]_\[([^\]]+)\]_\[([^\]]+)\]_\[([^\]]+)\]:\s*(.+)$', title)
    if not match:
        return {"module": "", "team": "", "activity": "", "shortDescription": title}
    return {
        "module": match.group(1).strip(),
        "team": match.group(2).strip(),
        "activity": match.group(3).strip(),
        "shortDescription": match.group(4).strip(),
    }


def parse_description_keys(description):
    """Parse [Key] : Value pairs from task description.
    Handles: bold, italic, underline, strikethrough, no spaces, text between keys.
    """
    keys = {}
    clean = re.sub(r'[*_~]+', '', description)
    clean = re.sub(r'[ \t]+', ' ', clean)

    for line in clean.split('\n'):
        line = line.strip()
        match = re.match(r'^[-•*]?\s*\[([^\]]+)\]\s*:\s*(.*)', line)
        if not match:
            continue
        key = match.group(1).strip()
        if key == key.upper() and len(key) > 2:
            continue
        raw = match.group(2).strip()
        non_ascii = re.search(r'[^\x00-\x7F]', raw)
        value = (raw[:non_ascii.start()] if non_ascii else raw).strip()
        if value:
            keys[key] = value
    return keys


def main():
    config = load_config()
    url = os.environ.get("TASKS_FBURL")
    if not url:
        ts_start, ts_end = get_week_timestamps()
        url = build_url(ts_start, ts_end, config)

    result = subprocess.run(
        ["meta", "tasks.task", "list", f"--fburl={url}",
         "--columns=number,title,owner,description,progress,tags",
         "-l", "100", "-o", "json"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Error querying tasks: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Filter out non-JSON lines (OAuth warnings, etc.)
    stdout_lines = result.stdout.strip().split('\n')
    json_start = next((i for i, line in enumerate(stdout_lines) if line.strip().startswith('[')), None)
    if json_start is None:
        print("Error: No JSON output from meta CLI.", file=sys.stderr)
        sys.exit(1)

    json_str = '\n'.join(stdout_lines[json_start:])
    tasks_raw = json.loads(json_str)

    if not tasks_raw:
        print("[]")
        return

    output = []
    for task in tasks_raw:
        title_parsed = parse_title(task.get("title", ""))
        desc_keys = parse_description_keys(task.get("description", ""))
        tags = [t.strip() for t in task.get("tags", "").split(",") if t.strip()]

        # Category (Type) comes from [Type] in description
        category = desc_keys.get("Type", "")

        output.append({
            "id": task["number"],
            "module": title_parsed["module"],
            "team": title_parsed["team"],
            "category": category,
            "shortDescription": title_parsed["shortDescription"],
            "status": task.get("progress", ""),
            "descriptionKeys": desc_keys,
            "tags": tags,
            "owner": task.get("owner", ""),
        })

    print(json.dumps(output))


if __name__ == "__main__":
    main()
