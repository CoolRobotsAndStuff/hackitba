from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta


def _get_service(service_account_file):
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=SCOPES
    )
    return build('calendar', 'v3', credentials=creds)


def get_calendar_tasks(calendar_id, service_account_file='service-account.json'):
    """
    Fetches all upcoming events from a Google Calendar and returns them as tasks.

    Returns:
        List of task dicts with datetime, name, deps, days, and id fields
    """
    service = _get_service(service_account_file)

    params = {
        'calendarId':   calendar_id,
        'singleEvents': True,
        'orderBy':      'startTime',
        'timeMin':      datetime.now(timezone.utc).isoformat(),
    }

    all_events = []
    while True:
        result = service.events().list(**params).execute()
        all_events.extend(result.get('items', []))
        page_token = result.get('nextPageToken')
        if not page_token:
            break
        params['pageToken'] = page_token

    tasks = []
    for event in all_events:
        start   = event['start'].get('dateTime', event['start'].get('date'))
        end_str = event['end'].get('dateTime',   event['end'].get('date'))

        start_dt = datetime.fromisoformat(start)
        end_dt   = datetime.fromisoformat(end_str)
        days = max(1, (end_dt - start_dt).days or 1)

        tasks.append({
            "id":       event['id'],        # useful for modify_event
            "datetime": start,
            "name":     event.get('summary', 'Untitled'),
            "deps":     [],
            "days":     days,
        })

    return tasks


def create_event(calendar_id, name, start, days=1, description=None, location=None, service_account_file='service-account.json'):
    """
    Creates an event in Google Calendar.

    Args:
        calendar_id:          Your calendar ID (e.g. 'your@gmail.com')
        name:                 Event title
        start:                Start datetime string (e.g. '2026-04-01T10:00:00')
        days:                 Duration in days (default 1)
        description:          Optional event description
        location:             Optional event location
        service_account_file: Path to your service account JSON key file

    Returns:
        Created event dict
    """
    service = _get_service(service_account_file)

    start_dt = datetime.fromisoformat(start)
    end_dt   = start_dt + timedelta(days=days)

    event = {
        'summary': name,
        'start':   {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'},
        'end':     {'dateTime': end_dt.isoformat(),   'timeZone': 'UTC'},
    }

    if description:
        event['description'] = description
    if location:
        event['location'] = location

    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    print(f"Event created: {created['summary']} → {created['htmlLink']}")
    return created


def modify_event(calendar_id, event_id, name=None, start=None, days=None, description=None, location=None, service_account_file='service-account.json'):
    """
    Modifies an existing event. Only fields you pass will be updated.

    Args:
        calendar_id:          Your calendar ID (e.g. 'your@gmail.com')
        event_id:             The event ID to modify — use the 'id' field from get_calendar_tasks()
        name:                 New title (optional)
        start:                New start datetime string (optional)
        days:                 New duration in days (optional)
        description:          New description (optional)
        location:             New location (optional)
        service_account_file: Path to your service account JSON key file

    Returns:
        Updated event dict
    """
    service = _get_service(service_account_file)

    event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

    if name:
        event['summary'] = name
    if description:
        event['description'] = description
    if location:
        event['location'] = location

    if start or days:
        current_start = event['start'].get('dateTime', event['start'].get('date'))
        start_dt = datetime.fromisoformat(start) if start else datetime.fromisoformat(current_start)

        if days:
            end_dt = start_dt + timedelta(days=days)
        else:
            current_end = event['end'].get('dateTime', event['end'].get('date'))
            current_duration = datetime.fromisoformat(current_end) - datetime.fromisoformat(current_start)
            end_dt = start_dt + current_duration

        event['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': 'UTC'}
        event['end']   = {'dateTime': end_dt.isoformat(),   'timeZone': 'UTC'}

    updated = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
    print(f"Event updated: {updated['summary']} → {updated['htmlLink']}")
    return updated
print(get_calendar_tasks("hackitba.demo@gmail.com"))
