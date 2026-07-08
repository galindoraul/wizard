#!/usr/bin/env python3
"""Writes C2CRow data as JSON to the Shared Drive.
Each person has their own file: Click2Sync/{Name}.json
Each week is stored as a key in the JSON. No concurrency conflicts."""

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

SCRIPTS_DIR = os.path.dirname(os.path.realpath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
SKILLS_DIR = os.path.dirname(SKILL_DIR)
CONFIG_PATH = os.path.join(SKILLS_DIR, "config.json")


def get_week_tab_name():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return f"{monday.strftime('%b')} {monday.day}-{sunday.day}"


def get_json_path(config):
    """Get the personal JSON path: Click2Sync/{Name}.json"""
    cloud_storage = Path.home() / "Library" / "CloudStorage"
    gdrive_dirs = list(cloud_storage.glob("GoogleDrive-*@meta.com"))
    if not gdrive_dirs:
        print(
            "Error: Google Drive not found in ~/Library/CloudStorage/", file=sys.stderr
        )
        sys.exit(1)
    base = gdrive_dirs[0]
    c2c_folder = (
        base
        / "Shared drives"
        / "Meta - STK"
        / "Project Tracking"
        / "Automation"
        / "Automation Outputs"
        / "Click2Sync"
    )

    if not c2c_folder.exists():
        print(f"Error: Click2Sync folder not found: {c2c_folder}", file=sys.stderr)
        print(
            "Please navigate to this folder in Finder first to sync it.",
            file=sys.stderr,
        )
        sys.exit(1)

    person_name = config["softtek_pto_name"]
    return c2c_folder / f"{person_name}.json"


def main():
    if not os.path.exists(CONFIG_PATH):
        print("Error: config.json not found.", file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    rows = json.loads(sys.stdin.read())
    if not rows:
        print("No rows to write.")
        return

    json_path = get_json_path(config)
    tab_name = get_week_tab_name()
    person_name = config["softtek_pto_name"]
    username = config["softtek_username"]
    meta_unixname = config.get("meta_unixname", "")

    # Load existing data or create new
    if json_path.exists():
        with open(json_path, "r") as f:
            data = json.load(f)
        # Ensure meta_unixname is present (update old files)
        if "meta_unixname" not in data or not data["meta_unixname"]:
            data["meta_unixname"] = meta_unixname
    else:
        data = {
            "person": person_name,
            "username": username,
            "meta_unixname": meta_unixname,
            "weeks": {},
        }

    # Replace current week's rows (always overwrite with latest)
    data["weeks"][tab_name] = rows

    # Write to temp file first, then copy to Drive
    tmp_path = Path(tempfile.gettempdir()) / f"Click2Sync_{username}.json"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)

    # Copy to Shared Drive
    shutil.copy2(str(tmp_path), str(json_path))
    tmp_path.unlink(missing_ok=True)

    print(json.dumps({"status": "ok"}))


if __name__ == "__main__":
    main()
