def interpretar_respuesta(data):
    if data is None:
        return None

    if "actions" not in data:
        print(f"El backend devolvió un error: {data.get('mensaje', 'desconocido')}")
        return None

    plan = {
        "summary": data.get("summary", ""),
        "task_order": data.get("task_order", {}),
        "acciones": []
    }

    for action in data["actions"]:
        plan["acciones"].append({
            "task_id": action["task_id"],
            "name": action.get("reason", ""),
            "type": action["type"],
            "date_after": action.get("new_due_date", "—"),
            "changed": True
        })

    return plan