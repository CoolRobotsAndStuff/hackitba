# test_gemini.py
import os, json, requests
from dotenv import load_dotenv

load_dotenv()

# --- Datos de prueba (Schema 4 completo) ---
contexto = {
    "sprint": {
        "id": "SPR-15",
        "name": "Sprint 5 — Features Q4",
        "deadline": "2025-11-10"
    },
    "delayed_task": {
        "id": "PROJ-01",
        "name": "Implementar modulo de pagos",
        "assignee": "carlos.rodriguez@empresa.com",
        "delay_days": 10,
        "reason": "El trabajador asignado esta enfermo y no puede trabajar por los proximos 10 dias"
    },
    "all_tasks": [
        {
            "id": "PROJ-01",
            "name": "Implementar modulo de pagos",
            "status": "in_progress",
            "assignee": "carlos.rodriguez@empresa.com",
            "estimated_days": 5,
            "dependencies": [],
            "dependents": [],
            "calendar_event_id": "cal111aaa",
            "due_date": "2025-11-05"
        },
        {
            "id": "PROJ-02",
            "name": "Desarrollar sistema de notificaciones",
            "status": "in_progress",
            "assignee": "maria.lopez@empresa.com",
            "estimated_days": 5,
            "dependencies": [],
            "dependents": [],
            "calendar_event_id": "cal222bbb",
            "due_date": "2025-11-05"
        },
        {
            "id": "PROJ-03",
            "name": "Migracion de base de datos",
            "status": "in_progress",
            "assignee": "diego.fernandez@empresa.com",
            "estimated_days": 5,
            "dependencies": [],
            "dependents": [],
            "calendar_event_id": "cal333ccc",
            "due_date": "2025-11-05"
        }
    ],
    "team_members": [
        {
            "email": "carlos.rodriguez@empresa.com",
            "name": "Carlos Rodriguez",
            "available_days": 0
        },
        {
            "email": "maria.lopez@empresa.com",
            "name": "Maria Lopez",
            "available_days": 5
        },
        {
            "email": "diego.fernandez@empresa.com",
            "name": "Diego Fernandez",
            "available_days": 5
        }
    ]
}

# --- Llamada a Gemini ---
print("Llamando a Gemini...")

response = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={os.getenv('GEMINI_API_KEY')}",
    headers={"Content-Type": "application/json"},
    json={
        "system_instruction": {
            "parts": [{"text": "Sos un orquestador de proyectos de software. Analiza el estado del sprint y propone acciones concretas para resolver el atraso sin superar el deadline."}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": json.dumps(contexto)}]
            }
        ],
        "tools": [
            {
                "function_declarations": [
                    {
                        "name": "propose_reschedule_plan",
                        "description": "Propone un plan de acciones para resolver el atraso del sprint",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "summary": {"type": "string"},
                                "actions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "type": {
                                                "type": "string",
                                                "enum": ["reassign_task", "reschedule_task", "notify_team"]
                                            },
                                            "task_id": {"type": "string"},
                                            "new_assignee": {"type": "string"},
                                            "new_due_date": {"type": "string"},
                                            "calendar_event_id": {"type": "string"},
                                            "message": {"type": "string"},
                                            "reason": {"type": "string"}
                                        },
                                        "required": ["type"]
                                    }
                                },
                                "task_order": {
                                    "type": "object",
                                    "description": "IDs de tareas en el orden de ejecucion antes y despues del rescheduling",
                                    "properties": {
                                        "before": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "IDs de tareas en el orden original"
                                        },
                                        "after": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "IDs de tareas en el nuevo orden propuesto"
                                        }
                                    },
                                    "required": ["before", "after"]
                                }
                            },
                            "required": ["summary", "actions", "task_order"]
                        }
                    }
                ]
            }
        ],
        "tool_config": {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": ["propose_reschedule_plan"]
            }
        }
    }
)

# --- Leer respuesta ---
data = response.json()

if response.status_code != 200:
    print(f"\n ERROR HTTP {response.status_code}:")
    print(json.dumps(data, indent=2))
else:
    part = data["candidates"][0]["content"]["parts"][0]
    plan = part["functionCall"]["args"]

    print(json.dumps(plan, indent=2, ensure_ascii=False))