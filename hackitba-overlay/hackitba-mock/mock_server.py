from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════
# Pending events cycle (simulates webhook-like data)
# ═══════════════════════════════════════════════
_pending_cycle = [
    {
        "id": "evt_001",
        "source": "jira",
        "message": "KAN-1 cambió de 'In Progress' a 'In Review' por Pedro",
        "data": {"issue_key": "KAN-1", "status": "In Review", "assignee": "Pedro"}
    },
    {
        "id": "evt_002",
        "source": "google_calendar",
        "message": "Sprint Review movido al jueves 12/04 por el equipo",
        "data": {"event_id": "7jg2lhrn70nusum2oipv23q78m", "title": "Sprint review - T-14"}
    },
    {
        "id": "evt_003",
        "source": "jira",
        "message": "KAN-3 (Deploy staging) desbloqueado — listo para continuar",
        "data": {"issue_key": "KAN-3", "status": "In Progress"}
    },
]
_pending_index = 0


# ═══════════════════════════════════════════════
# POST /prompt — unified endpoint (the frontend uses THIS)
# Detects whether the user is reporting a delay or creating a plan
# ═══════════════════════════════════════════════
@app.route('/prompt', methods=['POST'])
def unified_prompt():
    data = request.json
    prompt = (data.get('prompt', '') or '').lower()

    plan_keywords = ['plan', 'crea', 'crear', 'armar', 'armá', 'planific',
                     'mvp', 'proyecto', 'cronograma', 'organiz']
    is_plan = any(kw in prompt for kw in plan_keywords)

    if is_plan:
        return _plan_response()
    else:
        return _delay_response()


def _delay_response():
    return jsonify({
        "type": "adjust",
        "summary": "Reasignar KAN-1 a Pedro y mover el Sprint Review 2 días para cumplir el deadline del viernes",
        "actions": [
            {
                "type": "update_calendar_event",
                "target_id": "7jg2lhrn70nusum2oipv23q78m",
                "params": {"new_start": "2026-04-12T10:00:00", "new_end": "2026-04-12T11:00:00"}
            },
            {
                "type": "update_jira_issue",
                "target_id": "KAN-1",
                "params": {"new_assignee": "Pedro"}
            },
            {
                "type": "update_jira_duedate",
                "target_id": "KAN-1",
                "params": {"due_date": "2026-04-12"}
            }
        ],
        "warnings": [],
        "dependency_graph": {
            "nodes": [
                {"id": "KAN-1", "label": "Auth service",   "status": "progress", "x": 0.5,  "y": 0.15},
                {"id": "KAN-2", "label": "Tests auth",     "status": "todo",     "x": 0.2,  "y": 0.45},
                {"id": "KAN-3", "label": "Deploy stg",     "status": "blocked",  "x": 0.8,  "y": 0.45},
                {"id": "KAN-4", "label": "Monitoring",     "status": "todo",     "x": 0.35, "y": 0.78},
                {"id": "KAN-5", "label": "Go live",        "status": "todo",     "x": 0.65, "y": 0.78}
            ],
            "edges": [
                {"from": "KAN-1", "to": "KAN-2"},
                {"from": "KAN-1", "to": "KAN-3"},
                {"from": "KAN-2", "to": "KAN-4"},
                {"from": "KAN-3", "to": "KAN-5"},
                {"from": "KAN-4", "to": "KAN-5"}
            ]
        }
    })


