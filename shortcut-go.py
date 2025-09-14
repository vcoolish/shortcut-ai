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
    "500028067": "GO",
}

TEAM_MAPPING = {
    "686377b2-3918-4de2-bd88-924f7cff3374": "Earn Team",
    "67da9922-f33e-431a-9e40-5cbe4ac48d29": "Banking Team",
    "685d209a-04cc-4ec9-9742-49174eae7908": "Activation Team",
    "67626534-4ccd-4a09-a660-1f7d8667b0e2": "Trading Team",
    "685e7a04-fa00-4f08-9aaf-720706381dbc": "CoreX Client Team",
    "68637e43-f987-4ecb-989b-a71fd18729ee": "Growth Team",
}


def get_last_tuesday_utc():
    """Returns the date of last Tuesday at 00:00 UTC as a timezone-aware datetime."""
    from datetime import timezone

    now = datetime.now(timezone.utc)
    days_since_tuesday = (now.weekday() - 1) % 7  # Tuesday is 1 (Monday=0)
    if days_since_tuesday == 0 and now.hour == 0 and now.minute == 0:
        # If it's exactly Tuesday 00:00, get the previous Tuesday
        last_tuesday = now - timedelta(days=6)
    else:
        last_tuesday = now - timedelta(days=days_since_tuesday + (6 if days_since_tuesday == 0 else 0))

    last_tuesday = now - timedelta(days=7)
    return last_tuesday.replace(hour=0, minute=0, second=0, microsecond=0)


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


def fetch_go_stories_from_last_tuesday():
    """Fetches stories marked as 'GO' from last Tuesday 00:00 UTC to now.

    Returns:
        A Markdown-formatted string containing the stories grouped by team.
        Returns an empty string if there is an error fetching data.
    """
    headers = {
        "Content-Type": "application/json",
        "Shortcut-Token": SHORTCUT_API_KEY,
    }

    last_tuesday = get_last_tuesday_utc()
    now = datetime.now(timezone.utc)

    start_date = last_tuesday.strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    print(f"Fetching stories marked as 'GO' from {start_date} to {end_date}")

    team_tasks = defaultdict(list)
    owner_ids_set = set()

    # Instead of searching by update date, let's search by completion date and state
    # We'll use a more specific query to reduce results
    go_state_id = "500028067"  # The 'Done' state ID

    # First, let's try to fetch stories that are currently in 'Done' state
    # and filter by completion date client-side
    url = f"{BASE_URL}/api/v3/search/stories?query=state%3A{go_state_id}&detail=full"

    page_count = 0
    max_pages = 10  # Limit to prevent infinite loops

    while url and page_count < max_pages:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                error_data = response.json() if response.content else {"error": "Unknown error"}
                print(f"Error fetching data: {error_data}")

                # If we hit the maximum results error, let's try a different approach
                if error_data.get('error') == 'maximum-results-exceeded':
                    print("Too many results. Trying alternative approach...")
                    return fetch_done_stories_alternative_approach(start_date, end_date)
                return ""

            data = response.json()
            stories = data.get("data", [])

            print(f"Processing page {page_count + 1}, found {len(stories)} stories")

            for story in stories:
                # Check if the story was completed within our date range
                completed_at = story.get("completed_at")
                if completed_at:
                    # Parse the completion date
                    try:
                        # Handle different datetime formats from Shortcut API
                        if completed_at.endswith('Z'):
                            completion_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        elif '+' in completed_at or completed_at.endswith('UTC'):
                            completion_date = datetime.fromisoformat(completed_at.replace('UTC', '+00:00'))
                        else:
                            # If no timezone info, assume UTC
                            completion_date = datetime.fromisoformat(completed_at).replace(tzinfo=timezone.utc)

                        # Ensure our comparison datetimes are timezone-aware
                        if last_tuesday.tzinfo is None:
                            last_tuesday = last_tuesday.replace(tzinfo=timezone.utc)
                        if now.tzinfo is None:
                            now = now.replace(tzinfo=timezone.utc)

                        # Check if completion date is within our range
                        if completion_date >= last_tuesday and completion_date <= now:
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

                                if team_name != "Unknown Squad":
                                    team_tasks[team_name].append(
                                        (story_title, app_url, state, owner_ids, description)
                                    )
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing completion date for story {story.get('name', 'Unknown')}: {e}")
                        continue

            next_page = data.get("next")
            url = f"{BASE_URL}{next_page}" if next_page else None
            page_count += 1

        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            break

    print(f"Found {sum(len(tasks) for tasks in team_tasks.values())} completed stories")

    owner_details = fetch_owner_details(owner_ids_set)

    markdown_output = f"# Weekly Release Report\n"
    markdown_output += f"**Period:** {start_date} to {end_date}\n\n"

    for team, tasks in team_tasks.items():
        if tasks:  # Only show teams with completed tasks
            markdown_output += f"## {team}\n\n"
            for title, url, state, owners, description in tasks:
                owner_names = ", ".join(
                    owner_details.get(owner, "Unknown User") for owner in owners
                )
                markdown_output += f"- [{title}]({url})\n"
            markdown_output += "\n"

    return markdown_output


