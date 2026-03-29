from flask import Flask, send_from_directory, render_template, request, jsonify
app = Flask(__name__, static_folder="static", template_folder="pages")
import sqlite3

from jira import *

conn = sqlite3.connect('data.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, user TEXT, position INTEGER)')
conn.commit()

@app.route("/")
def index():
    return render_template("./index.html")

@app.route("/jira_webhook", methods=['POST'])
def jira_webhook():
    data = request.get_json(silent=True)
    tasks = get_jira_tasks()
    print('Received Jira event. Now the tasks are:', tasks)
    print("Timeline:")
    print(get_timeline_string(tasks));
    return jsonify({'status': 'ok'}), 200

@app.route("/incoming-event", methods=['POST'])
def incoming_event():
    data = request.get_json(silent=True)
    return jsonify({'status': 'ok'}), 200

@app.route('/tasks', methods=['POST'])
def receive_tasks():
    data = request.get_json(silent=True)
    print('Received tasks:', data)
    tasks = data["tasks"]
    c.execute('DELETE FROM tasks')
    for i, task in enumerate(tasks):
        c.execute('INSERT INTO tasks (id, user, position) VALUES (?, ?, ?)', (task["id"], "ale", i))
    conn.commit()
    return jsonify({'status': 'ok'}), 200

@app.route('/tasks', methods=['GET'])
def send_tasks():
    c.execute('SELECT id FROM tasks ORDER BY position')
    result = [{"id": r[0]} for r in c.fetchall()]
    return jsonify(result);

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':

    app.run(host='0.0.0.0', port=3000, debug=True)
