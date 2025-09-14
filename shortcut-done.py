import os
import sys
import requests
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import time

load_dotenv()
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_ORG_KEY = os.environ["OPENAI_ORG_KEY"]
SHORTCUT_API_KEY = os.environ["SHORTCUT_API_KEY"]

BASE_URL = "https://api.app.shortcut.com"

WORKFLOW_STATES = {
    "500000513": "Done",
    "500028067": "Go",
    "500015433": "In Testing",
    "500029050": "Ready for deployment",
}
GO_STATE_ID = "500028067"

TEAM_MAPPING = {
    "686377b2-3918-4de2-bd88-924f7cff3374": "💰Earn Team",
    "67da9922-f33e-431a-9e40-5cbe4ac48d29": "🏦Banking Team",
    "685d209a-04cc-4ec9-9742-49174eae7908": "👋Activation Team",
    "67626534-4ccd-4a09-a660-1f7d8667b0e2": "📈Trading Team",
    "685e7a04-fa00-4f08-9aaf-720706381dbc": "📱CoreX Client Team",
    "68637e43-f987-4ecb-989b-a71fd18729ee": "🌱Growth Team",
    "6548f4fb-429d-4c55-b2ba-a100128f8dd9": "💻DevOps Team",
    "685e9d52-60c7-4328-9a56-d7d81db4128b": "⚙️CoreX Services Team",
    "6863d63d-831d-408e-ae35-4a66877d3e88": "🔗CoreX On-Chain Team",
    "676265b1-331f-42f4-a7f9-97fe88b1ba60": "WebWallet Team",
    "65522d8a-a1a4-45b5-8947-ed0bd0096ade": "BD Team",
    "65559d07-43eb-4de2-a3a0-dc0063b14b07": "Design Team",
    "676265cd-7cbb-457d-b4fd-8b2827d07ff1": "🏗️ Foundation Squad",
    "65559cb8-f0fe-4fa2-b65f-6713ef84e56b": "Marketing Team",
    "65b6a41b-8430-4775-bd60-33cfb1f54ac9": "QA Team",
}

# --- Helper Functions ---
def get_start_of_last_friday_utc():
    """Returns the date of last Friday at 00:00 UTC as a timezone-aware datetime."""
    now = datetime.now(timezone.utc)
    days_since_friday = (now.weekday() - 4 + 7) % 7 # Friday is 4
    if now.weekday() == 4:
        days_since_friday += 7
    last_friday = now - timedelta(days=9)
    return last_friday.replace(hour=0, minute=0, second=0, microsecond=0)

def get_start_of_last_tuesday_utc():
    """Returns the date of last Tuesday at 00:00 UTC as a timezone-aware datetime."""
    now = datetime.now(timezone.utc)
    days_since_tuesday = (now.weekday() - 1 + 7) % 7 # Tuesday is 1
    last_tuesday = now - timedelta(days=days_since_tuesday)
    return last_tuesday.replace(hour=0, minute=0, second=0, microsecond=0)

def fetch_owner_details(owner_ids):
    """Fetches owner details from Shortcut API."""
    owners = {}
    for owner_id in owner_ids:
        url = f"{BASE_URL}/api/v3/members/{owner_id}"
        headers = {"Shortcut-Token": SHORTCUT_API_KEY}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                owner_data = response.json()
                owners[owner_id] = owner_data.get("profile", {}).get("name", "Unknown User")
            else:
                owners[owner_id] = "Unknown User"
        except requests.exceptions.RequestException:
            owners[owner_id] = "Unknown User"
    return owners

def fetch_go_stories_from_last_tuesday():
    """Fetches stories that were in the 'Go' column on the last Tuesday."""
    headers = {"Shortcut-Token": SHORTCUT_API_KEY}
    last_tuesday = get_start_of_last_tuesday_utc()
    go_stories_set = set()

    # Query for stories completed in the 'Go' state since last Tuesday
    query = f"state:{GO_STATE_ID} completed_after:{last_tuesday.isoformat()}"
    url = f"{BASE_URL}/api/v3/search/stories?query={requests.utils.quote(query)}&detail=full"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        for story in data.get("data", []):
            if story.get("completed_at"):
                completion_date = datetime.fromisoformat(story["completed_at"].replace('Z', '+00:00'))
                if completion_date.date() == last_tuesday.date():
                    go_stories_set.add(story["id"])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching 'Go' stories: {e}")
        return set()

    return go_stories_set


# The 'fetch_stories_by_state' function is removed, as its logic is now embedded directly in the main block.


def create_markdown_report(team_tasks, owner_details, start_date, end_date):
    """Generates the main Markdown report, grouping stories by team and then by state."""
    markdown_output = f"# Weekly Release Report\n"
    markdown_output += f"**Period:** {start_date.date()} to {end_date.date()}\n\n"

    for team, states in team_tasks.items():
        if states:
            markdown_output += f"## {team}\n\n"
            for state, stories in states.items():
                markdown_output += f"### {state}\n\n"
                for story in stories:
                    owner_names = ", ".join(
                        owner_details.get(owner, "Unknown User") for owner in story["owner_ids"]
                    )
                    markdown_output += f"- [{story['title']}]({story['url']})\n"
                markdown_output += "\n"
            markdown_output += "\n"

    return markdown_output

