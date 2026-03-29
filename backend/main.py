"""
HALeph Backend v3 — Flask server that orchestrates:
  - Claude API (reasoning + plan generation)
  - DAG algorithm (task scheduling)
  - Jira REST API (reading + direct writing as MCP fallback)
  - n8n MCP Server (writing to Jira, Calendar, Slack)
  - Bidirectional sync: Jira ↔ Calendar (changes in one reflect in the other)
  - Event queue (Jira/Calendar → frontend polling)

Endpoints:
  POST /prompt            ← primary prompt endpoint
  POST /report-delay      ← legacy fallback (same logic)
  POST /execute-plan      ← executes actions via MCP (+ direct API fallback)
  GET  /pending-events    ← polls queued events from Jira/Calendar changes
  GET  /team-status       ← team members + their tasks from Jira
  GET  /graph-data        ← dependency graph for the DAG visualization
  POST /incoming-event    ← receives events from n8n triggers
  POST /jira_webhook      ← receives native Jira webhooks → syncs to Calendar
  POST /calendar_webhook  ← receives calendar change notifications → syncs to Jira
  GET  /health            ← status check
"""

import os
import json
import uuid
import time
import threading
import requests
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from collections import deque
from requests.auth import HTTPBasicAuth
from google.oauth2 import service_account
from googleapiclient.discovery import build

from algo import get_task_timeline, get_timeline_string
from jira import get_jira_tasks, estimate_days

load_dotenv()

app = Flask(__name__)
CORS(app)

# =============================================================================
# CONFIGURATION
# =============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN", "aledeumsaf.atlassian.net")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "aledeum.saf@gmail.com")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "KAN")
MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "https://iandib.app.n8n.cloud/mcp/101a48e4-4bd9-46dc-8e6b-d5d225c593c5",
)

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "hackitba.demo@gmail.com")
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_sa_env = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json")
# Resolve relative paths from .env relative to the script directory
GOOGLE_SA_FILE = _sa_env if os.path.isabs(_sa_env) else os.path.join(_SCRIPT_DIR, _sa_env)


# =============================================================================
# GOOGLE CALENDAR — direct API (bypasses n8n MCP)
# =============================================================================

def _resolve_sa_path():
    """Resolve service-account.json — try multiple locations."""
    # 1. Already resolved absolute path
    if os.path.isfile(GOOGLE_SA_FILE):
        return GOOGLE_SA_FILE
    # 2. Next to this script
    beside_script = os.path.join(_SCRIPT_DIR, "service-account.json")
    if os.path.isfile(beside_script):
        return beside_script
    # 3. Current working directory
    cwd_path = os.path.join(os.getcwd(), "service-account.json")
    if os.path.isfile(cwd_path):
        return cwd_path
    # Nothing found
    raise FileNotFoundError(
        f"service-account.json not found. Searched:\n"
        f"  1. {GOOGLE_SA_FILE}\n"
        f"  2. {beside_script}\n"
        f"  3. {cwd_path}\n"
        f"Place the file next to main.py ({_SCRIPT_DIR})"
    )

def _get_calendar_service():
    """Build Google Calendar API service using service account."""
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    sa_path = _resolve_sa_path()
    creds = service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

def _extract_time(s):
    """Extract hour:minute from a datetime string. Returns (hour, minute) or None if date-only."""
    if not s:
        return None
    s = s.strip()
    if len(s) <= 10:
        return None  # pure date like 2026-04-01
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00').replace('z', '+00:00'))
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            return None  # midnight = no explicit time
        return (dt.hour, dt.minute)
    except Exception:
        return None

def _date_only(s):
    """Extract just YYYY-MM-DD from any date/datetime string."""
    if not s:
        return None
    return s.strip()[:10]

def calendar_create_direct(summary, start, end, description=None):
    """Create a Google Calendar event. Returns {success, message, event_id}."""
    try:
        service = _get_calendar_service()
        start_time = _extract_time(start)
        end_time = _extract_time(end)

        if start_time:
            # User specified a real time → timed event
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            if end and end_time:
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            else:
                end_dt = start_dt + timedelta(hours=1)
            event_body = {
                'summary': summary,
                'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/Argentina/Buenos_Aires'},
                'end':   {'dateTime': end_dt.isoformat(),   'timeZone': 'America/Argentina/Buenos_Aires'},
            }
        else:
            # Date only → all-day event (no timezone issues)
            d = _date_only(start)
            end_d = _date_only(end) if end and end != start else None
            if end_d and end_d != d:
                # Multi-day: end is exclusive in Google API
                end_date = (datetime.fromisoformat(end_d) + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                # Single day
                end_date = (datetime.fromisoformat(d) + timedelta(days=1)).strftime('%Y-%m-%d')
            event_body = {
                'summary': summary,
                'start': {'date': d},
                'end':   {'date': end_date},
            }

        if description:
            event_body['description'] = description

        print(f"[CALENDAR] Creating: {json.dumps(event_body, default=str)}")
        created = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body).execute()
        eid = created.get('id', '')
        print(f"[CALENDAR] ✓ Created: {summary} → {created.get('htmlLink', '')}")
        return {"success": True, "message": f"Evento creado: {summary}", "event_id": eid}

    except Exception as e:
        print(f"[CALENDAR] ✗ Create failed: {e}")
        return {"success": False, "message": f"Calendar API error: {str(e)}", "event_id": ""}

