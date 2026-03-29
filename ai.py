"""
Calendar Sync Orchestrator
--------------------------
1. Uses Claude AI to assign people to AFTER tasks based on the BEFORE assignments + team list.
2. Fetches all events from Google Calendar via MCP.
3. Uses Claude AI again to diff tasks vs calendar events and decide what to add / update / delete.
4. Executes those calendar actions via MCP.

Dependencies: requests, python-dateutil
Environment:  ANTHROPIC_API_KEY must be set.
"""

import uuid
import json
from dotenv import load_dotenv
import os
import requests
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG  ── edit these values
# ─────────────────────────────────────────────
MCP_SERVER_URL = "https://iandib.app.n8n.cloud/mcp/101a48e4-4bd9-46dc-8e6b-d5d225c593c5"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

ANTHROPIC_HEADERS = {
    "x-api-key": ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "Content-Type": "application/json",
}

# ─────────────────────────────────────────────
# MCP SESSION STATE
# ─────────────────────────────────────────────
_mcp_session: dict = {"id": None}


# ─────────────────────────────────────────────
# LOW-LEVEL MCP HELPER
# ─────────────────────────────────────────────
def mcp_call(method: str, params: dict | None = None) -> dict:
    """Send a JSON-RPC 2.0 request to the MCP server and return the parsed result."""
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
    if _mcp_session["id"]:
        headers["mcp-session-id"] = _mcp_session["id"]

    resp = requests.post(
        MCP_SERVER_URL,
        json=payload,
        headers=headers,
        verify=False,
        stream=True,
    )

    # Persist session ID before consuming the stream
    if "mcp-session-id" in resp.headers:
        _mcp_session["id"] = resp.headers["mcp-session-id"]

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


# ─────────────────────────────────────────────
# MCP INITIALISATION
# ─────────────────────────────────────────────
def mcp_init() -> set[str]:
    """
    Initialise the MCP connection and return the set of available tool names.
    Safe to call multiple times (re-uses the existing session).
    """
    if _mcp_session["id"] is None:
        print("Connecting to MCP server…")
        mcp_call("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "calendar-orchestrator", "version": "1.0"},
            "capabilities": {},
        })
        mcp_call("notifications/initialized")
        short = _mcp_session["id"][:8] if _mcp_session["id"] else "???"
        print(f"MCP connected — session: {short}…")

    tools_resp = mcp_call("tools/list")
    available = tools_resp.get("result", {}).get("tools", [])
    names = {t["name"] for t in available}
    print(f"MCP tools available: {sorted(names)}")
    return names


# ─────────────────────────────────────────────
# CALENDAR MCP HELPERS
# ─────────────────────────────────────────────
def _find_calendar_tool(tool_names: set[str], suffix: str) -> str | None:
    """Return the first tool name that contains the given suffix."""
    for name in tool_names:
        if suffix.lower() in name.lower():
            return name
    return None


def calendar_list_events(tool_name: str, calendar_id: str = "primary",
                          time_min: str | None = None,
                          time_max: str | None = None) -> list[dict]:
    """Fetch events from Google Calendar and return a flat list."""
    args: dict = {"input": json.dumps({
        "operation": "list",
        "calendar_id": calendar_id,
        **({"time_min": time_min} if time_min else {}),
        **({"time_max": time_max} if time_max else {}),
    })}
    result = mcp_call("tools/call", {"name": tool_name, "arguments": args})
    # Normalise — the MCP wrapper may nest the list differently
    content = result.get("result", result)
    if isinstance(content, list):
        return content
    if isinstance(content, dict):
        return content.get("events", content.get("items", []))
    return []


def calendar_create_event(tool_name: str, summary: str, start: str, end: str,
                           description: str = "", calendar_id: str = "primary") -> dict:
    args = {"input": json.dumps({
        "operation": "create",
        "calendar_id": calendar_id,
        "summary": summary,
        "start": start,
        "end": end,
        "description": description,
    })}
    return mcp_call("tools/call", {"name": tool_name, "arguments": args})


def calendar_update_event(tool_name: str, event_id: str, summary: str,
                           start: str, end: str, description: str = "",
                           calendar_id: str = "primary") -> dict:
    args = {"input": json.dumps({
        "operation": "update",
        "calendar_id": calendar_id,
        "event_id": event_id,
        "summary": summary,
        "start": start,
        "end": end,
        "description": description,
    })}
    return mcp_call("tools/call", {"name": tool_name, "arguments": args})


def calendar_delete_event(tool_name: str, event_id: str,
                           calendar_id: str = "primary") -> dict:
    args = {"input": json.dumps({
        "operation": "delete",
        "calendar_id": calendar_id,
        "event_id": event_id,
    })}
    return mcp_call("tools/call", {"name": tool_name, "arguments": args})