def _plan_response():
    return jsonify({
        "type": "plan",
        "summary": "Plan generado: 3 fases hasta el deadline. Soporte extra asignado a Pedro por historial de atrasos en infra.",
        "phases": [
            {
                "name": "Fase 1 — Setup (Semana 1)",
                "tasks": [
                    {"assignee": "Juan", "title": "Configurar repositorio y CI/CD", "date": "Lun"},
                    {"assignee": "Pedro", "title": "Provisionar infraestructura", "date": "Mar"},
                    {"assignee": "María", "title": "Diseño de arquitectura frontend", "date": "Mar"},
                    {"assignee": "Juan", "title": "Soporte infra con Pedro", "date": "Mié"}
                ],
                "note": "Juan como backup de Pedro — historial indica atrasos en tareas de infra"
            },
            {
                "name": "Fase 2 — Desarrollo (Semana 2-3)",
                "tasks": [
                    {"assignee": "Juan", "title": "Auth service + API core", "date": "Sem 2"},
                    {"assignee": "Pedro", "title": "Deploy pipeline + staging", "date": "Sem 2"},
                    {"assignee": "María", "title": "Dashboard + integración API", "date": "Sem 2-3"}
                ]
            },
            {
                "name": "Fase 3 — Testing (Semana 4)",
                "tasks": [
                    {"assignee": "Todos", "title": "Integración completa", "date": "Lun"},
                    {"assignee": "Pedro", "title": "Deploy a producción", "date": "Mié"},
                    {"assignee": "María", "title": "Demo + presentación", "date": "Vie"}
                ]
            }
        ],
        "actions": [
            {"type": "create_jira_issue", "target_id": "KAN-10", "params": {"summary": "Configurar repo y CI/CD"}},
            {"type": "create_jira_issue", "target_id": "KAN-11", "params": {"summary": "Provisionar infraestructura"}},
            {"type": "create_jira_issue", "target_id": "KAN-12", "params": {"summary": "Diseño arquitectura FE"}},
            {"type": "create_jira_issue", "target_id": "KAN-13", "params": {"summary": "Auth service + API core"}},
            {"type": "create_jira_issue", "target_id": "KAN-14", "params": {"summary": "Deploy pipeline + staging"}},
            {"type": "create_jira_issue", "target_id": "KAN-15", "params": {"summary": "Dashboard + integración"}},
            {"type": "create_calendar_event", "target_id": "demo", "params": {"summary": "Demo MVP"}},
            {"type": "notify_slack", "target_id": "general", "params": {"message": "Nuevo plan creado"}}
        ],
        "warnings": [
            "Pedro completó 2/4 tareas de infra con retraso en el último sprint."
        ],
        "dependency_graph": {
            "nodes": [
                {"id": "KAN-10", "label": "Repo + CI",   "status": "todo", "x": 0.2,  "y": 0.1},
                {"id": "KAN-11", "label": "Infra",       "status": "todo", "x": 0.5,  "y": 0.1},
                {"id": "KAN-12", "label": "Diseño FE",   "status": "todo", "x": 0.8,  "y": 0.1},
                {"id": "KAN-13", "label": "Auth + API",  "status": "todo", "x": 0.3,  "y": 0.45},
                {"id": "KAN-14", "label": "Deploy",      "status": "todo", "x": 0.7,  "y": 0.45},
                {"id": "KAN-15", "label": "Dashboard",   "status": "todo", "x": 0.5,  "y": 0.45},
                {"id": "INT",    "label": "Integración", "status": "todo", "x": 0.5,  "y": 0.75},
                {"id": "DEMO",   "label": "Demo MVP",    "status": "todo", "x": 0.5,  "y": 0.95}
            ],
            "edges": [
                {"from": "KAN-10", "to": "KAN-13"},
                {"from": "KAN-11", "to": "KAN-14"},
                {"from": "KAN-12", "to": "KAN-15"},
                {"from": "KAN-13", "to": "INT"},
                {"from": "KAN-14", "to": "INT"},
                {"from": "KAN-15", "to": "INT"},
                {"from": "INT", "to": "DEMO"}
            ]
        }
    })


# ═══════════════════════════════════════════════
# POST /report-delay — legacy, kept for compat
# ═══════════════════════════════════════════════
@app.route('/report-delay', methods=['POST'])
def report_delay():
    return _delay_response()