def calendar_update_direct(event_id, start=None, end=None, summary=None):
    """Update an existing Google Calendar event. Returns {success, message}."""
    try:
        service = _get_calendar_service()
        event = service.events().get(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()

        if summary:
            event['summary'] = summary

        if start or end:
            start_time = _extract_time(start) if start else None
            end_time = _extract_time(end) if end else None

            if start_time:
                # Explicit time → timed event
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                if end and end_time:
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                else:
                    end_dt = start_dt + timedelta(hours=1)
                event['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': 'America/Argentina/Buenos_Aires'}
                event['end']   = {'dateTime': end_dt.isoformat(),   'timeZone': 'America/Argentina/Buenos_Aires'}
            else:
                # Date only → all-day event
                d = _date_only(start) if start else event['start'].get('date', _date_only(event['start'].get('dateTime', '')))
                end_date = (datetime.fromisoformat(d) + timedelta(days=1)).strftime('%Y-%m-%d')
                event['start'] = {'date': d}
                event['end']   = {'date': end_date}

        print(f"[CALENDAR] Updating {event_id}: start={event.get('start')} end={event.get('end')}")
        service.events().update(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id, body=event).execute()
        print(f"[CALENDAR] ✓ Updated event {event_id}")
        return {"success": True, "message": f"Evento {event_id} actualizado en Calendar"}

    except Exception as e:
        print(f"[CALENDAR] ✗ Update failed: {e}")
        return {"success": False, "message": f"Calendar API error: {str(e)}"}

# n8n MCP tool names
TOOL_CALENDAR = "Call_sub_google_calendar_"
TOOL_JIRA = "Call_sub_jira_issue_"
TOOL_DUEDATE = "Call_sub_jira_duedate_"
TOOL_SLACK = "Call_sub_slack_notify_"

# =============================================================================
# DATABASE — persistent mapping Jira ↔ Calendar
# =============================================================================

db = sqlite3.connect("haleph.db", check_same_thread=False)
db_lock = threading.Lock()

with db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS issue_calendar_map (
            issue_key TEXT PRIMARY KEY,
            calendar_event_id TEXT NOT NULL,
            summary TEXT,
            updated_at TEXT
        )
    """)

def map_issue_to_event(issue_key, event_id, summary=""):
    with db_lock:
        db.execute(
            "INSERT OR REPLACE INTO issue_calendar_map (issue_key, calendar_event_id, summary, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (issue_key, event_id, summary, datetime.now().isoformat()),
        )
        db.commit()

def get_event_for_issue(issue_key):
    with db_lock:
        row = db.execute(
            "SELECT calendar_event_id FROM issue_calendar_map WHERE issue_key = ?", (issue_key,)
        ).fetchone()
        return row[0] if row else None

def get_issue_for_event(event_id):
    with db_lock:
        row = db.execute(
            "SELECT issue_key FROM issue_calendar_map WHERE calendar_event_id = ?", (event_id,)
        ).fetchone()
        return row[0] if row else None

def get_all_mappings():
    with db_lock:
        rows = db.execute("SELECT issue_key, calendar_event_id, summary FROM issue_calendar_map").fetchall()
        return [{"issue_key": r[0], "calendar_event_id": r[1], "summary": r[2]} for r in rows]


# =============================================================================
# IN-MEMORY STATE
# =============================================================================

pending_events = deque(maxlen=100)
event_counter = 0
cached_jira_issues = []
cached_jira_timestamp = 0
JIRA_CACHE_TTL = 60
latest_graph = None
mcp_session = {"id": None}

# Anti-loop: IDs currently being synced
sync_in_progress = set()
sync_lock = threading.Lock()


# =============================================================================
# JIRA REST API — reading
# =============================================================================

def fetch_jira_issues(force=False):
    global cached_jira_issues, cached_jira_timestamp

    if not force and cached_jira_issues and (time.time() - cached_jira_timestamp < JIRA_CACHE_TTL):
        return cached_jira_issues

    if not JIRA_API_TOKEN:
        print("[WARN] No JIRA_API_TOKEN — returning cached/empty")
        return cached_jira_issues

    try:
        url = f"https://{JIRA_DOMAIN}/rest/api/3/search/jql"
        auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)

        response = requests.get(
            url=url,
            headers={"Accept": "application/json"},
            params={
                "jql": "status != Done ORDER BY created DESC",
                "startAt": 0,
                "maxResults": 50,
                "fields": "summary,status,assignee,priority,created,updated,"
                          "issuelinks,duedate,timeoriginalestimate,story_points,"
                          "customfield_10016,issuetype,description",
            },
            auth=auth,
            verify=False,
        )

        data = response.json()
        print(f"[DEBUG] Jira HTTP {response.status_code}")
        print(f"[DEBUG] Response keys: {list(data.keys())}")
        print(f"[DEBUG] Response preview: {json.dumps(data, ensure_ascii=False)[:500]}")

        if response.status_code != 200:
            print(f"[ERROR] Jira API {response.status_code}: {response.text[:200]}")
            return cached_jira_issues

        # The new /search/jql endpoint might use "issues" or "values"
        issues = data.get("issues") or data.get("values") or []
        cached_jira_issues = issues
        cached_jira_timestamp = time.time()
        print(f"[INFO] Fetched {len(issues)} Jira issues")
        return issues

    except Exception as e:
        print(f"[ERROR] Jira fetch: {e}")
        return cached_jira_issues


# =============================================================================
# JIRA REST API — direct writing (fallback when MCP fails)
# =============================================================================

def jira_update_issue_direct(issue_key, fields_update):
    if not JIRA_API_TOKEN:
        return {"success": False, "message": "No Jira credentials"}
    try:
        resp = requests.put(
            f"https://{JIRA_DOMAIN}/rest/api/3/issue/{issue_key}",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"fields": fields_update},
            auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN),
            verify=False,
        )
        if resp.status_code in (200, 204):
            return {"success": True, "message": f"{issue_key} actualizado"}
        return {"success": False, "message": f"Jira API {resp.status_code}: {resp.text[:150]}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def jira_create_issue_direct(summary, description="", assignee_id=None):
    if not JIRA_API_TOKEN:
        return {"success": False, "message": "No Jira credentials"}
    try:
        fields = {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "issuetype": {"name": "Task"},
        }
        if description:
            fields["description"] = {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
            }
        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}

        resp = requests.post(
            f"https://{JIRA_DOMAIN}/rest/api/3/issue",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"fields": fields},
            auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN),
            verify=False,
        )
        if resp.status_code in (200, 201):
            new_key = resp.json().get("key", "")
            return {"success": True, "message": f"Tarea creada: {new_key}", "key": new_key}
        return {"success": False, "message": f"Jira API {resp.status_code}: {resp.text[:150]}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# =============================================================================
# CONTEXT BUILDERS
# =============================================================================

def jira_issues_to_context(issues):
    if not issues:
        return None

    key_to_idx = {issue["key"]: i for i, issue in enumerate(issues)}
    all_tasks = []
    team_set = {}

    for issue in issues:
        fields = issue["fields"]
        deps, dependents = [], []
        for link in fields.get("issuelinks", []):
            if "inwardIssue" in link and link["type"]["inward"] == "is blocked by":
                bk = link["inwardIssue"]["key"]
                if bk in key_to_idx:
                    deps.append(bk)
            if "outwardIssue" in link and link["type"]["outward"] == "blocks":
                bk = link["outwardIssue"]["key"]
                if bk in key_to_idx:
                    dependents.append(bk)

        assignee = fields.get("assignee") or {}
        a_id = assignee.get("accountId", "unassigned")
        a_name = assignee.get("displayName", "Sin asignar")
        a_email = assignee.get("emailAddress", a_id)

        jira_status = (fields.get("status", {}).get("name", "To Do")).lower()
        status = {"to do": "todo", "backlog": "todo", "in progress": "in_progress",
                  "in review": "in_progress", "done": "done", "closed": "done"}.get(jira_status, "todo")

        cal_event = get_event_for_issue(issue["key"]) or ""

        all_tasks.append({
            "id": issue["key"],
            "name": fields.get("summary", ""),
            "status": status,
            "assignee": a_email,
            "assignee_name": a_name,
            "assignee_id": a_id,
            "estimated_days": estimate_days(fields),
            "start_date": "",
            "due_date": fields.get("duedate") or "",
            "dependencies": deps,
            "dependents": dependents,
            "calendar_event_id": cal_event,
        })

        if a_id != "unassigned":
            team_set[a_id] = {"email": a_email, "name": a_name, "account_id": a_id, "available_days": 5}

    return {
        "sprint": {"id": "current", "name": "Sprint actual",
                   "deadline": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")},
        "all_tasks": all_tasks,
        "team_members": list(team_set.values()),
    }


def build_graph_from_context(context):
    if not context or not context.get("all_tasks"):
        return None

    tasks = context["all_tasks"]
    n = len(tasks)
    cols = max(3, int(n ** 0.5) + 1)

    nodes = []
    for i, t in enumerate(tasks):
        col, row = i % cols, i // cols
        total_rows = (n // cols) + 1
        nodes.append({
            "id": t["id"],
            "label": t["name"][:30],
            "status": {"done": "done", "in_progress": "progress"}.get(t["status"], "todo"),
            "x": round((col + 0.5) / cols, 3),
            "y": round((row + 0.5) / total_rows, 3) if total_rows > 0 else 0.5,
        })

    edges = [{"from": dep, "to": t["id"]} for t in tasks for dep in t.get("dependencies", [])]
    return {"nodes": nodes, "edges": edges}


def get_calendar_events_context():
    """Fetch upcoming Calendar events for cross-app context."""
    try:
        service = _get_calendar_service()
        now = datetime.utcnow().isoformat() + "Z"
        result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=now,
            maxResults=30,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for ev in result.get("items", []):
            start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
            end = ev.get("end", {}).get("dateTime", ev.get("end", {}).get("date", ""))
            linked_issue = get_issue_for_event(ev.get("id", ""))
            events.append({
                "event_id": ev.get("id", ""),
                "summary": ev.get("summary", ""),
                "start": start,
                "end": end,
                "linked_jira_issue": linked_issue or "",
            })
        return events
    except Exception as e:
        print(f"[WARN] Calendar context fetch failed: {e}")
        return []


def build_cascade_hint(issue_key, changed_fields, context):
    """Build a human-readable hint about potential cross-app effects."""
    hints = []

    # Check if this issue has a linked Calendar event
    cal_event = get_event_for_issue(issue_key)
    if cal_event:
        hints.append("tiene evento en Calendar")

    # Check for dependent tasks
    if context and context.get("all_tasks"):
        dependents = []
        for t in context["all_tasks"]:
            if issue_key in t.get("dependencies", []):
                dependents.append(t["id"])
        if dependents:
            hints.append(f"bloquea a {', '.join(dependents)}")

    if not hints:
        return ""

    return f"⚡ Click para analizar impacto — {'; '.join(hints)}"


# =============================================================================
# CLAUDE API
# =============================================================================

def call_claude_for_plan(prompt_text, context):
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not configured"}

    tasks_for_algo = []
    id_to_index = {task["id"]: i for i, task in enumerate(context["all_tasks"])}
    for task in context["all_tasks"]:
        tasks_for_algo.append({
            "name": task["name"],
            "deps": [id_to_index[d] for d in task.get("dependencies", []) if d in id_to_index],
            "days": task.get("estimated_days", 2),
        })

    timeline, task_parts = get_task_timeline(tasks_for_algo)
    index_to_id = {i: task["id"] for i, task in enumerate(context["all_tasks"])}
    timeline_jira = [[index_to_id[task_parts[idx]] for idx in day] for day in timeline]

    order_before = [task["id"] for task in context["all_tasks"]]
    order_after, seen = [], set()
    for day in timeline_jira:
        for tid in day:
            if tid not in seen:
                order_after.append(tid)
                seen.add(tid)

    payload_claude = {
        "user_request": prompt_text,
        "context": context,
        "calendar_events": get_calendar_events_context(),
        "issue_calendar_mappings": get_all_mappings(),
        "computed_timeline": timeline_jira,
        "task_order": {"before": order_before, "after": order_after},
    }

    claude_response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 2048,
            "system": (
                "Sos un orquestador de proyectos de software llamado HALeph. "
                "Tu diferencial clave es que razonas ENTRE apps: los cambios en una app "
                "desencadenan efectos en las demas. No operas en silos. "
                "\n\n"
                "APPS CONECTADAS: Jira (tareas), Google Calendar (eventos), Slack (notificaciones). "
                "El contexto incluye: tareas de Jira con sus dependencias, eventos de Calendar, "
                "y los mapeos entre issues de Jira y eventos de Calendar (issue_calendar_mappings). "
                "\n\n"
                "REGLA FUNDAMENTAL — EFECTOS EN CASCADA: "
                "Cuando el usuario reporta un cambio o atraso: "
                "1) Analiza las dependencias en Jira: que otras tareas se ven afectadas? "
                "2) Analiza Calendar: hay eventos vinculados que hay que mover? "
                "   Usa el campo calendar_event_id de cada tarea, o los issue_calendar_mappings. "
                "3) Notifica via Slack a los afectados. "
                "4) Si una tarea bloqueante se atrasa, TODAS las dependientes se mueven en cadena. "
                "   Incluye acciones para CADA tarea y evento afectado, no solo el que cambio. "
                "\n\n"
                "Cuando el usuario pide 'analizar impacto' o 'efectos en cascada': "
                "examina exhaustivamente que mas se ve afectado en TODAS las apps y propone "
                "el conjunto completo de cambios necesarios. "
                "\n\n"
                "Tipos de accion validos: "
                "update_calendar_event (params: new_start como YYYY-MM-DD, new_end opcional como YYYY-MM-DD), "
                "update_jira_issue (params: new_assignee como accountId, o new_status), "
                "update_jira_duedate (params: due_date como YYYY-MM-DD), "
                "notify_slack (params: message), "
                "create_jira_issue (params: summary, description, assignee, start, end), "
                "create_calendar_event (params: summary, start como YYYY-MM-DD, end opcional como YYYY-MM-DD). "
                "Usa target_id para el ID del issue (KAN-1) o evento calendar. "
                "\n\n"
                "Si el usuario pide un plan completo, usa response_type:'plan' con phases. "
                "Siempre genera el summary en espanol."
            ),
            "messages": [
                {"role": "user", "content": json.dumps(payload_claude, ensure_ascii=False)},
            ],
            "tools": [
                {
                    "name": "propose_plan",
                    "description": "Propone un plan de acciones para responder al pedido del usuario",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "response_type": {
                                "type": "string",
                                "enum": ["adjust", "plan"],
                            },
                            "summary": {"type": "string"},
                            "actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": [
                                                "update_calendar_event",
                                                "update_jira_issue",
                                                "update_jira_duedate",
                                                "notify_slack",
                                                "create_jira_issue",
                                                "create_calendar_event",
                                            ],
                                        },
                                        "target_id": {"type": "string"},
                                        "params": {"type": "object"},
                                    },
                                    "required": ["type", "target_id", "params"],
                                },
                            },
                            "phases": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "tasks": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "title": {"type": "string"},
                                                    "assignee": {"type": "string"},
                                                    "date": {"type": "string"},
                                                },
                                            },
                                        },
                                        "note": {"type": "string"},
                                    },
                                },
                            },
                            "warnings": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["response_type", "summary", "actions"],
                    },
                }
            ],
            "tool_choice": {"type": "tool", "name": "propose_plan"},
        },
        verify=False,
    )

    if claude_response.status_code != 200:
        print(f"[ERROR] Claude {claude_response.status_code}: {claude_response.text[:300]}")
        return {"error": f"Claude API error {claude_response.status_code}"}

    data = claude_response.json()
    plan = next(
        (block["input"] for block in data.get("content", []) if block.get("name") == "propose_plan"),
        None,
    )
    if plan is None:
        text = " ".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return {"summary": text or "No se pudo generar un plan.", "actions": [], "warnings": []}
    return plan


# =============================================================================
# MCP — n8n JSON-RPC over SSE
# =============================================================================

def mcp_call(method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if mcp_session["id"]:
        headers["mcp-session-id"] = mcp_session["id"]

    try:
        resp = requests.post(MCP_SERVER_URL, json=payload, headers=headers,
                             verify=False, stream=True, timeout=30)
        if "mcp-session-id" in resp.headers:
            mcp_session["id"] = resp.headers["mcp-session-id"]

        result_text = ""
        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            if decoded.startswith("data:"):
                result_text = decoded[len("data:"):].strip()
                break

        if not result_text:
            return {"error": f"HTTP {resp.status_code} — no data"}
        return json.loads(result_text)

    except Exception as e:
        print(f"[ERROR] MCP: {e}")
        return {"error": str(e)}


def ensure_mcp_session():
    if mcp_session["id"]:
        return True

    print("[INFO] Initializing MCP session...")
    mcp_call("initialize", {
        "protocolVersion": "2024-11-05",
        "clientInfo": {"name": "haleph-backend", "version": "3.0"},
        "capabilities": {},
    })

    if not mcp_session["id"]:
        print("[ERROR] MCP init failed — no session ID")
        return False

    print(f"[INFO] MCP connected — session: {mcp_session['id'][:12]}...")
    mcp_call("notifications/initialized")

    tools_resp = mcp_call("tools/list")
    available = tools_resp.get("result", {}).get("tools", [])
    print(f"[INFO] MCP tools: {sorted(t['name'] for t in available)}")
    return True


# =============================================================================
# ACTION EXECUTION — MCP first, direct API fallback
# =============================================================================

def _mcp_ok(result):
    if not isinstance(result, dict):
        return False
    if result.get("error"):
        return False
    r = result.get("result", {})
    if isinstance(r, dict) and r.get("isError"):
        return False
    return True

def _mcp_err(result):
    if not isinstance(result, dict):
        return str(result)
    err = result.get("error")
    if isinstance(err, dict):
        return err.get("message", str(err))
    if err:
        return str(err)
    r = result.get("result", {})
    if isinstance(r, dict) and r.get("isError"):
        content = r.get("content", [])
        if content and isinstance(content[0], dict):
            return content[0].get("text", str(r))
    return "Unknown error"

def _extract_id_from_result(mcp_result, *keys):
    try:
        content = mcp_result.get("result", {}).get("content", [])
        for block in content:
            text = block.get("text", "")
            if text:
                data = json.loads(text)
                for k in keys:
                    if data.get(k):
                        return data[k]
    except Exception:
        pass
    return None


def execute_action(action):
    action_type = action.get("type", "")
    target_id = action.get("target_id", "")
    params = action.get("params", {})

    try:
        # ── Calendar update ──
        if action_type == "update_calendar_event":
            print(f"[INFO] Updating Calendar event via direct API: {target_id}")
            return calendar_update_direct(
                event_id=target_id,
                start=params.get("new_start"),
                end=params.get("new_end"),
                summary=params.get("summary"),
            )

        # ── Calendar create ──
        elif action_type == "create_calendar_event":
            print(f"[INFO] Creating Calendar event via direct API: {params.get('summary', '')}")
            r = calendar_create_direct(
                summary=params.get("summary", ""),
                start=params.get("start", ""),
                end=params.get("end", params.get("start", "")),
                description=params.get("description"),
            )
            # Map to Jira issue if target_id is an issue key
            if r["success"] and r.get("event_id") and target_id:
                map_issue_to_event(target_id, r["event_id"], params.get("summary", ""))
            return r

        # ── Jira update ── (direct API — n8n MCP returns false success)
        elif action_type == "update_jira_issue":
            print(f"[INFO] Updating Jira issue via direct API: {target_id}")
            fields = {}
            if params.get("new_assignee"):
                fields["assignee"] = {"accountId": params["new_assignee"]}
            if params.get("new_status"):
                # Status changes need transitions API, not fields update
                fields["status_note"] = params["new_status"]
            if not fields:
                return {"success": False, "message": f"No fields to update for {target_id}"}
            return jira_update_issue_direct(target_id, fields)

        # ── Jira due date ── (direct API — n8n MCP returns false success)
        elif action_type == "update_jira_duedate":
            print(f"[INFO] Updating Jira due date via direct API: {target_id} → {params.get('due_date', '')}")
            r = jira_update_issue_direct(target_id, {"duedate": params.get("due_date", "")})
            if r["success"]:
                _sync_jira_date_to_calendar_async(target_id, params.get("due_date", ""))
            return r

        # ── Slack ──
        elif action_type == "notify_slack":
            result = mcp_call("tools/call", {
                "name": TOOL_SLACK,
                "arguments": {"input": json.dumps({"message": params.get("message", "")})},
            })
            if _mcp_ok(result):
                return {"success": True, "message": "Equipo notificado en Slack"}
            return {"success": False, "message": f"Slack MCP: {_mcp_err(result)}"}

        # ── Jira create ──
        elif action_type == "create_jira_issue":
            # Direct API first — n8n MCP sub-workflow doesn't support create reliably
            print(f"[INFO] Creating Jira issue via direct API: {params.get('summary', '')}")
            r = jira_create_issue_direct(
                params.get("summary", "Nueva tarea"),
                params.get("description", ""),
                params.get("assignee"),
            )

            if not r["success"]:
                return r

            new_key = r.get("key", "")
            msg = r["message"]

            # Auto-create Calendar event for new Jira issue
            if new_key and params.get("start"):
                threading.Thread(
                    target=_auto_create_calendar_for_issue,
                    args=(new_key, params.get("summary", ""), params.get("start", ""),
                          params.get("end", params.get("start", ""))),
                    daemon=True,
                ).start()

            return {"success": True, "message": msg}

        else:
            return {"success": False, "message": f"Tipo desconocido: {action_type}"}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


# =============================================================================
# BIDIRECTIONAL SYNC
# =============================================================================

def _sync_jira_date_to_calendar_async(issue_key, due_date):
    if due_date:
        threading.Thread(target=_sync_jira_date_to_calendar,
                         args=(issue_key, due_date), daemon=True).start()

def _sync_jira_date_to_calendar(issue_key, due_date):
    if not due_date:
        return
    with sync_lock:
        if issue_key in sync_in_progress:
            return
        sync_in_progress.add(issue_key)
    try:
        cal_event_id = get_event_for_issue(issue_key)
        if not cal_event_id:
            print(f"[SYNC] No Calendar mapped for {issue_key}")
            return

        print(f"[SYNC] Jira→Cal: {issue_key} → event {cal_event_id} date={due_date}")
        # Use date-only so it stays as an all-day event (no timezone shift)
        r = calendar_update_direct(event_id=cal_event_id, start=due_date[:10])

        if r["success"]:
            print(f"[SYNC] ✓ Calendar {cal_event_id} updated")
            queue_event("haleph", f"Calendar sincronizado: {issue_key} → {due_date}",
                        {"issue_key": issue_key, "calendar_event_id": cal_event_id, "sync": True})
        else:
            print(f"[SYNC] ✗ Calendar update failed: {r['message']}")
    finally:
        with sync_lock:
            sync_in_progress.discard(issue_key)


def _sync_calendar_date_to_jira(event_id, new_start, summary=""):
    with sync_lock:
        if event_id in sync_in_progress:
            return
        sync_in_progress.add(event_id)
    try:
        issue_key = get_issue_for_event(event_id)
        if not issue_key:
            print(f"[SYNC] No Jira mapped for event {event_id}")
            return

        due_date = new_start[:10] if new_start else ""
        if not due_date:
            return

        print(f"[SYNC] Cal→Jira: event {event_id} → {issue_key} due={due_date}")

        r = jira_update_issue_direct(issue_key, {"duedate": due_date})
        if r["success"]:
            print(f"[SYNC] ✓ Jira {issue_key} updated to {due_date}")
        else:
            print(f"[SYNC] ✗ Jira update failed: {r['message']}")

        queue_event("haleph", f"Jira sincronizado: {issue_key} deadline → {due_date}",
                    {"issue_key": issue_key, "calendar_event_id": event_id, "sync": True})
    finally:
        with sync_lock:
            sync_in_progress.discard(event_id)


def _auto_create_calendar_for_issue(issue_key, summary, start, end):
    print(f"[SYNC] Auto-creating Calendar for {issue_key}: '{summary}'")
    r = calendar_create_direct(
        summary=f"[{issue_key}] {summary}",
        start=start,
        end=end,
    )
    if r["success"] and r.get("event_id"):
        map_issue_to_event(issue_key, r["event_id"], summary)
        print(f"[SYNC] ✓ Mapped {issue_key} ↔ {r['event_id']}")
        queue_event("haleph", f"Evento Calendar auto-creado para {issue_key}",
                    {"issue_key": issue_key, "calendar_event_id": r["event_id"], "sync": True})
    else:
        print(f"[SYNC] ✗ Auto-create failed: {r['message']}")


# =============================================================================
# EVENT QUEUE
# =============================================================================

def queue_event(source, message, data=None):
    global event_counter
    event_counter += 1
    pending_events.append({
        "id": f"evt_{event_counter:04d}",
        "source": source,
        "message": message,
        "data": data or {},
        "timestamp": datetime.now().isoformat(),
    })


# =============================================================================
# FLASK ROUTES
# =============================================================================

@app.route("/")
def index():
    return jsonify({"status": "ok", "service": "HALeph Backend", "version": "3.0"})


@app.route("/prompt", methods=["POST"])
@app.route("/report-delay", methods=["POST"])
def handle_prompt():
    global latest_graph

    body = request.get_json(silent=True) or {}
    prompt_text = body.get("prompt", "")
    if not prompt_text:
        return jsonify({"error": "No prompt provided"}), 400

    print(f"\n[PROMPT] {prompt_text}")

    issues = fetch_jira_issues(force=True)
    context = jira_issues_to_context(issues)

    if not context or not context["all_tasks"]:
        return jsonify({
            "summary": "No se encontraron tareas en Jira. Verificá la conexión y las credenciales.",
            "actions": [], "warnings": ["Sin conexión a Jira o sin tareas activas"],
        }), 200

    plan = call_claude_for_plan(prompt_text, context)

    if "error" in plan:
        return jsonify({
            "summary": f"Error al generar plan: {plan['error']}",
            "actions": [], "warnings": [plan["error"]],
        }), 200

    graph = build_graph_from_context(context)
    latest_graph = graph

    response_data = {
        "summary": plan.get("summary", ""),
        "actions": plan.get("actions", []),
        "warnings": plan.get("warnings", []),
        "dependency_graph": graph,
    }

    if plan.get("response_type") == "plan":
        response_data["type"] = "plan"
        response_data["phases"] = plan.get("phases", [])

    print(f"[PLAN] {len(response_data['actions'])} actions, type={response_data.get('type', 'adjust')}")
    return jsonify(response_data), 200


@app.route("/execute-plan", methods=["POST"])
def execute_plan():
    body = request.get_json(silent=True) or {}
    actions = body.get("actions", [])
    if not actions:
        return jsonify({"results": []}), 200

    print(f"\n[EXECUTE] {len(actions)} actions")
    ensure_mcp_session()

    results = []
    for i, action in enumerate(actions):
        print(f"  [{i+1}/{len(actions)}] {action.get('type')} → {action.get('target_id', '')}")
        result = execute_action(action)
        results.append(result)
        print(f"    → {'✓' if result['success'] else '✗'} {result['message']}")

    success_count = sum(1 for r in results if r["success"])
    queue_event("haleph", f"Plan ejecutado: {success_count}/{len(results)} acciones exitosas",
                {"actions_count": len(results), "success_count": success_count})

    threading.Thread(target=fetch_jira_issues, kwargs={"force": True}, daemon=True).start()
    return jsonify({"results": results}), 200


@app.route("/pending-events", methods=["GET"])
def get_pending_events():
    events = list(pending_events)
    pending_events.clear()
    return jsonify({"events": events}), 200


@app.route("/team-status", methods=["GET"])
def team_status():
    issues = fetch_jira_issues()
    if not issues:
        return jsonify({"members": []}), 200

    members_map = {}
    for issue in issues:
        fields = issue["fields"]
        assignee = fields.get("assignee") or {}
        a_id = assignee.get("accountId", "unassigned")

        if a_id not in members_map:
            members_map[a_id] = {
                "name": assignee.get("displayName", "Sin asignar"),
                "role": "",
                "tasks": [],
            }

        members_map[a_id]["tasks"].append({
            "id": issue["key"],
            "title": fields.get("summary", ""),
            "status": fields.get("status", {}).get("name", "To Do"),
            "source": "jira",
        })

    members = sorted(members_map.values(), key=lambda m: len(m["tasks"]), reverse=True)
    return jsonify({"members": members}), 200


@app.route("/graph-data", methods=["GET"])
def graph_data():
    global latest_graph

    # Always fetch fresh from Jira to avoid stale/deleted nodes
    fresh = request.args.get("fresh", "0")
    if fresh == "1" or not latest_graph:
        issues = fetch_jira_issues(force=True)
        context = jira_issues_to_context(issues)
        graph = build_graph_from_context(context)
        if graph:
            latest_graph = graph
            return jsonify(graph), 200
        return jsonify({"nodes": [], "edges": []}), 200

    return jsonify(latest_graph), 200


@app.route("/incoming-event", methods=["POST"])
def incoming_event():
    body = request.get_json(silent=True) or {}
    source = body.get("source", "unknown")
    event_type = body.get("event_type", "")
    data = body.get("data", {})

    print(f"[EVENT] {source}/{event_type}: {json.dumps(data, ensure_ascii=False)[:200]}")

    if source == "jira":
        issue_key = data.get("issue_key", "")
        summary = data.get("summary", "")
        changed = data.get("changed_fields", {})
        changes_str = ", ".join(
            f"{k}: {v.get('from', '?')} → {v.get('to', '?')}" if isinstance(v, dict) else f"{k}: {v}"
            for k, v in changed.items()
        )
        message = f"{issue_key} {summary} — {changes_str}" if changes_str else f"{issue_key} {summary} actualizado"

        # Bidirectional: due date → Calendar
        if "duedate" in changed or "due date" in changed:
            new_date = changed.get("duedate", changed.get("due date", {}))
            if isinstance(new_date, dict):
                new_date = new_date.get("to", "")
            if new_date:
                threading.Thread(target=_sync_jira_date_to_calendar,
                                 args=(issue_key, new_date), daemon=True).start()

        # Cascade hint for frontend
        context = jira_issues_to_context(cached_jira_issues)
        data["cascade_hint"] = build_cascade_hint(issue_key, changed, context)
        data["changed_fields"] = changed

        threading.Thread(target=fetch_jira_issues, kwargs={"force": True}, daemon=True).start()

    elif source == "google_calendar":
        event_title = data.get("summary", data.get("title", ""))
        event_id = data.get("event_id", data.get("id", ""))
        new_start = data.get("start", data.get("new_start", ""))

        linked_issue = get_issue_for_event(event_id)
        message = f"Evento Calendar '{event_title}' modificado"
        if linked_issue:
            data["issue_key"] = linked_issue
            data["cascade_hint"] = f"⚡ Click para analizar impacto — vinculado a {linked_issue}"

        # Bidirectional: Calendar → Jira
        if new_start and event_id:
            threading.Thread(target=_sync_calendar_date_to_jira,
                             args=(event_id, new_start, event_title), daemon=True).start()
    else:
        message = body.get("message", f"Evento de {source}")

    queue_event(source, message, data)
    return jsonify({"status": "ok"}), 200


@app.route("/jira_webhook", methods=["POST"])
def jira_webhook():
    body = request.get_json(silent=True) or {}
    event_name = body.get("webhookEvent", "unknown")
    issue = body.get("issue", {})
    issue_key = issue.get("key", "")
    summary = issue.get("fields", {}).get("summary", "")
    changelog = body.get("changelog", {})

    print(f"[JIRA WEBHOOK] {event_name}: {issue_key} — {summary}")

    changed_fields = {}
    for item in changelog.get("items", []):
        changed_fields[item.get("field", "")] = {
            "from": item.get("fromString", ""),
            "to": item.get("toString", ""),
        }

    if changed_fields:
        changes_str = ", ".join(f"{k}: {v['from']} → {v['to']}" for k, v in changed_fields.items())
        message = f"{issue_key} — {changes_str}"
    else:
        message = f"{issue_key} {summary} ({event_name.replace('jira:', '')})"

    # Build cascade hint
    context = jira_issues_to_context(cached_jira_issues)
    cascade_hint = build_cascade_hint(issue_key, changed_fields, context)

    queue_event("jira", message, {
        "issue_key": issue_key, "summary": summary,
        "changed_fields": changed_fields, "webhook_event": event_name,
        "cascade_hint": cascade_hint,
    })

    # Bidirectional: due date → Calendar
    if "duedate" in changed_fields:
        new_date = changed_fields["duedate"]["to"]
        if new_date:
            threading.Thread(target=ensure_mcp_session, daemon=True).start()
            threading.Thread(target=_sync_jira_date_to_calendar,
                             args=(issue_key, new_date), daemon=True).start()

    # Status change notification
    if "status" in changed_fields:
        new_status = changed_fields["status"]["to"]
        if new_status.lower() in ("done", "closed"):
            queue_event("haleph", f"{issue_key} completada",
                        {"issue_key": issue_key, "new_status": new_status, "sync": True})

    global cached_jira_timestamp, latest_graph
    cached_jira_timestamp = 0
    latest_graph = None

    return jsonify({"status": "ok"}), 200


@app.route("/calendar_webhook", methods=["POST"])
def calendar_webhook():
    body = request.get_json(silent=True) or {}
    print(f"[CALENDAR WEBHOOK] {json.dumps(body, ensure_ascii=False)[:300]}")

    event_title = body.get("summary", body.get("title", body.get("data", {}).get("summary", "evento")))
    event_id = body.get("event_id", body.get("id", body.get("data", {}).get("id", "")))
    new_start = body.get("start", body.get("data", {}).get("start", ""))

    if isinstance(new_start, dict):
        new_start = new_start.get("dateTime", new_start.get("date", ""))

    message = f"Evento '{event_title}' modificado en Calendar"
    queue_event("google_calendar", message, {
        "event_id": event_id, "summary": event_title, "new_start": new_start,
    })

    # Bidirectional: Calendar → Jira
    if event_id and new_start:
        threading.Thread(target=ensure_mcp_session, daemon=True).start()
        threading.Thread(target=_sync_calendar_date_to_jira,
                         args=(event_id, new_start, event_title), daemon=True).start()

    return jsonify({"status": "ok"}), 200


# ── Manual mapping ──

@app.route("/map-issue-event", methods=["POST"])
def map_issue_event():
    body = request.get_json(silent=True) or {}
    issue_key = body.get("issue_key", "")
    event_id = body.get("calendar_event_id", "")
    if not issue_key or not event_id:
        return jsonify({"error": "issue_key and calendar_event_id required"}), 400
    map_issue_to_event(issue_key, event_id, body.get("summary", ""))
    return jsonify({"status": "ok"}), 200

@app.route("/mappings", methods=["GET"])
def list_mappings():
    return jsonify({"mappings": get_all_mappings()}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok", "version": "3.0",
        "jira_connected": bool(JIRA_API_TOKEN),
        "claude_connected": bool(ANTHROPIC_API_KEY),
        "mcp_session": bool(mcp_session["id"]),
        "pending_events": len(pending_events),
        "cached_issues": len(cached_jira_issues),
        "mappings": len(get_all_mappings()),
    }), 200


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  HALeph Backend v3.0")
    print("=" * 60)
    print(f"  Jira:     {'✓' if JIRA_API_TOKEN else '✗'} {JIRA_DOMAIN}")
    print(f"  Claude:   {'✓' if ANTHROPIC_API_KEY else '✗'}")
    try:
        _sa_resolved = _resolve_sa_path()
        print(f"  Calendar: ✓ {_sa_resolved}")
    except FileNotFoundError as _e:
        print(f"  Calendar: ✗ {_e}")
    print(f"  MCP:      {MCP_SERVER_URL[:50]}...")
    print(f"  Mappings: {len(get_all_mappings())} Jira↔Calendar links")
    print("=" * 60)

    app.run(host="0.0.0.0", port=3000, debug=True)