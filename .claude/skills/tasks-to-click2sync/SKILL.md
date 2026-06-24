---
name: task-to-click2sync
description: Reads QA tasks from Meta's task system, validates them against Click2Sync rules and writes them to Google Sheets as weekly tabs. Use when user says 'genera mi C2C', 'C2C report', 'valida mis tareas', 'validate tasks'.
---

# Generate Click2Sync Rows

## IMPORTANT
ALWAYS use `/usr/bin/python3` to run scripts. NEVER use `python` or `python3` without the full path.

## Instructions

### Step 1: Config
If `config.json` does not exist, ask the user and save:
```json
{
  "person_tag": "FirstnameLastname-QA",
  "person_tag_fbid": "1234567890123456",
  "softtek_pto_name": "Firstname Lastname",
  "softtek_username": "flastname",
  "meta_username": "lastnamefirstname"
}
```

### Step 2: Read and Validate
```bash
/usr/bin/python3 scripts/read-tasks.py | /usr/bin/python3 scripts/validate-tasks.py
```
If errors, stop. Show output only.

### Step 3: Write Report (only if Step 2 passes with 0 errors)
```bash
/usr/bin/python3 scripts/read-tasks.py | /usr/bin/python3 scripts/row-builder.py | /usr/bin/python3 scripts/sheets-writer.py
```

## Output rules

Show ONLY script stdout. Do NOT add anything after it.

## Error: Auth expired

If any script fails with "OAuth" or "401" or "auth" errors, tell the user:

1. Go to https://www.internalfb.com/intern/jf/authenticate/
2. Find "Legacy Options" section
3. Copy the UID and NONCE values
4. Run: `jf auth --skip-legacy-auth-upgrade <UID> <NONCE>`
5. Then re-run the skill
