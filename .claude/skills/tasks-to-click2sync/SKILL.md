---
## name: generate-click2sync-rows
description: Genera reportes semanales C2C (Click2Sync) de actividades QA. Use when user says "genera mi C2C", "C2C report", "reporte semanal", "genera el reporte", "click2sync".
---

# Generate Click2Sync Rows

## Instructions

### Step 1: Config

Si no existe `config.json`, preguntar al usuario:

- `person_tag`: Su tag personal de QA (formato: NombreApellido-QA)
- `person_tag_fbid`: El FBID de ese tag

Guardar en `config.json` en esta misma carpeta.

### Step 2: Leer Tasks

```bash
python scripts/read-tasks.py
```

Genera `output/tasks-raw.json`.

### Step 3: Validar

```bash
python scripts/validate-tasks.py
```

Genera `output/validation-report.md`.

**Si hay errores → mostrar el reporte y NO avanzar.**

## Examples

Example 1: Ejecución normal
User says: "genera mi C2C"
Actions:

1. Verifica config.json existe
2. Ejecuta `python scripts/read-tasks.py`
3. Ejecuta `python scripts/validate-tasks.py`
4. Muestra validation-report.md al usuario
Result: Si todo OK → listo. Si errores → usuario corrige tasks.

## Troubleshooting

Error: "config.json not found"
Cause: Primera ejecución
Solution: Preguntar person_tag y person_tag_fbid, crear config.json

Error: "0 tasks found"
Cause: No hay tasks de esta semana con esos tags
Solution: Verificar que existan tasks creadas entre lunes y domingo con tag SOFTTEK-PQX-QA + tag personal
