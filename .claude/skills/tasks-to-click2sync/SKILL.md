---
name: tasks-to-click2sync
description: Genera reporte semanal C2C (Click2Sync) desde tasks de Workplace. Triggers: "C2C", "click2sync", "reporte semanal", "genera mi reporte", "weekly report".
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
/usr/bin/python3 scripts/row-builder.py < /tmp/c2c_tasks.json | /usr/bin/python3 scripts/json-writer.py
```

Note: row-builder.py has an internal validation gate. Even if Step 2 is somehow bypassed, row-builder.py will refuse to produce output if validation fails.

## Presentation Rules

**This skill will be used by non-technical users. Follow these rules strictly:**

### NEVER show or mention:
- Exit codes (exit code 0, exit code 1)
- Script names (validate-tasks.py, read-tasks.py, row-builder.py, json-writer.py)
- File paths (/tmp/c2c_tasks.json, config.json)
- Technical jargon ("per the skill rules", "stdout", "stdin", "JSON", "ISO week")
- Raw script output or code blocks with the output
- "I'm stopping here because..." or similar meta-commentary

### ALWAYS:
- Speak directly to the user as if you're a QA assistant
- Use simple language: "your tasks", "the report", "fix and re-run"
- Be concise — no filler

### Error Format (when validation fails):

validate-tasks.py outputs JSON. Parse it and present **grouped by week**:

```
N cosas por corregir:

📅 Semana 27 (Jun 30 - Jul 4):
1. **Week** en [T276903396](https://www.internalfb.com/T276903396) — falta [Week].

📅 Semana 28 (Jul 7 - Jul 11):
2. **Effort total** — 71hrs registradas vs. 40hrs esperadas (5 días × 8hrs). Sobran 31hrs.
   → T277644569 (32hrs) ⚠️ posible [Week] incorrecto
   → T278660575 (8hrs)
   → T278660598 (8hrs)
   → T278660623 (8hrs)
   → T278660641 (8hrs)
   → T278660658 (7hrs)

⛔ Todas las semanas deben estar corregidas para generar el reporte.
Corrige y vuelve a correr /tasks-to-click2sync.
```

Rules:
- Use the `weekLabels` from JSON for the 📅 headers
- Sort weeks ascending
- Do NOT show the raw JSON
- One line per error, numbered list (continuous numbering across weeks)
- Bold the field name, link the task ID
- Show numbers with their decimals as-is (do NOT round or truncate)
- **MANDATORY for Effort total errors:** List tasks ONE PER LINE, indented with "→". Format: `→ T123 (8hrs)`. Read from `calendarErrors[].tasks[]`. If a task has `"suspicious": true`, append ` ⚠️ posible [Week] incorrecto` to that line. NEVER omit task lines.
- Always end with "⛔ Todas las semanas deben estar corregidas para generar el reporte.\nCorrige y vuelve a correr /tasks-to-click2sync."

### Success Format (when validation passes):

Say ONLY: "✅ Validación OK — escribiendo reporte..." then proceed to Step 3.

After Step 3 completes, say ONLY: "✅ Reporte escrito (N semanas)." where N is the number of weeks written.

### Empty Format:

Say ONLY: "No hay tasks en las últimas semanas."

### Warnings (no errors but has warnings):

Proceed to Step 3. Show warnings AFTER the write:
```
Reporte escrito (2 semanas). ⚠️ 1 aviso:
- **Productivity TEP** en [T277644569](https://www.internalfb.com/T277644569) — ratio 1.5, threshold <= 1.0.
```

## Error: Auth expired

If any script fails with "OAuth" or "401" or "auth" errors, tell the user:

> Tu sesión expiró. Para renovarla:
> 1. Abre https://www.internalfb.com/intern/jf/authenticate/
> 2. Da click en "Generate new token"
> 3. Copia URL
> 4. Pégala en tu terminal y da enter
> 5. Vuelve a correr /tasks-to-click2sync
