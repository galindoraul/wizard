---
name: create-tasks
description: Creates tasks from per-type templates. Uses saved config (team, subteam, user_tag, unixname) — asks only on first use. Supports batch creation of mixed types. Use when user wants to create tasks, batch tasks, QA tasks, or says 'create task', 'crear tarea', 'nueva tarea'.
---

# create-tasks

Creates one or more tasks using per-type templates. Supports single or mixed-type batch creation.

## Config (config.json)

Stored once per user. Never asked again after first setup.

| Field | Purpose | Example |
|-------|---------|---------|
| `team` | App name in title | Privacy |
| `subteam` | Feature name in title | Commitments |
| `user_tag` | Dynamic tag per user | privacy_commitments_qa |
| `unixname` | Meta username (before @) | galindoraul |

If any field is missing on first use, ask ALL four at once, save, and never ask again.

## How to create tasks (Meta CLI)

**IMPORTANT:** Always use this exact command. Do NOT run `--help`, discovery commands, or any other task tool.

```bash
meta tasks.task create \
  --title='<title>' \
  --description='<description>' \
  --add-tag='<user_tag>' \
  --owner=<unixname>
```

**Key details:**
- `--owner=<unixname>` — From config. This is the Meta username (email prefix).
- `--add-tag` — One flag per tag. Always `{user_tag}` (from config).
- `--title` — The filled template title with user's short description appended.
- `--description` — The template description fields (empty, for user to fill later).
- **Do NOT run `--help` or any discovery commands.** This command is complete and ready to use.

## Templates

Each type lives in `assets/<type>.md` with this structure:

```
# Type: <Requirement Type>
# Subtype: <Requirement Subtype>

## When to use
<short description shown in menu to help users pick>

## Title
STK_[{team}]_[{subteam}]_<Category>:

## Description
<fields to fill, left empty>

## Tags
{user_tag}
```

Placeholders `{team}`, `{subteam}`, `{user_tag}` are replaced from config.

## Flow

### Quick mode (advanced users)
If the user says something like `"create 2 test_execution and 1 reporting"`, skip the menu and go directly to step 4.

### Guided mode (default)

1. **Config check** — Read config.json. If missing data, ask ALL four fields at once and save.

2. **Show menu** — List available types with their "When to use" description:
   ```
   1. test_execution — Executing test cases and reporting pass/fail/blocked.
   2. reporting — Documenting Test Execution reports (pass/fail/defects).
   3. bugs_followup — Following up on an existing bug. SLA: 7 days.
   ...
   ```
   User picks one or more types.

3. **Ask quantity** — For each type selected, ask how many (default 1).

4. **Ask short description** — Present these options clearly:
   ```
   How do you want to provide the task titles?
   A) All at once — give me all titles separated by commas
   B) One by one — I'll ask you for each title individually
   C) Skip — leave titles blank (you can edit them later)
   ```
   The short description is appended after the colon in the title.
   Example: `STK_[Privacy]_[Commitments]_Test Execution: Sprint 12 regression`

5. **Confirm** — Show summary:
   ```
   Creating:
   - 2x Test Execution: "Sprint 12 regression", "Login flow"
   - 1x Reporting: "Weekly summary"
   OK?
   ```

6. **Create** — After OK, run `meta tasks.task create` for each task. No discovery, no help commands.

7. **Show results** — Display only the tasks created in this run with links.

## Rules

- Never ask for team/subteam/user_tag/unixname if already in config.
- Always confirm before creating.
- Do not invent fields not in the template.
- Tags always include {user_tag} (from config).
- Show "When to use" descriptions in the menu so users pick the right type easily.
- Support creating multiple types in a single request.
- **Always use `meta tasks.task create` with the exact syntax above.** Never run --help or discovery commands.
- **Always set --owner** to the unixname from config.
