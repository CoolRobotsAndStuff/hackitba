from display import mostrar_plan

# Inventamos datos con la misma forma que los reales
plan_falso = [
    {
        "task_id": "T-04",
        "name": "Backend Auth",
        "assignee_before": "Juan",
        "assignee_after": "María",
        "date_before": "2025-06-10",
        "date_after": "2025-06-11",
        "changed": True
    },
    {
        "task_id": "T-05",
        "name": "Testing de integración",
        "assignee_before": "María",
        "assignee_after": "María",
        "date_before": "2025-06-11",
        "date_after": "2025-06-13",
        "changed": True
    },
    {
        "task_id": "T-06",
        "name": "Deploy a producción",
        "assignee_before": "Carlos",
        "assignee_after": "Carlos",
        "date_before": "2025-06-12",
        "date_after": "2025-06-12",
        "changed": False
    }
]

mostrar_plan(plan_falso)