# ─────────────────────────────────────────────
# CLAUDE AI HELPERS
# ─────────────────────────────────────────────
def _claude(system: str, user_content: str, tools: list | None = None,
            tool_choice: dict | None = None) -> dict:
    """Thin wrapper around the Anthropic /v1/messages endpoint."""
    body: dict = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2048,
        "system": system,
        "messages": [{"role": "user", "content": user_content}],
    }
    if tools:
        body["tools"] = tools
    if tool_choice:
        body["tool_choice"] = tool_choice

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=ANTHROPIC_HEADERS,
        json=body,
        verify=False,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_tool_input(response: dict, tool_name: str) -> dict:
    """Pull the input dict from a tool_use content block."""
    for block in response.get("content", []):
        if block.get("type") == "tool_use" and block.get("name") == tool_name:
            return block.get("input", {})
    raise ValueError(f"Tool '{tool_name}' not found in Claude response:\n"
                     + json.dumps(response, indent=2))


# ─────────────────────────────────────────────
# STEP 1 — ASSIGN PEOPLE TO AFTER TASKS
# ─────────────────────────────────────────────
_ASSIGN_TOOL = {
    "name": "assign_tasks",
    "description": (
        "Assign team members to each task in the AFTER timeline. "
        "Preserve existing assignments from BEFORE where sensible, "
        "balance workload, and respect each person's concurrent task load."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the assignment decisions.",
            },
            "assignments": {
                "type": "array",
                "description": "One entry per (day, task) slot in the AFTER timeline.",
                "items": {
                    "type": "object",
                    "properties": {
                        "day":      {"type": "integer"},
                        "task_id":  {"type": "string"},
                        "assignee": {"type": "string"},
                    },
                    "required": ["day", "task_id", "assignee"],
                },
            },
        },
        "required": ["reasoning", "assignments"],
    },
}


def assign_people_to_tasks(
    timeline_before: dict[int, list[dict]],
    timeline_after:  dict[int, list[dict]],
    team:            list[str],
) -> dict:
    """
    Ask Claude to assign team members to all tasks in `timeline_after`.

    Parameters
    ----------
    timeline_before : {day: [{"task_id": str, "assignee": str}, ...]}
    timeline_after  : {day: [{"task_id": str}, ...]}   ← no assignees yet
    team            : list of names available

    Returns
    -------
    {"reasoning": str, "assignments": [{"day": int, "task_id": str, "assignee": str}]}
    """
    prompt = json.dumps({
        "team_members": team,
        "timeline_before": {str(k): v for k, v in timeline_before.items()},
        "timeline_after":  {str(k): v for k, v in timeline_after.items()},
    }, ensure_ascii=False, indent=2)

    system = (
        "You are a project manager. "
        "Given a BEFORE timeline (tasks with current assignees) and an AFTER timeline "
        "(reordered/modified tasks without assignees), assign team members to every task "
        "in the AFTER timeline. Rules:\n"
        "• Reuse existing assignments where possible.\n"
        "• Balance the workload — no one person should be overloaded on any single day.\n"
        "• Only use names from the provided team_members list.\n"
        "• A task that appears on multiple consecutive days should keep the same assignee.\n"
        "Use the assign_tasks tool to return your answer."
    )

    response = _claude(system, prompt, tools=[_ASSIGN_TOOL],
                        tool_choice={"type": "tool", "name": "assign_tasks"})
    return _extract_tool_input(response, "assign_tasks")


# ─────────────────────────────────────────────
# STEP 2 — DIFF TASKS VS CALENDAR EVENTS
# ─────────────────────────────────────────────
_SYNC_TOOL = {
    "name": "sync_calendar",
    "description": (
        "Produce a list of calendar actions (create / update / delete) "
        "that will bring Google Calendar in sync with the new task assignments."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string"},
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action":      {"type": "string", "enum": ["create", "update", "delete"]},
                        "event_id":    {"type": "string",
                                        "description": "Required for update / delete."},
                        "summary":     {"type": "string",
                                        "description": "Event title. Required for create / update."},
                        "start":       {"type": "string",
                                        "description": "ISO-8601 datetime. Required for create / update."},
                        "end":         {"type": "string",
                                        "description": "ISO-8601 datetime. Required for create / update."},
                        "description": {"type": "string"},
                        "reason":      {"type": "string"},
                    },
                    "required": ["action"],
                },
            },
        },
        "required": ["reasoning", "actions"],
    },
}


