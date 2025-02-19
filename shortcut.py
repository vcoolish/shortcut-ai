import os
import sys
import requests
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
SHORTCUT_API_KEY = os.environ["SHORTCUT_API_KEY"]

BASE_URL = "https://api.app.shortcut.com"

WORKFLOW_STATES = {
    "500000516": "Started work",
    "500000518": "Moved to review",
    "500000519": "Ready for QA",
    "500015433": "In QA",
    "500000513": "Finished",
}

TEAM_MAPPING = {
    "6762654a-965c-467f-a23e-14c24f7aa80f": "Gateway Squad",
    "6548f4fb-429d-4c55-b2ba-a100128f8dd9": "Platform Squad",
    "67876dcb-3573-4ae7-bf71-7adaf3ec31e9": "Native Squad",
    "67626534-4ccd-4a09-a660-1f7d8667b0e2": "DeFi Squad",
    "67877589-c6d8-4ed8-91cc-e455c6e1583a": "Services Squad",
    "67626576-18d0-4f72-bad4-db8982cd96d9": "Wallet Squad",
    "676265b1-331f-42f4-a7f9-97fe88b1ba60": "WebWallet Squad",
    "67876d95-6990-4c3e-acbe-f220f016f2e6": "Chain Squad",
    "65522d8a-a1a4-45b5-8947-ed0bd0096ade": "BD Team",
    "65559d07-43eb-4de2-a3a0-dc0063b14b07": "Design Team",
    "676265cd-7cbb-457d-b4fd-8b2827d07ff1": "Foundation Squad",
    "65559cb8-f0fe-4fa2-b65f-6713ef84e56b": "Marketing Team",
    "65b6a41b-8430-4775-bd60-33cfb1f54ac9": "QA Team",
}


def fetch_owner_details(owner_ids):
    """Fetches owner details from Shortcut API.

    Args:
        owner_ids: A list of owner IDs.

    Returns:
        A dictionary mapping owner_id to owner name. Returns "Unknown User"
        if the owner's name cannot be retrieved.
    """
    owners = {}
    for owner_id in owner_ids:
        url = f"{BASE_URL}/api/v3/members/{owner_id}"
        headers = {"Shortcut-Token": SHORTCUT_API_KEY}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            owner_data = response.json()
            owners[owner_id] = owner_data.get("profile", {}).get("name", "Unknown User")
        else:
            owners[owner_id] = "Unknown User"
    return owners


def fetch_stories_updated_on(date: str):
    """Fetches Shortcut stories updated on a given date, groups them by team,
    and formats the data as Markdown.

    Args:
        date: The date to search for in YYYY-MM-DD format.

    Returns:
        A Markdown-formatted string containing the stories grouped by team.
        Returns an empty string if there is an error fetching data.
    """
    headers = {
        "Content-Type": "application/json",
        "Shortcut-Token": SHORTCUT_API_KEY,
    }

    url = f"{BASE_URL}/api/v3/search/stories?query=updated%3A{date}&detail=full"
    team_tasks = defaultdict(list)
    owner_ids_set = set()

    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Error fetching data: {response.json()}")
            return ""

        data = response.json()
        stories = data.get("data", [])

        for story in stories:
            workflow_state_id = str(story.get("workflow_state_id"))
            group_id = story.get("group_id", "")
            description = story.get("description", "")
            owner_ids = story.get("owner_ids", [])
            owner_ids_set.update(owner_ids)

            if workflow_state_id in WORKFLOW_STATES:
                state = WORKFLOW_STATES[workflow_state_id]
                team_name = TEAM_MAPPING.get(group_id, "Unknown Squad")
                story_title = story["name"]
                app_url = story["app_url"]

                team_tasks[team_name].append(
                    (story_title, app_url, state, owner_ids, description)
                )

        next_page = data.get("next")
        url = f"{BASE_URL}{next_page}" if next_page else None

    owner_details = fetch_owner_details(owner_ids_set)

    markdown_output = ""
    for team, tasks in team_tasks.items():
        markdown_output += f"## {team}\n\n"
        for title, url, state, owners, description in tasks:
            owner_names = ", ".join(
                owner_details.get(owner, "Unknown User") for owner in owners
            )
            markdown_output += (
                f"- [{title}]({url}) → **{state}** by *{owner_names}*\n"
                f"DESCRIPTION_START\n{description}DESCRIPTION_END\n"
            )
        markdown_output += "\n"

    return markdown_output

