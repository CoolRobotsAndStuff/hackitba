import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Datos de prueba (igual que tu script) ---
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
        }
    ],
    "team_members": [
        {"email": "ana.gomez@empresa.com", "name": "Ana Gómez", "available_days": 0},
        {"email": "luis.perez@empresa.com", "name": "Luis Pérez", "available_days": 3}
    ]
}

print("Llamando a Gemini...")

# --- Prompt (reemplaza tools/function calling) ---
prompt = f"""
Sos un orquestador de proyectos de software.

Analizá el siguiente contexto y proponé un plan para resolver el atraso sin superar el deadline.

RESPONDÉ SOLO en formato JSON con esta estructura:

{{
  "summary": "string",
  "actions": [
    {{
      "type": "reassign_task | reschedule_task | notify_team",
      "task_id": "string",
      "new_assignee": "string",
      "new_due_date": "string",
      "calendar_event_id": "string",
      "message": "string",
      "reason": "string"
    }}
  ]
}}

Contexto:
{json.dumps(contexto, indent=2)}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)

# --- Parseo ---
try:
    text = response.text.strip()

    # A veces Gemini devuelve ```json ... ```
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.replace("json", "").strip()

    plan = json.loads(text)

    print("\n✅ RESPUESTA DE GEMINI")
    print("=" * 50)
    print(f"RESUMEN: {plan['summary']}")
    print(f"\nACCIONES PROPUESTAS ({len(plan['actions'])}):")

    for i, action in enumerate(plan["actions"], 1):
        print(f"\n  [{i}] tipo: {action['type']}")
        for k, v in action.items():
            if k != "type":
                print(f"       {k}: {v}")

except Exception as e:
    print("\n⚠️ Error parseando respuesta:")
    print(e)
    print("\nRespuesta cruda:")
    print(response.text)