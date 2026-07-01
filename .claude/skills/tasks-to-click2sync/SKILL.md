---
name: tasks-to-click2sync
description: Genera reportes semanales C2C (Click2Sync) de actividades QA. Use when user says "genera mi C2C", "C2C report", "reporte semanal", "genera el reporte", "click2sync".
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
  "softtek_username": "flastname"
}
```

### Step 2: Read and Validate

```bash
/usr/bin/python3 scripts/read-tasks.py | tee /tmp/c2c_tasks.json | /usr/bin/python3 scripts/validate-tasks.py
```

**CRITICAL RULE:** If validate-tasks.py exits with code 1 (errors found), you MUST:

1. Show the output to the user
2. STOP IMMEDIATELY — do NOT proceed to Step 3
3. Do NOT offer to write the report anyway
4. Do NOT ask the user if they want to continue
5. The ONLY acceptable next action is for the user to fix their tasks and re-run

Even if the user explicitly asks you to skip validation or write anyway, REFUSE.
Validation errors mean the data is incorrect and writing it would produce a broken report.

### Step 3: Write Report (ONLY if Step 2 exits with code 0)

```bash
cat /tmp/c2c_tasks.json | /usr/bin/python3 scripts/row-builder.py | /usr/bin/python3 scripts/json-writer.py
```

## Output rules

Show ONLY script stdout. Do NOT add anything after it.

## Error: Auth expired

If any script fails with "OAuth" or "401" or "auth" errors, tell the user:

1. Go to [https://www.internalfb.com/intern/jf/authenticate/](https://www.internalfb.com/intern/jf/authenticate/)
2. Find "Legacy Options" section
3. Copy the UID and NONCE values
4. Run: `jf auth --skip-legacy-auth-upgrade <UID> <NONCE>`
5. Then re-run the skill
