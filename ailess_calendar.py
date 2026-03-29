from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timezone

def get_calendar_tasks(calendar_id, service_account_file='service-account.json'):
    """
    Fetches all upcoming events from a Google Calendar and returns them as tasks.

    Args:
        calendar_id:          Your calendar ID (e.g. 'your@gmail.com')
        service_account_file: Path to your service account JSON key file

    Returns:
        List of task dicts with datetime, name, deps, and days fields
    """
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

    creds = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=SCOPES
    )
    service = build('calendar', 'v3', credentials=creds)

    time_min = datetime.now(timezone.utc).isoformat()

    params = {
        'calendarId':  calendar_id,
        'singleEvents': True,
        'orderBy':     'startTime',
        'timeMin':     time_min,
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
            "datetime": start,
            "name":     event.get('summary', 'Untitled'),
            "deps":     [],
            "days":     days,
        })

    return tasks

print(get_calendar_tasks("hackitba.demo@gmail.com"))
