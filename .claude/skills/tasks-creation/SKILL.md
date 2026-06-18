---
name: create-tasks
description: Creates tasks in MetaMate's internal tasks tool from per-type templates. Uses fixed config (user-tag, team, subteam) and only asks for type and quantity. Shows the newly created tasks when done.
---

# create-tasks

Creates one or more tasks of the same type in MetaMate's `tasks` tool.

## Fixed data (config.json)

These are NOT asked on every run. They live in `config.json`:

- `user_tag` -> added as the task tag
- `team` -> goes in the title
- `subteam` -> goes in the title

If any field in `config.json` is empty, ask the user ONCE, write it to `config.json`, and never ask again.

## Templates

Each task type is a file in `assets/<type>.md` with three sections:

- `## Title` -> title format. Contains `{team}` and `{subteam}`.
- `## Tags` -> contains `{user_tag}`.
- `## Description` -> fixed content for the type (defined by the user in the template).

The placeholders `{team}`, `{subteam}`, `{user_tag}` are replaced with the values from `config.json`.

The task fields are always the same per type. The user fills in the rest after the task is created; the skill only creates the base structure.

## Flow

1. Read `config.json`. If any data is missing, ask for it once and save it.
2. List the available types (file names in `assets/`) and ask the user to choose one.
3. Ask how many tasks of that type to create (default 1).
4. Show a simple summary of what was requested: task type and quantity. Ask for explicit confirmation before creating. Do not show how the task will look.
5. After the OK, create the N tasks with MetaMate's `tasks` tool (same title, tag, and description for all).
6. Filter and show the user only the tasks created in this run.

## Rules

- Never ask for user_tag, team, or subteam if they are already in config.json.
- Always confirm before creating.
- Do not invent fields that are not in the template.
