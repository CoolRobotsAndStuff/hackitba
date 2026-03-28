# test_claude.py
import os, json, requests, uuid
from dotenv import load_dotenv
from collections import deque
from copy import copy, deepcopy
from dataclasses import dataclass
from algo import *

load_dotenv()

# =============================================================================
# CONVERSION ENTRE CONTEXTO JSON Y FORMATO DEL ALGORITMO
# =============================================================================

def context_to_tasks(context):
    all_tasks = context["all_tasks"]
    id_to_index = {task["id"]: i for i, task in enumerate(all_tasks)}
    tasks = [
        {
            "name": task["name"],
            "deps": [id_to_index[dep] for dep in task["dependencies"]],
            "days": task["estimated_days"]
        }
        for task in all_tasks
    ]
    return tasks, id_to_index

def timeline_to_jira_ids(timeline, task_parts, context):
    index_to_id = {i: task["id"] for i, task in enumerate(context["all_tasks"])}
    return [[index_to_id[task_parts[idx]] for idx in day] for day in timeline]

# =============================================================================
# CONTEXTO DE PRUEBA
# =============================================================================

contexto = {
  "sprint": {
    "id": "SPR-20",
    "name": "Sprint 7 - Integracion Core",
    "deadline": "2025-11-20"
  },
  "delayed_task": {
    "id": "PROJ-04",
    "name": "Implementar sistema de reportes",
    "assignee": "cacho.gomez@empresa.com",
    "delay_days": 3,
    "reason": "La tarea ahora depende de PROJ-01 que todavia no termino"
  },
  "all_tasks": [
    {
      "id": "PROJ-00",
      "name": "Configurar entorno de produccion",
      "status": "in_progress",
      "assignee": "pedro.martinez@empresa.com",
      "estimated_days": 2,
      "start_date": "2025-11-10",
      "due_date": "2025-11-12",
      "dependencies": [],
      "dependents": ["PROJ-02"],
      "calendar_event_id": "cal000aaa"
    },
    {
      "id": "PROJ-01",
      "name": "Desarrollar modulo de autenticacion",
      "status": "todo",
      "assignee": "juan.perez@empresa.com",
      "estimated_days": 2,
      "start_date": "2025-11-15",
      "due_date": "2025-11-17",
      "dependencies": ["PROJ-02", "PROJ-03"],
      "dependents": ["PROJ-04"],
      "calendar_event_id": "cal111bbb"
    },
    {
      "id": "PROJ-02",
      "name": "Implementar capa de servicios",
      "status": "todo",
      "assignee": "maria.lopez@empresa.com",
      "estimated_days": 2,
      "start_date": "2025-11-13",
      "due_date": "2025-11-15",
      "dependencies": ["PROJ-03", "PROJ-00"],
      "dependents": ["PROJ-01"],
      "calendar_event_id": "cal222ccc"
    },
    {
      "id": "PROJ-03",
      "name": "Disenar esquema de base de datos",
      "status": "in_progress",
      "assignee": "lucas.fernandez@empresa.com",
      "estimated_days": 3,
      "start_date": "2025-11-10",
      "due_date": "2025-11-13",
      "dependencies": [],
      "dependents": ["PROJ-01", "PROJ-02"],
      "calendar_event_id": "cal333ddd"
    },
    {
      "id": "PROJ-04",
      "name": "Implementar sistema de reportes",
      "status": "todo",
      "assignee": "cacho.gomez@empresa.com",
      "estimated_days": 2,
      "start_date": "2025-11-17",
      "due_date": "2025-11-19",
      "dependencies": ["PROJ-01"],
      "dependents": [],
      "calendar_event_id": "cal444eee"
    }
  ],
  "team_members": [
    {"email": "pedro.martinez@empresa.com", "name": "Pedro Martinez", "available_days": 4},
    {"email": "juan.perez@empresa.com",     "name": "Juan Perez",     "available_days": 4},
    {"email": "maria.lopez@empresa.com",    "name": "Maria Lopez",    "available_days": 4},
    {"email": "lucas.fernandez@empresa.com","name": "Lucas Fernandez","available_days": 5},
    {"email": "cacho.gomez@empresa.com",    "name": "Cacho Gomez",    "available_days": 3}
  ]
}

# =============================================================================
# PASO 1 — ALGORITMO CALCULA EL ORDEN CORRECTO
# =============================================================================

tasks_fmt, id_to_index = context_to_tasks(contexto)
timeline, task_parts = get_task_timeline(tasks_fmt)
timeline_jira = timeline_to_jira_ids(timeline, task_parts, contexto)

order_before = [task["id"] for task in contexto["all_tasks"]]
order_after = []
seen = set()
for day in timeline_jira:
    for task_id in day:
        if task_id not in seen:
            order_after.append(task_id)
            seen.add(task_id)

# =============================================================================
# PASO 2 — CLAUDE ASIGNA PERSONAS Y GENERA EL SUMMARY
# =============================================================================

MCP_SERVER_URL = "https://iandib.app.n8n.cloud/mcp-test/101a48e4-4bd9-46dc-8e6b-d5d225c593c5"
#MCP_SERVER_URL = "https://iandib.app.n8n.cloud/mcp/101a48e4-4bd9-46dc-8e6b-d5d225c593c5"

