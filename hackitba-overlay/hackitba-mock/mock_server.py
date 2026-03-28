from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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


@app.route('/report-delay', methods=['POST'])
def report_delay():
    return jsonify({
        "summary": "Reasignar KAN-1 a Pedro y mover el Sprint Review 2 días para cumplir el deadline del viernes",
        "actions": [
            {
                "type": "update_calendar_event",
                "target_id": "7jg2lhrn70nusum2oipv23q78m",
                "params": {
                    "new_start": "2026-04-12T10:00:00",
                    "new_end":   "2026-04-12T11:00:00"
                }
            },
            {
                "type": "update_jira_issue",
                "target_id": "KAN-1",
                "params": {
                    "new_assignee": "712020:dab6a190-e38c-4fc2-b30d-06ca52ddcea2"
                }
            },
            {
                "type": "update_jira_duedate",
                "target_id": "KAN-1",
                "params": {
                    "due_date": "2026-04-12"
                }
            }
        ],
        "dependency_graph": {
            "nodes": [
                {"id": "KAN-1", "label": "Auth service", "status": "progress", "x": 0.5,  "y": 0.15},
                {"id": "KAN-2", "label": "Tests auth",   "status": "todo",     "x": 0.2,  "y": 0.45},
                {"id": "KAN-3", "label": "Deploy stg",   "status": "blocked",  "x": 0.8,  "y": 0.45},
                {"id": "KAN-4", "label": "Monitoring",   "status": "todo",     "x": 0.35, "y": 0.78},
                {"id": "KAN-5", "label": "Go live",      "status": "todo",     "x": 0.65, "y": 0.78}
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


@app.route('/execute-plan', methods=['POST'])
def execute_plan():
    data = request.json
    actions = data.get('actions', [])
    labels = {
        "update_calendar_event": "Evento de Calendar movido",
        "update_jira_issue":     "Issue de Jira reasignada",
        "update_jira_duedate":   "Due date actualizada en Jira",
        "notify_slack":          "Notificación enviada al equipo",
    }
    results = []
    for action in actions:
        label = labels.get(action['type'], action['type'].replace('_', ' ').title())
        results.append({
            "success": True,
            "message": f"✓ {label} — {action.get('target_id', '')}"
        })
    return jsonify({"results": results})


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


@app.route('/pending-events', methods=['GET'])
def pending_events():
    global _pending_index
    _pending_index += 1
    # Devuelve un evento cada 2 llamadas para simular que no siempre hay novedades
    if _pending_index % 2 == 0:
        return jsonify({"events": []})
    event = _pending_cycle[(_pending_index // 2 - 1) % len(_pending_cycle)]
    return jsonify({"events": [event]})


@app.route('/incoming-event', methods=['POST'])
def incoming_event():
    data = request.json
    print(f"[incoming-event] {data.get('source')} — {data.get('event_type')}")
    return jsonify({"ok": True})


if __name__ == '__main__':
    print("HALeph mock server en http://localhost:8000")
    print("  POST /report-delay")
    print("  POST /execute-plan")
    print("  GET  /team-status")
    print("  GET  /pending-events")
    print("  POST /incoming-event")
    app.run(port=8000, debug=True)