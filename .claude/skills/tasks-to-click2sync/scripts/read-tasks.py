#!/usr/bin/env python3
"""Step 2: Lee tasks de la semana actual y genera output/tasks-raw.json"""

import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from urllib.parse import quote

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")
OUTPUT_DIR = os.path.join(SKILL_DIR, "output")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "tasks-raw.json")

TEAM_TAG = {"title": "SOFTTEK-PQX-QA", "fbid": "1512046989630466"}
EXCLUDE_TAGS = [
    {"title": "permission request", "fbid": "410788758967895"},
    {"title": "permission requests", "fbid": "630189192353771"},
    {"title": "permission-request", "fbid": "1141017623024532"},
    {"title": "Device Inventory", "fbid": "772502848173513"},
]


def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"config.json not found at {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_week_timestamps():
    today = datetime.now()
    monday = (today - timedelta(days=today.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
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
    match = re.match(r"^STK_\[([^\]]+)\]_\[([^\]]+)\]_([^:]+):\s*(.+)$", title)
    if not match:
        return {"module": "", "team": "", "category": "", "shortDescription": title}
    return {
        "module": match.group(1).strip(),
        "team": match.group(2).strip(),
        "category": match.group(3).strip(),
        "shortDescription": match.group(4).strip(),
    }


def parse_description_keys(description):
    keys = {}
    for match in re.finditer(r"\[([^\]]+)\]\s*:\s*([^\[]*)", description):
        key = match.group(1).strip()
        if key == key.upper():
            continue
        raw = match.group(2)
        non_ascii = re.search(r"[^\x00-\x7F]", raw)
        value = (raw[: non_ascii.start()] if non_ascii else raw).strip().strip("*").strip()
        if value:
            keys[key] = value
    return keys


def main():
    config = load_config()
    ts_start, ts_end = get_week_timestamps()
    url = build_url(ts_start, ts_end, config)

    result = subprocess.run(
        ["meta", "tasks.task", "list", f"--fburl={url}",
         "--columns=number,title,owner,description,progress,tags",
         "-l", "100", "-o", "json"],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        return

    # `meta` puede imprimir warnings (p.ej. de auth) en stdout antes del JSON.
    # Extraemos el array JSON desde el primer '[' hasta el último ']'.
    stdout = result.stdout
    start = stdout.find("[")
    end = stdout.rfind("]")
    if start == -1 or end == -1:
        print(f"❌ No se encontró JSON en la salida de `meta`:\n{stdout[:500]}")
        return
    tasks_raw = json.loads(stdout[start : end + 1])
    output = []

    for task in tasks_raw:
        title_parsed = parse_title(task.get("title", ""))
        desc_keys = parse_description_keys(task.get("description", ""))
        tags = [t.strip() for t in task.get("tags", "").split(",") if t.strip()]

        output.append({
            "id": task["number"],
            "module": title_parsed["module"],
            "team": title_parsed["team"],
            "category": title_parsed["category"],
            "shortDescription": title_parsed["shortDescription"],
            "status": task.get("progress", ""),
            "descriptionKeys": desc_keys,
            "tags": tags,
            "owner": task.get("owner", ""),
        })

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ {len(output)} tasks guardadas en output/tasks-raw.json")


if __name__ == "__main__":
    main()
