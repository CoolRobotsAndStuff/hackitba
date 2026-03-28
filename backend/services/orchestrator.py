def procesar_atraso(prompt):
    return {
        "summary": f"Plan generado para: {prompt}",
        "actions": [
            {
                "type": "update_calendar_event",
                "target_id": "evento-123",
                "params": {
                    "new_start": "2025-06-19T10:00:00",
                    "new_end": "2025-06-19T11:00:00"
                }
            },
            {
                "type": "update_jira_issue",
                "target_id": "KAN-4",
                "params": {
                    "new_assignee": "pedro@equipo.com",
                    "new_due_date": "2025-06-19"
                }
            }
        ]
    }

def ejecutar_acciones(actions):
    results = []
    for action in actions:
        results.append({
            "success": True,
            "message": f"✓ {action['type'].replace('_', ' ').title()} — {action['target_id']}"
        })
    return {"results": results}