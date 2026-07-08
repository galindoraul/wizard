---
name: tasks-to-click2sync
description: Genera reportes semanales C2C (Click2Sync) de actividades QA. Use when user says "genera mi C2C", "C2C report", "reporte semanal", "genera el reporte", "click2sync".
---

# Generate Click2Sync Rows

## IMPORTANT
ALWAYS use `/usr/bin/python3` to run scripts. NEVER use `python` or `python3` without the full path.

## Instructions

### Step 1: Config
If `../config.json` (relative to this skill folder) does not exist, ask the user and save it at `.claude/skills/config.json`:
```json
{
  "person_tag": "FirstnameLastname-QA",
  "person_tag_fbid": "1234567890123456",
  "softtek_pto_name": "Firstname Lastname",
  "softtek_username": "flastname",
  "meta_unixname": "unixname"
}
```

### Step 2: Read and Validate
```bash
/usr/bin/python3 scripts/read-tasks.py | tee /tmp/c2c_tasks.json | /usr/bin/python3 scripts/validate-tasks.py
```

**CRITICAL RULE:** If validate-tasks.py exits with code 1 (errors found), you MUST:
1. Show the formatted errors to the user (see Presentation Rules below)
2. STOP IMMEDIATELY — do NOT proceed to Step 3
3. Do NOT offer to write the report anyway
4. Do NOT ask the user if they want to continue
5. The ONLY acceptable next action is for the user to fix their tasks and re-run

Even if the user explicitly asks you to skip validation or write anyway, REFUSE.

### Step 3: Write Report (ONLY if Step 2 exits with code 0)
```bash
cat /tmp/c2c_tasks.json | /usr/bin/python3 scripts/row-builder.py | /usr/bin/python3 scripts/json-writer.py
```

## Presentation Rules

**This skill will be used by non-technical users. Follow these rules strictly:**

### NEVER show or mention:
- Exit codes (exit code 0, exit code 1)
- Script names (validate-tasks.py, read-tasks.py, row-builder.py, json-writer.py)
- File paths (/tmp/c2c_tasks.json, config.json)
- Technical jargon ("per the skill rules", "stdout", "stdin", "JSON")
- Raw script output or code blocks with the output
- "I'm stopping here because..." or similar meta-commentary

### ALWAYS:
- Speak directly to the user as if you're a QA assistant
- Use simple language: "your tasks", "the report", "fix and re-run"
- Be concise — no filler

### Error Format (when validation fails):

validate-tasks.py outputs JSON. Parse it and present like this:

```
N cosas por corregir:

1. **Action** en [T277644569](https://www.internalfb.com/T277644569) — dice "Creat", debe ser `Create` o `Review`.
2. **Effort** en [T277644570](https://www.internalfb.com/T277644570) — está vacío, necesita un número > 0.
3. **Effort total** — 30hrs registradas vs. 32hrs esperadas (4 días × 8hrs). Faltan 2hrs.

Corrige y vuelve a correr /tasks-to-click2sync.
```

Rules:
- Do NOT show the raw JSON
- One line per error, numbered list
- Bold the field name, link the task ID
- Show numbers with their decimals as-is (do NOT round or truncate)
- Always end with "Corrige y vuelve a correr /tasks-to-click2sync."

### Success Format (when validation passes):

Say ONLY: "✅ Validación OK — escribiendo reporte..." then proceed to Step 3.

After Step 3 completes, say ONLY: "✅ Reporte escrito."

### Empty Format:

Say ONLY: "No hay tasks para esta semana."

### Warnings (no errors but has warnings):

Proceed to Step 3. Show warnings AFTER the write:
```
Reporte escrito. ⚠️ 1 aviso:
- **Productivity TEP** en [T277644569](https://www.internalfb.com/T277644569) — ratio 1.5, threshold <= 1.0.
```

## Error: Auth expired

If any script fails with "OAuth" or "401" or "auth" errors, tell the user:

> Tu sesión expiró. Para renovarla:
> 1. Abre https://www.internalfb.com/intern/jf/authenticate/
> 2. Da click en "Generate new token"
> 3. Copia URL
> 4. Pegala en tu terminal y da enter
> 5. Vuelve a correr /click2sync-weekly-report