def fetch_done_stories_alternative_approach(start_date, end_date):
    """Alternative approach: fetch stories by team to avoid hitting the 1000 result limit."""
    headers = {
        "Content-Type": "application/json",
        "Shortcut-Token": SHORTCUT_API_KEY,
    }

    print("Using alternative approach: fetching by team...")

    team_tasks = defaultdict(list)
    owner_ids_set = set()
    go_state_id = "500028067"

    last_tuesday = get_last_tuesday_utc()
    now = datetime.utcnow()

    # Fetch stories for each team separately to avoid hitting the limit
    for team_id, team_name in TEAM_MAPPING.items():
        print(f"Fetching stories for {team_name}...")

        # Search for done stories in this specific team
        url = f"{BASE_URL}/api/v3/search/stories?query=state%3A{go_state_id}+group%3A{team_id}&detail=full"

        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Error fetching data for {team_name}: {response.json()}")
                continue

            data = response.json()
            stories = data.get("data", [])

            for story in stories:
                # Check if the story was completed within our date range
                completed_at = story.get("completed_at")
                if completed_at:
                    try:
                        # Handle different datetime formats from Shortcut API
                        if completed_at.endswith('Z'):
                            completion_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        elif '+' in completed_at or completed_at.endswith('UTC'):
                            completion_date = datetime.fromisoformat(completed_at.replace('UTC', '+00:00'))
                        else:
                            # If no timezone info, assume UTC
                            completion_date = datetime.fromisoformat(completed_at).replace(tzinfo=timezone.utc)

                        # Ensure our comparison datetimes are timezone-aware
                        if last_tuesday.tzinfo is None:
                            last_tuesday = last_tuesday.replace(tzinfo=timezone.utc)
                        if now.tzinfo is None:
                            now = now.replace(tzinfo=timezone.utc)

                        if completion_date >= last_tuesday and completion_date <= now:
                            workflow_state_id = str(story.get("workflow_state_id"))
                            description = story.get("description", "")
                            owner_ids = story.get("owner_ids", [])
                            owner_ids_set.update(owner_ids)

                            if workflow_state_id in WORKFLOW_STATES:
                                state = WORKFLOW_STATES[workflow_state_id]
                                story_title = story["name"]
                                app_url = story["app_url"]

                                team_tasks[team_name].append(
                                    (story_title, app_url, state, owner_ids, description)
                                )
                    except (ValueError, TypeError) as e:
                        print(f"Error parsing completion date for story {story.get('name', 'Unknown')}: {e}")
                        continue

        except requests.exceptions.RequestException as e:
            print(f"Request error for {team_name}: {e}")
            continue

    print(f"Found {sum(len(tasks) for tasks in team_tasks.values())} completed stories using alternative approach")

    owner_details = fetch_owner_details(owner_ids_set)

    markdown_output = f"# Weekly Release Report\n"
    markdown_output += f"**Period:** {start_date} to {end_date}\n\n"

    for team, tasks in team_tasks.items():
        if tasks:  # Only show teams with completed tasks
            markdown_output += f"## {team}\n\n"
            for title, url, state, owners, description in tasks:
                owner_names = ", ".join(
                    owner_details.get(owner, "Unknown User") for owner in owners
                )
                markdown_output += f"- [{title}]({url})\n"
            markdown_output += "\n"

    return markdown_output


def categorize_stories_by_platform(markdown_report: str):
    """Categorizes stories by platform (Extension, iOS, Android) based on story titles and descriptions.

    Args:
        markdown_report: The markdown report containing all stories

    Returns:
        A dictionary with platform categories and their stories
    """
    # Keywords to identify platform-specific stories
    platform_keywords = {
        "extension": ["extension", "chrome", "firefox", "browser", "popup", "content script", "web extension"],
        "ios": ["ios", "iphone", "ipad", "swift", "xcode", "app store", "cocoapods"],
        "android": ["android", "kotlin", "java", "gradle", "play store", "aab", "apk"]
    }

    categorized = {
        "extension": [],
        "ios": [],
        "android": [],
        "other": []
    }

    # Parse the markdown to extract story information
    lines = markdown_report.split('\n')
    current_team = ""

    for line in lines:
        if line.startswith('## '):
            current_team = line[3:].strip()
        elif line.startswith('- ['):
            # Extract story title and URL
            story_info = line[2:].strip()  # Remove '- '

            # Categorize based on keywords in title
            story_lower = story_info.lower()
            categorized_story = False

            for platform, keywords in platform_keywords.items():
                if any(keyword in story_lower for keyword in keywords):
                    categorized[platform].append(f"{story_info} (Team: {current_team})")
                    categorized_story = True
                    break

            if not categorized_story:
                categorized["other"].append(f"{story_info} (Team: {current_team})")

    return categorized