def generate_dogfooding_summary(markdown_report: str):
    """
    Generates a summary for an agile dogfooding document using LLM.
    ... (rest of the function is the same)
    """
    openai_api_key = OPENAI_API_KEY
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not set.")
        return None

    headers = {
        "x-portkey-api-key": os.environ["PORTKEY_API_KEY"],
        "x-portkey-virtual-key": os.environ["GOOGLE_VIRTUAL_KEY"],
        "Content-Type": "application/json",
    }

    prompt = f"""{markdown_report}

Based on the stories above generate **Dogfooding Highlights**: A brief, high-level summary of the most important features or changes to dogfood.
Add focus area of testing of a week based on stories. Attach challenges for focus area to make it as quest. If can't find a solid focus area, take a random one from list:
Security & Privacy Week,New User Onboarding Week,DeFi and DApps Week,Localization & Internationalization Week,Specific Challenges,Performance Challenges,Ecosystem & Integration Challenges,UI/UX Challenges, Edge Case Challenges
Don't add anything else.
Use clear, concise language and emojis to make the document easy to read and act upon."""

    data = {
        "model": "gemini-2.5-flash",
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        response = requests.post(
            "https://api.portkey.ai/v1/chat/completions",
            headers=headers,
            json=data,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"Error during OpenAI API call for dogfooding summary: {e}")
        return None

def create_dogfooding_report(team_tasks):
    """Generates a list of stories for dogfooding."""
    dogfooding_output = "# Dogfooding Stories\n\n"
    for team, states in team_tasks.items():
        if states:
            dogfooding_output += f"## {team}\n\n"
            for state, stories in states.items():
                dogfooding_output += f"### {state}\n\n"
                for story in stories:
                    dogfooding_output += f"- [{story['title']}]({story['url']})\n"
                dogfooding_output += "\n"
    return dogfooding_output


if __name__ == "__main__":
    # 1. Fetch stories from the 'Go' column from last Tuesday
    go_stories_to_exclude = fetch_go_stories_from_last_tuesday()

    DONE_STATE_ID = "500000513"
    IN_TESTING_STATE_ID = "500015433"
    READY_FOR_DEPLOYMENT_STATE_ID = "500029050"
    TARGET_STATE_IDS = [DONE_STATE_ID, IN_TESTING_STATE_ID, READY_FOR_DEPLOYMENT_STATE_ID]

    stories_by_team_and_state = defaultdict(lambda: defaultdict(list))
    owner_ids_set = set()
    start_date = get_start_of_last_friday_utc()
    end_date = datetime.now(timezone.utc)

    for state_id in TARGET_STATE_IDS:
        state_name = WORKFLOW_STATES.get(state_id, "Unknown State")
        headers = {"Shortcut-Token": SHORTCUT_API_KEY}

        # Build a valid query for each state individually
        query = f"state:{state_id} moved_after:{start_date.isoformat()}"
        url = f"{BASE_URL}/api/v3/search/stories?query={requests.utils.quote(query)}&detail=full"

        print(f"Fetching stories in '{state_name}' state since {start_date.date()}...")

        page_count = 0
        while url and page_count < 10:
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                stories = data.get("data", [])

                for story in stories:
                    story_id = story.get("id")
                    if story_id in go_stories_to_exclude:
                        continue

                    group_id = story.get("group_id", "")
                    team_name = TEAM_MAPPING.get(group_id, "Unknown Squad")

                    owner_ids = story.get("owner_ids", [])
                    owner_ids_set.update(owner_ids)

                    stories_by_team_and_state[team_name][state_name].append({
                        "title": story["name"],
                        "url": story["app_url"],
                        "description": story.get("description", ""),
                        "owner_ids": owner_ids
                    })

                next_page = data.get("next")
                url = f"{BASE_URL}{next_page}" if next_page else None
                page_count += 1

            except requests.exceptions.RequestException as e:
                print(f"Request error for state '{state_name}': {e}")
                break

    if not stories_by_team_and_state:
        print("No stories fetched from Shortcut in the specified timeframe and states.")
        sys.exit(1)

    owner_details = fetch_owner_details(owner_ids_set)

    # 3. Generate the main report
    stories_report_markdown = create_markdown_report(stories_by_team_and_state, owner_details, start_date, end_date)
    print(stories_report_markdown)

    # 4. Generate the dogfooding report
    dogfooding_report_markdown = create_dogfooding_report(stories_by_team_and_state)
    print(dogfooding_report_markdown)

    # 5. (Optional) Generate AI summary
    form = "[Report your findings here.](https://forms.gle/F3r6rbq4uYJNfpAN8)"
    openai_summary = generate_dogfooding_summary(stories_report_markdown)
    if openai_summary:
        print("\n--- OpenAI Summary ---\n")
        print(openai_summary)

    # 6. Save the reports
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)

    # Main report filename
    main_filename = os.path.join(reports_dir, f"weekly_release_{start_date.strftime('%Y-%m-%d')}.md")
    try:
        with open(main_filename, "w") as f:
            f.write(stories_report_markdown)
        print(f"Weekly release report saved to {main_filename}")
    except IOError as e:
        print(f"Error writing main report to file: {e}")

    # Dogfooding report filename
    dogfooding_filename = os.path.join(reports_dir, f"dogfooding_report_{start_date.strftime('%Y-%m-%d')}.md")
    try:
        with open(dogfooding_filename, "w") as f:
            # Handle the case where openai_summary is None
            if openai_summary:
                f.write(openai_summary + "\n" + form + "\n" + dogfooding_report_markdown)
            else:
                f.write(dogfooding_report_markdown)
        print(f"Dogfooding report saved to {dogfooding_filename}")
    except IOError as e:
        print(f"Error writing dogfooding report to file: {e}")