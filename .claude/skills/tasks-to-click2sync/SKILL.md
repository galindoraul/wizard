---
name: generate-click2sync-rows
description: Genera reportes semanales C2C (Click2Sync) de actividades QA. Use when user says "genera mi C2C", "C2C report", "reporte semanal", "genera el reporte", "click2sync".
---

# Generate Click2Sync Rows

## Instructions

### Step 1: Config
If `config.json` does not exist in this skill folder, ask the user:
- `person_tag`: Their personal QA tag (format: FirstnameLastname-QA)
- `person_tag_fbid`: The FBID of that tag

Save to `config.json` in this skill folder.

### Step 2: Run
```bash
python scripts/read_tasks.py | python scripts/validate.py
```

## Output rules

After running the command, show ONLY its stdout. Do NOT add anything after it. No summary, no bullet points, no extra explanation. Your response is ONLY the script output. Zero additional words.