def plan_calendar_sync(
    assigned_timeline: list[dict],   # output of assign_people_to_tasks["assignments"]
    existing_events:   list[dict],   # raw events from Google Calendar
    project_start_date: str,         # ISO date, e.g. "2025-04-07"
    workday_hours: tuple[int, int] = (9, 17),  # (start_hour, end_hour)
) -> dict:
    """
    Ask Claude to diff the assigned tasks against the existing calendar events
    and return a structured list of create / update / delete actions.
    """
    prompt = json.dumps({
        "project_start_date": project_start_date,
        "workday_start_hour": workday_hours[0],
        "workday_end_hour":   workday_hours[1],
        "assigned_tasks": assigned_timeline,
        "existing_calendar_events": existing_events,
    }, ensure_ascii=False, indent=2)

    system = (
        "You are a calendar synchronisation engine. "
        "Given a list of assigned tasks (each with a day offset from project_start_date, "
        "a task_id, and an assignee) and the current Google Calendar events, "
        "produce the minimal set of create / update / delete actions to make the calendar "
        "match the tasks exactly. Rules:\n"
        "• Each task slot becomes one all-day or timed event: "
        "  summary = '<task_id> – <assignee>', start/end within the workday.\n"
        "• If an existing event already matches (same task, same assignee, same date), "
        "  do NOT emit an action for it.\n"
        "• Delete events that correspond to tasks no longer in the AFTER timeline.\n"
        "• Use ISO-8601 datetime strings (e.g. '2025-04-07T09:00:00') for start/end.\n"
        "Use the sync_calendar tool to return your answer."
    )

    response = _claude(system, prompt, tools=[_SYNC_TOOL],
                        tool_choice={"type": "tool", "name": "sync_calendar"})
    return _extract_tool_input(response, "sync_calendar")


# ─────────────────────────────────────────────
# STEP 3 — EXECUTE CALENDAR ACTIONS
# ─────────────────────────────────────────────
def execute_calendar_actions(
    actions: list[dict],
    cal_tool: str,
    calendar_id: str = "primary",
    dry_run: bool = False,
) -> list[dict]:
    """
    Execute the create / update / delete actions against Google Calendar via MCP.

    Parameters
    ----------
    actions     : list produced by plan_calendar_sync
    cal_tool    : MCP tool name for Google Calendar
    calendar_id : Google Calendar ID (default "primary")
    dry_run     : if True, print actions but do not call MCP

    Returns
    -------
    list of {"action": ..., "result": ...}
    """
    results = []
    for action in actions:
        kind = action.get("action")
        print(f"  [{kind.upper()}] {action.get('summary', action.get('event_id', '?'))} "
              f"— {action.get('reason', '')}")

        if dry_run:
            results.append({"action": action, "result": "dry_run"})
            continue

        if kind == "create":
            result = calendar_create_event(
                cal_tool,
                summary=action["summary"],
                start=action["start"],
                end=action["end"],
                description=action.get("description", ""),
                calendar_id=calendar_id,
            )
        elif kind == "update":
            result = calendar_update_event(
                cal_tool,
                event_id=action["event_id"],
                summary=action["summary"],
                start=action["start"],
                end=action["end"],
                description=action.get("description", ""),
                calendar_id=calendar_id,
            )
        elif kind == "delete":
            result = calendar_delete_event(
                cal_tool,
                event_id=action["event_id"],
                calendar_id=calendar_id,
            )
        else:
            result = {"error": f"Unknown action type: {kind}"}

        results.append({"action": action, "result": result})

    return results


