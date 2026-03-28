# test_gemini.py
import os, json, requests
from dotenv import load_dotenv
from collections import deque
from copy import copy, deepcopy
from dataclasses import dataclass

load_dotenv()

# =============================================================================
# ALGORITMO ORIGINAL (sin modificaciones)
# =============================================================================

def accesible_from(node, adj):
    ret = []
    q = deque()
    q.append(node)
    while q:
        n = q.popleft()
        ret.append(n)
        for d in adj[n]:
            if d not in q: q.append(d)
    return ret

def longest_path(tasks, src, dst):
    n = len(tasks)
    in_degree = [0] * n
    for node in range(n):
        for neighbor in tasks[node]:
            in_degree[neighbor] += 1

    queue = deque(i for i in range(n) if in_degree[i] == 0)
    topo_order = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for neighbor in tasks[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    dist = [-1] * n
    dist[src] = 0
    for node in topo_order:
        if dist[node] == -1:
            continue
        for neighbor in tasks[node]:
            dist[neighbor] = max(dist[neighbor], dist[node] + 1)

    return dist[dst]

def longest_chain_length(node, adj):
    n = len(adj)
    indegree = [0] * n
    for i in range(n):
        for next_node in adj[i]:
            indegree[next_node] += 1

    longest = 0
    for root, ind in enumerate(indegree):
        if ind == 0:
            longest = max(longest, longest_path(adj, root, node))
    return longest

def organize_tasks(adj):
    n = len(adj)
    index = []
    for node in range(n):
        index.append(longest_chain_length(node, adj))
    return index

def most_repeated_count(arr):
    from collections import Counter
    element, count = Counter(arr).most_common(1)[0]
    return count

@dataclass
class TaskBitId:
    id: int
    task: int

def get_task_timeline(tasks):
    adj = [[]]*len(tasks)
    task_parts = list(range(len(tasks)))
    task_index = 0
    extra = len(adj)
    for i, t in enumerate(tasks):
        if t["days"] == 1:
            adj[i] = t["deps"]
        elif t["days"] == 2:
            adj[i] = [extra,]
            adj.append(t["deps"])
            task_parts.append(i)
            extra += 1
        elif t["days"] >= 3:
            adj[i] = [extra,]
            task_parts.append(i)
            extra += 1

            for _ in range(t["days"] - 2):
                adj.append([extra,])
                task_parts.append(i)
                extra += 1

            adj.append(t["deps"])

    adj = invert_graph(adj)
    indexes = organize_tasks(adj)

    arr = []
    for _ in range(max(indexes)+1):
        arr.append([])
    for node, index in enumerate(indexes):
        arr[index].append(node)

    return arr, task_parts

def invert_graph(tasks):
    n = len(tasks)
    inverted = [[] for _ in range(n)]
    for node in range(n):
        for neighbor in tasks[node]:
            inverted[neighbor].append(node)
    return inverted

# =============================================================================
# CONVERSION ENTRE CONTEXTO JSON Y FORMATO DEL ALGORITMO
# =============================================================================

def context_to_tasks(context):
    """
    Convierte el contexto JSON al formato que espera el algoritmo:
        {"name": "...", "deps": [0, 2], "days": 3}
    Las dependencias pasan de IDs de Jira ("PROJ-02") a indices numericos (1).
    """
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
    """
    Convierte el timeline de indices internos del algoritmo a IDs de Jira.
    Usa task_parts para mapear nodos expandidos (dias) de vuelta a su tarea original.
    """
    index_to_id = {i: task["id"] for i, task in enumerate(context["all_tasks"])}
    return [[index_to_id[task_parts[idx]] for idx in day] for day in timeline]

# =============================================================================
# CONTEXTO DE PRUEBA
# =============================================================================

contexto = {
    "sprint": {
        "id": "SPR-15",
        "name": "Sprint 5 - Features Q4",
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
            "start_date": "2025-11-01",
            "due_date": "2025-11-05",
            "dependencies": [],
            "dependents": [],
            "calendar_event_id": "cal111aaa"
        },
        {
            "id": "PROJ-02",
            "name": "Desarrollar sistema de notificaciones",
            "status": "in_progress",
            "assignee": "maria.lopez@empresa.com",
            "estimated_days": 5,
            "start_date": "2025-11-01",
            "due_date": "2025-11-05",
            "dependencies": [],
            "dependents": [],
            "calendar_event_id": "cal222bbb"
        },
        {
            "id": "PROJ-03",
            "name": "Migracion de base de datos",
            "status": "in_progress",
            "assignee": "diego.fernandez@empresa.com",
            "estimated_days": 5,
            "start_date": "2025-11-01",
            "due_date": "2025-11-05",
            "dependencies": [],
            "dependents": [],
            "calendar_event_id": "cal333ccc"
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
# PASO 2 — GEMINI ASIGNA PERSONAS Y GENERA EL SUMMARY
# =============================================================================

payload_gemini = {
    "context": contexto,
    "computed_timeline": timeline_jira,
    "task_order": {
        "before": order_before,
        "after": order_after
    }
}

print("Llamando a Gemini...")

response = requests.post(
    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.getenv('GEMINI_API_KEY')}",
    headers={"Content-Type": "application/json"},
    json={
        "system_instruction": {
            "parts": [{
                "text": (
                    "Sos un orquestador de proyectos de software. "
                    "El orden de las tareas ya fue calculado matematicamente y esta en computed_timeline. "
                    "Cada entrada del timeline es un dia, y una tarea puede aparecer en varios dias consecutivos si dura mas de un dia. "
                    "Tu trabajo es: 1) asignar personas a cada tarea respetando su disponibilidad y balanceando la carga, "
                    "2) proponer fechas nuevas usando start_date y estimated_days de cada tarea si es necesario, "
                    "3) generar un summary explicando el razonamiento de los cambios. "
                    "No cambies el orden de las tareas, solo la asignacion de personas y fechas."
                )
            }]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": json.dumps(payload_gemini)}]
            }
        ],
        "tools": [
            {
                "function_declarations": [
                    {
                        "name": "propose_reschedule_plan",
                        "description": "Propone asignaciones de personas y fechas para el orden de tareas ya calculado",
                        "parameters": {
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

# =============================================================================
# PASO 3 — LEER Y MOSTRAR RESULTADO FINAL
# =============================================================================

data = response.json()

if response.status_code != 200:
    print(f"\nERROR HTTP {response.status_code}:")
    print(json.dumps(data, indent=2))
else:
    part = data["candidates"][0]["content"]["parts"][0]
    plan = part["functionCall"]["args"]

    plan["task_order"] = {
        "before": order_before,
        "after": order_after
    }

    print(json.dumps(plan, indent=2, ensure_ascii=False))

    # --- Asignaciones propuestas por Gemini ---
    reassignments = {
        action["task_id"]: action["new_assignee"]
        for action in plan["actions"]
        if action["type"] == "reassign_task" and "task_id" in action and "new_assignee" in action
    }

    email_to_name = {m["email"]: m["name"] for m in contexto["team_members"]}

    print("\n--- ASIGNACIONES PROPUESTAS ---")
    for task in contexto["all_tasks"]:
        task_id = task["id"]
        task_name = task["name"]
        assignee_email = reassignments.get(task_id, task["assignee"])
        assignee_name = email_to_name.get(assignee_email, assignee_email)
        print(f"  {task_id} | {task_name} -> {assignee_name}")