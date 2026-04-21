# Know exactly what changed in your slide decks—and why it matters.

## The Problem
Teams share presentations constantly, but critical updates often happen in silence. Important pricing, timelines, or strategies change without notice, and catching these shifts manually is impossible when you're managing dozens of decks. You only find out something changed when you're already in the meeting.

## What you get
> "Price on slide 4 dropped from $500 to $420. Use case on slide 9 was replaced. 
> This looks like a proposal revision."

This tool provides a human-readable summary of every meaningful change. Instead of telling you "text was modified," it interprets the shift in strategy or content so you can stay informed without opening a single file.

## Better than native notifications
Google Drive's built-in notifications only tell you *that* a file was edited or who edited it. They don't tell you *what* changed inside the slides. This agent goes deep into the content, compares it to the previous version, and uses AI to explain the business impact of those changes in plain language.

## A note on change attribution
This tool identifies the last editor of the presentation at the moment a change is detected. Please note that if multiple people are collaborating on a deck simultaneously, the attribution will reflect the final person to modify the file before the system performed its check. It is a "last-look" attribution, not a per-character audit log.

## How to run it
1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/asset-watchdog.git
   cd asset-watchdog
   pip install -r requirements.txt
   ```
2. **Google Cloud Setup:**
   - Enable the **Drive API** and **Slides API** in your Google Cloud Console.
   - Download your `credentials.json` file and place it in the project root.
3. **Configure:**
   - Copy `.env.example` to `.env` and add your `PRESENTATION_ID` and `GEMINI_API_KEY`.
   - Add a `SLACK_WEBHOOK_URL` if you want alerts sent to Slack.
4. **Start Monitoring:**
   ```bash
   python main.py
   ```

---

# Developer Documentation

## Architecture Overview
The system operates as a continuous loop that monitors state and interprets deltas:

1.  **Monitor (`drive_monitor.py`)**: Polls the Drive API to check the `modifiedTime` of the target presentation.
2.  **Differ (`slide_diff.py`)**: When a timestamp change is detected, it fetches the full presentation structure and compares it against a local `cache/snapshot.json` using stable `objectIds`.
3.  **Analyzer (`analyzer.py`)**: Sends the structured differences to the Google Gemini API to generate a business-language summary.
4.  **Notifier (`notifier.py`)**: Formats a rich alert (including slide numbers, titles, before/after text, and editor info) and delivers it via Slack or Email.

## Stack and Dependencies
- **Core**: Python 3.11+
- **APIs**: Google Drive v3, Google Slides v1
- **AI**: Google Gemini (via `google-genai` SDK)
- **Delivery**: Slack Webhooks, SMTP (smtplib)
- **Config**: `python-dotenv`

## Developer Setup
1.  Install dependencies: `pip install -r requirements.txt`
2.  Run tests: `pytest tests/`
3.  **Mock Mode**: You can run the agent without Google credentials by setting `MOCK_MODE=true` in your `.env`. This uses fixture data from `tests/fixtures/` to simulate API responses.
4.  **Resetting**: Use `python main.py --reset` to clear the current history and start tracking from the presentation's current state.

## Note on Change Attribution
Attribution is fetched from the Drive Revisions API. The `lastModifyingUser` of the most recent revision is reported. Because the agent polls at intervals (default 60s), it captures the state of the deck at the time of the poll. It does not track every individual keystroke in real-time.