# ─────────────────────────────────────────────
# MAIN ORCHESTRATION FUNCTION
# ─────────────────────────────────────────────
def sync_tasks_to_calendar(
    timeline_before: dict[int, list[dict]],
    timeline_after:  dict[int, list[dict]],
    team:            list[str],
    project_start_date: str,
    calendar_id:     str = "tester",
    workday_hours:   tuple[int, int] = (9, 17),
    cal_event_range_days: int = 60,
    dry_run:         bool = False,
) -> dict:
    """
    Full pipeline: assign → fetch → diff → sync.

    Parameters
    ----------
    timeline_before : {day_int: [{"task_id": str, "assignee": str}]}
        The original schedule with known assignees.
    timeline_after  : {day_int: [{"task_id": str}]}
        The new (reordered / modified) schedule without assignees.
    team            : list of team member names
    project_start_date : ISO date string, e.g. "2025-04-07"
    calendar_id     : Google Calendar id (default "primary")
    workday_hours   : (start_hour, end_hour) for event times
    cal_event_range_days : how many days ahead to fetch from calendar
    dry_run         : if True, plan but do not mutate the calendar

    Returns
    -------
    {
        "assignments": [...],
        "calendar_actions": [...],
        "execution_results": [...],
    }
    """
    # ── 0. Connect to MCP ──────────────────────────────────────────────────
    tool_names = mcp_init()
    cal_tool = _find_calendar_tool(tool_names, "google_calendar")
    if cal_tool is None:
        raise RuntimeError(
            "No Google Calendar tool found in MCP. "
            f"Available tools: {sorted(tool_names)}"
        )
    print(f"Using calendar tool: {cal_tool}")

    # ── 1. Assign people to the AFTER timeline ─────────────────────────────
    print("\n── Step 1: Assigning people to tasks…")
    assignment_result = assign_people_to_tasks(timeline_before, timeline_after, team)
    assignments = assignment_result["assignments"]
    print(f"   Reasoning: {assignment_result['reasoning']}")
    print(f"   Assignments: {len(assignments)} slots assigned.")

    # ── 2. Fetch existing calendar events ─────────────────────────────────
    print("\n── Step 2: Fetching Google Calendar events…")
    start_dt = datetime.fromisoformat(project_start_date)
    time_min = start_dt.strftime("%Y-%m-%dT00:00:00Z")
    time_max = (start_dt + timedelta(days=cal_event_range_days)).strftime("%Y-%m-%dT23:59:59Z")
    existing_events = calendar_list_events(cal_tool, calendar_id, time_min, time_max)
    print(f"   Found {len(existing_events)} existing events.")

    # ── 3. Plan calendar sync ──────────────────────────────────────────────
    print("\n── Step 3: Planning calendar sync…")
    sync_plan = plan_calendar_sync(assignments, existing_events,
                                    project_start_date, workday_hours)
    actions = sync_plan["actions"]
    print(f"   Reasoning: {sync_plan['reasoning']}")
    print(f"   Actions planned: {len(actions)} "
          f"({sum(1 for a in actions if a['action']=='create')} create, "
          f"{sum(1 for a in actions if a['action']=='update')} update, "
          f"{sum(1 for a in actions if a['action']=='delete')} delete)")

    # ── 4. Execute ─────────────────────────────────────────────────────────
    print(f"\n── Step 4: {'(DRY RUN) ' if dry_run else ''}Executing calendar actions…")
    execution_results = execute_calendar_actions(actions, cal_tool, calendar_id, dry_run)
    print(f"   Done. {len(execution_results)} actions processed.")

    return {
        "assignments":        assignments,
        "assignment_reasoning": assignment_result["reasoning"],
        "calendar_actions":   actions,
        "sync_reasoning":     sync_plan["reasoning"],
        "execution_results":  execution_results,
    }


# ─────────────────────────────────────────────
# EXAMPLE USAGE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # ── Timeline structures ────────────────────────────────────────────────
    # BEFORE: tasks with known assignees
    TIMELINE_BEFORE: dict[int, list[dict]] = {
        0: [
            {"task_id": "Task 3", "assignee": "María"},
            {"task_id": "Task 4", "assignee": "José"},
            {"task_id": "Task 0", "assignee": "Pablo"},
        ],
        1: [{"task_id": "Task 0", "assignee": "Pablo"}],
        2: [{"task_id": "Task 0", "assignee": "Pablo"}],
        3: [{"task_id": "Task 0", "assignee": "Pablo"}],
        4: [{"task_id": "Task 0", "assignee": "Pablo"}],
        5: [{"task_id": "Task 2", "assignee": "María"}],
        6: [{"task_id": "Task 2", "assignee": "María"}],
        7: [{"task_id": "Task 1", "assignee": "María"}],
    }

    # AFTER: reordered tasks, no assignees yet
    TIMELINE_AFTER: dict[int, list[dict]] = {
        0: [
            {"task_id": "Task 3"},
            {"task_id": "Task 4"},
            {"task_id": "Task 0"},
        ],
        1: [{"task_id": "Task 0"}],
        2: [{"task_id": "Task 0"}],
        3: [{"task_id": "Task 0"}],
        4: [{"task_id": "Task 2"}],
        5: [{"task_id": "Task 2"}],
        6: [{"task_id": "Task 1"}],
    }

    TEAM = ["María", "José", "Pablo"]

    PROJECT_START = "2026-05-05"  # Monday — adjust to your sprint start

    result = sync_tasks_to_calendar(
        timeline_before=TIMELINE_BEFORE,
        timeline_after=TIMELINE_AFTER,
        team=TEAM,
        project_start_date=PROJECT_START,
        calendar_id="primary",
        dry_run=False,           # set True to plan without touching the calendar
    )

    print("\n── Final Summary ──────────────────────────────────────────")
    print("Assignment reasoning:", result["assignment_reasoning"])
    print("Sync reasoning:", result["sync_reasoning"])
    print(f"Total calendar actions executed: {len(result['execution_results'])}")
