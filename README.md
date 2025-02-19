# Shortcut to OpenAI Summary Script

This Python script fetches stories from Shortcut updated on a specific date, and then uses OpenAI's GPT-4o model to generate a summarized Markdown report.

## Prerequisites

*   **Python 3.7+**
*   **Shortcut API Key:** You need a Shortcut API key with read access to your stories. Set this as an environment variable named `SHORTCUT_API_KEY`.
*   **OpenAI API Key:** You need an OpenAI API key with access to the GPT-4o model. Set this as an environment variable named `OPENAI_API_KEY`.

## Installation

1.  **Clone the repository:**

    ```bash
    git clone <your_repository_url>
    cd <your_repository_directory>
    ```

2.  **Install dependencies:**

    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

## Configuration

1. Before running the script, you **must** set the following environment variables into ./.env file:

    ```bash
    SHORTCUT_API_KEY=<your-api-key>
    OPENAI_API_KEY=<your-api-key>
    ```

## Run
1.  **Example**
    ```bash
    python shortcut.py 2025-01-01
    open -e ./2025-01-01.md
    ```