from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/report-delay', methods=['POST'])
def report_delay():
    return jsonify({
        "summary": "Reasignar T-14 a Pedro y comprimir T-15 para cumplir el deadline del viernes",
        "actions": [
            {
                "type": "update_calendar_event",
                "target_id": "7jg2lhrn70nusum2oipv23q78m",
                "params": {
                    "new_start": "2025-06-19T10:00:00",
                    "new_end": "2025-06-19T11:00:00"
                }
            },
            {
                "type": "update_jira_issue",
                "target_id": "KAN-4",
                "params": {
                    "new_assignee": "712020:dab6a190-e38c-4fc2-b30d-06ca52ddcea2",
                    "new_due_date": "2025-06-19"
                }
            }
        ]
    })

@app.route('/execute-plan', methods=['POST'])
def execute_plan():
    data = request.json
    actions = data.get('actions', [])
    results = []

    for action in actions:
        results.append({
            "success": True,
            "message": f"✓ {action['type'].replace('_', ' ').title()} — {action['target_id']}"
        })

    return jsonify({ "results": results })

if __name__ == '__main__':
    app.run(port=8000, debug=True)