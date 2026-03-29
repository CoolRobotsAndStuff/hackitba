import requests
import os
from requests.auth import HTTPBasicAuth
import json
from dotenv import load_dotenv
from algo import *

def estimate_days(fields):
    # 1. Original time estimate (in seconds)
    estimate = fields.get("timeoriginalestimate")
    if estimate:
        return max(1, round(estimate / 86400))
    
    # 2. Story points (assume 1 point ~ 1 day)
    story_points = fields.get("story_points") or fields.get("customfield_10016")
    if story_points:
        return max(1, round(story_points))
    
    # 3. Issue type as a rough heuristic
    issue_type = fields.get("issuetype", {}).get("name", "")
    heuristics = {
        "Epic": 10,
        "Story": 3,
        "Task": 2,
        "Sub-task": 1,
        "Bug": 1,
    }
    return heuristics.get(issue_type, 2)  # default 2 days


def get_jira_tasks():
    load_dotenv()
    url = "https://aledeumsaf.atlassian.net/rest/api/3/search/jql"

    auth = HTTPBasicAuth("aledeum.saf@gmail.com", os.getenv("JIRA_API_TOKEN"))

    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
    }

    response = requests.get(
        url=url,
        headers=headers,
        params={
            "jql": "status != Done ORDER BY created DESC",
            "startAt": 0,
            "maxResults": 50,  # max is 100
            "fields": "summary,status,assignee,priority,created,updated,issuelinks"
        },
        auth=auth
    )

    issues = response.json()["issues"]

    key_to_idx = {issue["key"]: i for i, issue in enumerate(issues)}

    tasks = []

    for issue in issues:
        idx = key_to_idx[issue["key"]]
        deps = []
        for link in issue["fields"].get("issuelinks", []):
            if "inwardIssue" in link and link["type"]["inward"] == "is blocked by":
                blocker_key = link["inwardIssue"]["key"]
                if blocker_key in key_to_idx:
                    deps.append(key_to_idx[blocker_key])

        tasks.append({
            "name": issue["fields"]["summary"],  # or issue["fields"]["summary"] for full title
            "deps": deps,
            "days": estimate_days(issue["fields"])  # Jira has no duration field, set a default or derive from story points
        })
    return tasks


if __name__ == "__main__":
    print(get_timeline_string(get_jira_tasks()));