# ═══════════════════════════════════════════════
# POST /execute-plan
# ═══════════════════════════════════════════════
@app.route('/execute-plan', methods=['POST'])
def execute_plan():
    data = request.json
    actions = data.get('actions', [])
    labels = {
        "update_calendar_event": "Evento de Calendar movido",
        "update_jira_issue":     "Issue de Jira reasignada",
        "update_jira_duedate":   "Due date actualizada en Jira",
        "notify_slack":          "Notificación enviada al equipo",
        "create_jira_issue":     "Issue creada en Jira",
        "create_calendar_event": "Evento creado en Calendar",
        "create_github_issue":   "Issue creada en GitHub",
    }
    results = []
    for action in actions:
        label = labels.get(action['type'], action['type'].replace('_', ' ').title())
        results.append({
            "success": True,
            "message": f"{label} — {action.get('target_id', '')}"
        })
    return jsonify({"results": results})


# ═══════════════════════════════════════════════
# GET /graph-data — current dependency graph
# (used when the graph tab is opened without prior prompt)
# ═══════════════════════════════════════════════
@app.route('/graph-data', methods=['GET'])
def graph_data():
    return jsonify({
        "nodes": [
            {"id": "KAN-1", "label": "Auth service",   "status": "progress", "x": 0.5,  "y": 0.15},
            {"id": "KAN-2", "label": "Tests auth",     "status": "todo",     "x": 0.2,  "y": 0.45},
            {"id": "KAN-3", "label": "Deploy stg",     "status": "blocked",  "x": 0.8,  "y": 0.45},
            {"id": "KAN-4", "label": "Monitoring",     "status": "todo",     "x": 0.35, "y": 0.78},
            {"id": "KAN-5", "label": "Go live",        "status": "todo",     "x": 0.65, "y": 0.78}
        ],
        "edges": [
            {"from": "KAN-1", "to": "KAN-2"},
            {"from": "KAN-1", "to": "KAN-3"},
            {"from": "KAN-2", "to": "KAN-4"},
            {"from": "KAN-3", "to": "KAN-5"},
            {"from": "KAN-4", "to": "KAN-5"}
        ]
    })


# ═══════════════════════════════════════════════
# GET /team-status
# ═══════════════════════════════════════════════
@app.route('/team-status', methods=['GET'])
def team_status():
    return jsonify({
        "members": [
            {
                "name": "Juan",
                "role": "Backend Engineer",
                "tasks": [
                    {"id": "KAN-1", "title": "Implementar auth service", "status": "In Progress", "source": "jira"},
                    {"id": "KAN-2", "title": "Tests de auth",            "status": "To Do",       "source": "jira"}
                ]
            },
            {
                "name": "Pedro",
                "role": "Backend Engineer",
                "tasks": [
                    {"id": "KAN-3", "title": "Deploy staging",   "status": "Blocked", "source": "jira"},
                    {"id": "KAN-4", "title": "Setup monitoring", "status": "To Do",   "source": "jira"}
                ]
            },
            {
                "name": "María",
                "role": "Frontend Engineer",
                "tasks": [
                    {"id": "KAN-5", "title": "Dashboard UI", "status": "In Progress", "source": "jira"}
                ]
            }
        ]
    })


# ═══════════════════════════════════════════════
# GET /pending-events
# ═══════════════════════════════════════════════
@app.route('/pending-events', methods=['GET'])
def pending_events():
    global _pending_index
    _pending_index += 1
    if _pending_index % 2 == 0:
        return jsonify({"events": []})
    event = _pending_cycle[(_pending_index // 2 - 1) % len(_pending_cycle)]
    return jsonify({"events": [event]})


# ═══════════════════════════════════════════════
# POST /incoming-event
# ═══════════════════════════════════════════════
@app.route('/incoming-event', methods=['POST'])
def incoming_event():
    data = request.json
    print(f"[incoming-event] {data.get('source')} — {data.get('event_type')}")
    return jsonify({"ok": True})


if __name__ == '__main__':
    print()
    print("  HALeph mock server corriendo en http://localhost:8000")
    print()
    print("  POST /prompt          ← el frontend usa este")
    print("  POST /report-delay    ← legacy")
    print("  POST /execute-plan")
    print("  GET  /graph-data")
    print("  GET  /team-status")
    print("  GET  /pending-events")
    print("  POST /incoming-event")
    print()
    app.run(port=8000, debug=True)