def fetch_epics_updated_on(date: str):
    """Fetches epics from Shortcut API updated on a given date, and formats
    them into a string similar to how stories are formatted.

    Args:
        date: The date to search for in YYYY-MM-DD format.

    Returns:
        A Markdown-formatted string containing the epics information.
        Returns an empty string if there is an error.
    """
    headers = {
        "Content-Type": "application/json",
        "Shortcut-Token": SHORTCUT_API_KEY,
    }
    url = f"{BASE_URL}/api/v3/search/epics?query=updated%3A{date}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        epics = data.get("data", [])
        epic_markdown = ""
        owner_ids_set = set() # collect all owner_ids
        for epic in epics:
            owner_ids = epic.get("owner_ids", [])
            owner_ids_set.update(owner_ids)

        owner_details = fetch_owner_details(owner_ids_set)

        for epic in epics:
            try:
                num_stories_done = epic.get("stats", {}).get("num_stories_done", 0)
                num_stories_total = epic.get("stats", {}).get("num_stories_total", 1)  # Avoid division by zero
                progress_percent = (num_stories_done / num_stories_total) * 100
            except (TypeError, ZeroDivisionError):
                progress_percent = 0  # Handle missing or invalid stats

            title = epic.get("name", "Untitled Epic")
            link = epic.get("app_url", "")
            description = epic.get("description", "")
            progress_str = f"{round(progress_percent, 2)}%"
            owner_ids = epic.get("owner_ids", [])
            owner_names = ", ".join(owner_details.get(owner, "Unknown User") for owner in owner_ids)

            epic_markdown += (
                f"- [{title}]({link}) - Progress: {progress_str} complete by *{owner_names}\n" +
                f"DESCRIPTION_START\n{description}DESCRIPTION_END\n"
            )

        return epic_markdown
    except requests.exceptions.RequestException as e:
        print(f"Error fetching epics: {e}")
        if response is not None:
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.content.decode()}")
        return ""

def generate_openai_summary(markdown_report: str):
    """Generates a summary of the Shortcut data using OpenAI's GPT-4o model.

    Args:
        markdown_report: The Markdown-formatted report to summarize.

    Returns:
        A string containing the OpenAI-generated summary.  Returns None if
        the OpenAI API key is not set or if there is an error during the API call.
    """
    openai_api_key = OPENAI_API_KEY
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not set.")
        return None

    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }
    prompt = f"""{markdown_report}\n\nMake a nice markdown table for above items grouped by squad and add a summary of what was done
taking into account added descriptions for each story, update your summaries but don't add the actual descriptions into the report.
Use emojis to make report nice. 
Explanations in () are for you.
Structure is following: 
Summary for all work (TLDR of report):
Status Breakdown (story count by status):
Key Highlights (key highlights of updates for the day with context of story Descriptions):
Work Items Grouped by Squad:
tables: Task(Title with link to story) - Status - Owner(s)
"""
    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"Error during OpenAI API call: {e}")
        if response is not None:
            print(f"Response status code: {response.status_code}")
            print(f"Response content: {response.content.decode()}")
        return None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python shortcut.py <YYYY-MM-DD>")
        sys.exit(1)

    date = sys.argv[1]
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        sys.exit(1)

    story = fetch_stories_updated_on(date)
    epics = fetch_epics_updated_on(date)
    print(epics)

    if not markdown_report:
        print("No data fetched from Shortcut.")
        sys.exit(1)

    openai_summary = generate_openai_summary(story)
    openai_summary_epic = generate_openai_summary(epics)

    if openai_summary:
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)
        filename = os.path.join(reports_dir, f"{date}.md")
        filename_epic = os.path.join(reports_dir, f"{date}-epic.md")
        try:
            with open(filename, "w") as f:
                f.write(openai_summary)
            print(f"OpenAI summary saved to {filename}")
            with open(filename_epic, "w") as f:
                f.write(openai_summary_epic)
            print(f"OpenAI summary saved to {filename_epic}")
        except IOError as e:
            print(f"Error writing to file: {e}")
    else:
        print("Failed to generate OpenAI summary.")