def generate_release_notes(categorized_stories):
    """Generates release notes for each platform using OpenAI.

    Args:
        categorized_stories: Dictionary with platform categories and their stories

    Returns:
        A string containing the OpenAI-generated release notes for all platforms.
    """

    headers = {
        "x-portkey-api-key": os.environ["PORTKEY_API_KEY"],
        "x-portkey-virtual-key": os.environ["GOOGLE_VIRTUAL_KEY"],
        "Content-Type": "application/json",
    }

    release_notes = "# Release Notes\n\n"

    for platform, stories in categorized_stories.items():
        if not stories:
            continue

        if platform == "other":
            continue  # Skip 'other' category for release notes

        stories_text = "\n".join(stories)

        prompt = f"""Based on the following completed stories for {platform.upper()}, generate user-friendly release notes:

{stories_text}

You are an expert in marketing and product development for the crypto industry, 
specializing in enhancing release notes for Trust Wallet products. 
Your role is to emulate the style of Apple’s release notes, focusing on clear, structured content with specific 
feature highlights in a user-friendly presentation. Organize the notes into distinct sections: 
Features, Security Enhancements, and Bug Fixes. For the Features section, begin each point with a clear 
subtitle and ensure the subtitle and bullet point are on the same line. Pay special attention to the "feat" 
label from Github commits; they should all be included in the Features section. Do not include subtitles for 
Security Enhancements and Bug Fixes to maintain simplicity. Feature descriptions should not end with commit IDs. 
Use engaging and concise descriptions for new features, and prominently highlight improvements 
in accessibility and usability. Detail important technical and security updates in an informative yet accessible way
for non-technical users. Mention any regional or device-specific limitations or availability, similar
to Apple's style, to manage user expectations. Maintain a professional and neutral tone in the writing, 
avoiding the use of 'we'. 
Android release notes have limit of 500 characters.
iOS and Extension release notes have limit of 1000 characters.
Do not add any markdown formatting for release notes.
Please create release notes:

Format the response as a clean output for {platform.upper()} release notes."""

        data = {
            "model": "gemini-2.0-flash",
            "messages": [{"role": "user", "content": prompt}],

        }

        try:
            time.sleep(3)
            response = requests.post(
                "https://api.portkey.ai/v1/chat/completions",
                headers=headers,
                json=data,
            )
            print(response.headers)
            response.raise_for_status()
            print(response.json())
            platform_notes = response.json()["choices"][0]["message"]["content"]
            release_notes += f"\n{platform_notes}\n\n"
        except requests.exceptions.RequestException as e:
            print(f"Error generating release notes for {platform}: {e}")
            release_notes += f"\n## {platform.upper()} Release Notes\n\nError generating release notes for this platform.\n\n"

    return release_notes


def generate_openai_summary(markdown_report: str):
    """Generates a summary of the weekly release report using OpenAI's GPT-4o model.

    Args:
        markdown_report: The Markdown-formatted report to summarize.

    Returns:
        A string containing the OpenAI-generated summary.
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

Please create a comprehensive weekly release summary with the following structure:

1. **Executive Summary** (2-3 sentences overview of the week's achievements)
2. **Team Contributions** (summary of work completed by each team)
3. **Key Deliverables** (highlight major features or fixes completed)
4. **Platform Breakdown** (if applicable, categorize work by platform)

Use emojis to make the report engaging and ensure the language is accessible to both technical and non-technical stakeholders."""

    data = {
        "model": "gemini-2.0-flash",
        "messages": [{"role": "user", "content": prompt}],

    }

    try:
        time.sleep(3)
        response = requests.post(
            "https://api.portkey.ai/v1/chat/completions",
            headers=headers,
            json=data,
        )
        print(response.headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        print(f"Error during summary OpenAI API call: {e}")
        return None


if __name__ == "__main__":
    # Fetch stories marked as 'Done' from last Tuesday to now
    stories_report = fetch_go_stories_from_last_tuesday()
    print(stories_report)

    if not stories_report:
        print("No data fetched from Shortcut.")
        sys.exit(1)

    final_report = stories_report

    # Generate main summary
    openai_summary = generate_openai_summary(stories_report)
    print(openai_summary)

    # Categorize stories by platform and generate release notes
    categorized_stories = categorize_stories_by_platform(stories_report)
    release_notes = generate_release_notes(categorized_stories)

    # Combine all reports
    final_report = ""
    if openai_summary:
        final_report += openai_summary + "\n\n"

    final_report += stories_report + "\n\n"

    if release_notes:
        final_report += release_notes

    # Save the report
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)

    last_tuesday = get_last_tuesday_utc()
    filename = os.path.join(reports_dir, f"weekly_go_{last_tuesday.strftime('%Y-%m-%d')}.md")

    try:
        with open(filename, "w") as f:
            f.write(final_report)
        print(f"Weekly release report saved to {filename}")
    except IOError as e:
        print(f"Error writing to file: {e}")