HEADERS = {
    "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
    "anthropic-version": "2023-06-01",
    "Content-Type": "application/json"
}

payload_claude = {
    "context": contexto,
    "computed_timeline": timeline_jira,
    "task_order": {
        "before": order_before,
        "after": order_after
    }
}

print("Llamando a Claude...")

response = requests.post(
    "https://api.anthropic.com/v1/messages",
    headers=HEADERS,
    json={
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "system": (
            "Sos un orquestador de proyectos de software. "
            "El orden de las tareas ya fue calculado matematicamente y esta en computed_timeline. "
            "Cada entrada del timeline es un dia, y una tarea puede aparecer en varios dias consecutivos si dura mas de un dia. "
            "Tu trabajo es: 1) asignar personas a cada tarea respetando su disponibilidad y balanceando la carga, "
            "2) proponer fechas nuevas usando start_date y estimated_days de cada tarea si es necesario, "
            "3) generar un summary explicando el razonamiento de los cambios. "
            "No cambies el orden de las tareas, solo la asignacion de personas y fechas."
        ),
        "messages": [
            {"role": "user", "content": json.dumps(payload_claude)}
        ],
        "tools": [
            {
                "name": "propose_reschedule_plan",
                "description": "Propone asignaciones de personas y fechas para el orden de tareas ya calculado",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Explicacion del razonamiento detras de los cambios de asignacion"
                        },
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
                                    "new_start_date": {"type": "string"},
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
                            "properties": {
                                "before": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "IDs de tareas en el orden original"
                                },
                                "after": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "IDs de tareas en el nuevo orden calculado por el algoritmo"
                                }
                            },
                            "required": ["before", "after"]
                        }
                    },
                    "required": ["summary", "actions", "task_order"]
                }
            },
        ],
        "tool_choice": {"type": "tool", "name": "propose_reschedule_plan"}
    },
    verify=False  # permissive SSL
)

# =============================================================================
# PASO 3 — LEER Y MOSTRAR RESULTADO FINAL
# =============================================================================

data = response.json()

if response.status_code != 200:
    print(f"\nERROR HTTP {response.status_code}:")
    print(json.dumps(data, indent=2))
else:
    plan = next(
        (block["input"] for block in data["content"] if block.get("name") == "propose_reschedule_plan"),
        None
    )

    if plan is None:
        print("No se encontro el bloque propose_reschedule_plan:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        plan["task_order"] = {
            "before": order_before,
            "after": order_after
        }

        print(json.dumps(plan, indent=2, ensure_ascii=False))

        # =====================================================================
        # PASO 4 — ENVIAR EL PLAN AL MCP SERVER (JSON-RPC over SSE)
        # =====================================================================

        def mcp_call(method, params=None):
            """Send a JSON-RPC request to the MCP server and return the result."""
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": method,
                "params": params or {}
            }
            resp = requests.post(
                MCP_SERVER_URL,
                json=payload,
                headers={
                    #"Authorization": f"Bearer {os.getenv('N8N_API_KEY')}",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                verify=False,
                stream=True,
            )
            result_text = ""
            for line in resp.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                if decoded.startswith("data:"):
                    result_text = decoded[len("data:"):].strip()
                    break
            if not result_text:
                return {"error": f"HTTP {resp.status_code} — no data received"}
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                return {"raw": result_text}

        print("\nConectando al MCP server (n8n)...")

        # 1. Initialize the MCP session
        init = mcp_call("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "hackitba-orchestrator", "version": "1.0"},
            "capabilities": {}
        })
        print(f"MCP init: {json.dumps(init, indent=2)}")

        # 2. Discover available tools
        tools_resp = mcp_call("tools/list")
        available_tools = tools_resp.get("result", {}).get("tools", [])
        print(f"MCP tools disponibles: {[t['name'] for t in available_tools]}")

        # 3. Call the first available tool with the plan
        if available_tools:
            tool_name = available_tools[0]["name"]
            print(f"\nLlamando tool MCP '{tool_name}'...")
            tool_result = mcp_call("tools/call", {
                "name": tool_name,
                "arguments": plan
            })
            print(f"MCP tool result: {json.dumps(tool_result, indent=2, ensure_ascii=False)}")
        else:
            print("No se encontraron tools en el MCP server.")

        reassignments = {
            action["task_id"]: action["new_assignee"]
            for action in plan["actions"]
            if action["type"] == "reassign_task"
            and "task_id" in action
            and "new_assignee" in action
        }

        email_to_name = {m["email"]: m["name"] for m in contexto["team_members"]}

        task_info = {}
        for task in contexto["all_tasks"]:
            assignee_email = reassignments.get(task["id"], task["assignee"])
            task_info[task["id"]] = {
                "name": task["name"],
                "assignee": email_to_name.get(assignee_email, assignee_email)
            }

        print()
        for day, task_ids in enumerate(timeline_jira):
            print(f"Day {day}:")
            for task_id in task_ids:
                info = task_info[task_id]
                print(f"    - {task_id} | {info['name']} -> {info['assignee']}")
