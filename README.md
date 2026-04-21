--- PART 1: FOR USERS ---

# Presentation Intelligence Agent
Automatically track and understand changes in your Google Slides presentations.

## The Problem
Teams often update critical slide decks—like sales proposals or strategic roadmaps—without notifying anyone else. You might go into a meeting only to discover that a price or a timeline was changed an hour ago by someone else on your team. Finding these small but important shifts manually is impossible when you're managing dozens of active presentations.

## What You Get
> "Price on slide 4 dropped from $10,000 to $8,500 (Promotional). 
> A new slide was added: Competitor Analysis. 
> This looks like a pricing adjustment ahead of a competitive pitch."

This is a real-world example of the message you receive in Slack, Google Chat, or Email whenever a change is detected.

## Why This Is Different
Google Drive's built-in alerts only tell you *that* a file was edited and who did it. They don't tell you *what* happened inside the slides. This tool reads the actual content, compares it to the previous version, and uses AI to explain the business impact of those changes in plain language so you never have to hunt for updates again.

## A Note on Change Attribution
This tool identifies the last editor of the presentation at the moment a change is detected using the Drive Revision history. Because people often collaborate at the same time, this reflects the final person to save the file before our system checked it. It provides a helpful trail of who made the most recent updates, rather than a character-by-character audit log. We clearly label this as the "Last editor" to ensure transparency.

---

## How to Run It

### Requirements
- Python 3.11+
- A Google Cloud project with Drive API and Slides API enabled
- A Gemini API key (the free tier works perfectly)
- A Slack or Google Chat webhook URL (optional)

### Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/asset-watchdog.git
   cd asset-watchdog
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Google API Credentials:**
   - Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
   - Enable the **Google Drive API** and **Google Slides API**.
   - Create an **OAuth 2.0 Client ID** (Desktop Application).
   - Download the JSON file, rename it to `credentials.json`, and place it in the project folder.
4. **Configure:**
   - Copy `.env.example` to a new file named `.env`.
   - Fill in your presentation ID and API keys (see the Configuration section below).
5. **Start the agent:**
   ```bash
   python main.py
   ```

> [!WARNING]
> **OAuth Consent:** On the first run, your web browser will automatically open and ask for permission to access your Google account. This is a standard security step and only happens once.

### Configuration (.env)
```bash
# Path to your Google Cloud credentials file
GOOGLE_CREDENTIALS_PATH=./credentials.json

# The ID of the slide deck you want to watch (found in its URL)
PRESENTATION_ID=your_google_slides_id

# Your Gemini AI key for change interpretation
GEMINI_API_KEY=your_gemini_api_key

# The language for your alerts (en or es)
ALERT_LANGUAGE=en

# Where to send Slack alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Email address to receive alerts
NOTIFY_EMAIL=your_email@example.com

# SMTP settings for sending emails
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@example.com
SMTP_PASS=your_app_password

# How often to check for updates (in seconds)
POLL_INTERVAL_SECONDS=60

# Set to true to test without real Google/AI credentials
MOCK_MODE=false
```

### Reset
If you want the agent to "forget" the current state of a presentation and start fresh, run `python main.py --reset`. This is useful if you've made many changes yourself and don't want to receive a massive alert for them, or if you've switched to a different presentation ID.

--- PART 2: FOR DEVELOPERS ---

---

## Architecture
```text
main.py (poll loop)
  ├── drive_monitor.py   → detects file was modified
  ├── slide_diff.py      → extracts what changed and where  
  ├── analyzer.py        → interprets changes using Gemini AI
  └── notifier.py        → sends alert to Slack, Google Chat, or Email
```

1. **Change Detection:** Watches the Drive file metadata for a new "Modified Time" timestamp.
2. **Content Extraction:** Fetches the full structure of the presentation and compares every element against a local snapshot.
3. **Semantic Analysis:** Passes the raw changes to Gemini AI to generate a business-focused summary.
4. **Notification:** Formats the final report with localized labels and dispatches it to configured channels.

## Stack
- **Google API Client:** Handles all communication with Drive and Slides services.
- **Google GenAI SDK:** Orchestrates the semantic interpretation of content changes.
- **Python-Dotenv:** Manages environment variables and secrets securely.
- **Pytest:** Provides the testing framework for the extraction and notification logic.

## Running Tests
Run the full test suite with:
```bash
python -m pytest tests/ -v
```
The **21 tests** cover:
- Precision of the comparison engine (added, removed, or modified slides).
- Localized alert formatting for Slack and Email.
- Integrity of the "Mock Mode" for development without live API access.
- Successful extraction of editor attribution from revision history.

## Roadmap
- **Visual Interpretation:** Use AI vision to detect changes in images and layouts, not just text.
- **Folder Monitoring:** Watch an entire Google Drive folder for changes in any presentation.
- **Deep Linking:** Include links in the alert that open the presentation directly to the modified slide.
- **PowerPoint Support:** Automatically convert and monitor uploaded `.pptx` files.
