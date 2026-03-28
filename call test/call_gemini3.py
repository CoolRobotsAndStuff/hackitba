# test_gemini.py
import os, json, requests
from dotenv import load_dotenv

load_dotenv()

# --- Datos de prueba (Schema 4 completo) ---
contexto = {
    "sprint": {
        "id": "SPR-12",
        "name": "Sprint 3 — Backend Auth",
        "deadline": "2025-11-15"
    },
    "delayed_task": {
        "id": "PROJ-14",
        "name": "Implementar JWT refresh token",
        "assignee": "ana.gomez@empresa.com",
        "delay_days": 2,
        "reason": "La persona asignada está enferma"
    },
    "all_tasks": [
        {
            "id": "PROJ-14",
            "name": "Implementar JWT refresh token",
            "status": "in_progress",
            "assignee": "ana.gomez@empresa.com",
            "estimated_days": 3,
            "dependencies": [],
            "dependents": ["PROJ-15", "PROJ-16"],
            "calendar_event_id": "abc123xyz",
            "due_date": "2025-11-13"
        },
        {
            "id": "PROJ-15",
            "name": "Testear endpoints de auth",
            "status": "todo",
            "assignee": "luis.perez@empresa.com",
            "estimated_days": 1,
            "dependencies": ["PROJ-14"],
            "dependents": [],
            "calendar_event_id": "def456uvw",
            "due_date": "2025-11-14"
        },
        {
            "id": "PROJ-16",
            "name": "Deploy a staging",
            "status": "todo",
            "assignee": "luis.perez@empresa.com",
            "estimated_days": 1,
            "dependencies": ["PROJ-14"],
            "dependents": [],
            "calendar_event_id": "ghi789rst",
            "due_date": "2025-11-15"
        }
    ],
    "team_members": [
        {"email": "ana.gomez@empresa.com", "name": "Ana Gómez", "available_days": 0},
        {"email": "luis.perez@empresa.com", "name": "Luis Pérez", "available_days": 3}
    ]
}

# --- Llamada a Gemini ---
# print("Llamando a Gemini...")

response = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={os.getenv('GEMINI_API_KEY')}",
    headers={"Content-Type": "application/json"},
    json={
        "system_instruction": {
            "parts": [{"text": "Sos un orquestador de proyectos de software. Analizá el estado del sprint y proponé acciones concretas para resolver el atraso sin superar el deadline."}]
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
                                    "description": "IDs de tareas en el orden de ejecución antes y después del rescheduling",
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