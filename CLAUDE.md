# Asset Watchdog Agent — CLAUDE.md

## What This Project Does

Monitors a single Google Slides presentation for changes. On every poll cycle, compares the current state against a local JSON snapshot using objectIds as stable identifiers. When changes are detected, immediately sends a structured alert to Slack or Google Chat.

## Core Design Decisions (do not change without discussion)

- **One presentation per instance** — single `PRESENTATION_ID` in `.env`
- **Alert on change, immediately** — no batching, no daily digest
- **objectId-based diffing** — never compare by slide index
- **Snapshot = source of truth** — stored in `/cache/snapshot.json`
- **Reset is explicit** — only via `python main.py --reset`, never automatic

---

## Architecture

```
main.py
  └── poll loop (every N seconds)
        ├── drive_monitor.py   → checks if presentation was modified (Drive API)
        ├── slide_diff.py      → fetches slides, compares against snapshot (Slides API)
        ├── analyzer.py        → sends diff to Gemini, returns business-language summary
        └── notifier.py        → delivers alert to Slack or Google Chat webhook
```

**On `--reset` flag:**
```
main.py --reset
  └── slide_diff.py → fetches current state → overwrites snapshot.json → exits
```

---

## Snapshot Format (`/cache/snapshot.json`)

This is the contract. Do not change the shape without updating `slide_diff.py` and the reset logic.

```json
{
  "presentation_id": "string",
  "presentation_title": "string",
  "last_reported_at": "ISO8601 timestamp",
  "slides": [
    {
      "slide_object_id": "string",
      "slide_index": "integer (informational only, never used for comparison)",
      "title": "string or null",
      "text_elements": [
        {
          "object_id": "string",
          "text": "string"
        }
      ]
    }
  ]
}
```

---

## Diff Logic (implement exactly this way)

Compare current API state vs snapshot **by objectId only**. Never by index.

Three change types to detect:

**1. Slide removed** — `slide_object_id` exists in snapshot but not in current API response.

**2. Slide added** — `slide_object_id` exists in current API response but not in snapshot.

**3. Text modified** — `slide_object_id` matches AND `text_element.object_id` matches AND `text` content differs.

After detecting changes, update `last_reported_at` in the snapshot to now. Do NOT overwrite the full snapshot after a normal diff run — only update `last_reported_at`. The full snapshot is only overwritten on `--reset`.

---

## Reset Behavior (`--reset` flag)

1. Fetch current presentation state from Slides API
2. Overwrite `/cache/snapshot.json` completely with current state
3. Set `last_reported_at` to now
4. Print confirmation and exit — do not start the poll loop

Use case: user wants to zero out all accumulated changes and start tracking from the current state forward.

---

## Alert Format

Send immediately when any change is detected. Do not batch.

The alert must include:
- Presentation title
- Timestamp of detection
- List of changes (human-readable, not technical):
  - "Slide added" → slide title or position
  - "Slide removed" → slide title or position
  - "Text changed in [slide title]" → before and after content
- Gemini's business-language interpretation of what the changes likely mean

---

## Commands

```bash
# Install
pip install -r requirements.txt

# First run (creates initial snapshot, then starts polling)
python main.py

# Reset snapshot to current state
python main.py --reset

# Run tests
pytest tests/
```

---

## Environment Variables (see .env.example)

```
GOOGLE_CREDENTIALS_PATH=./credentials.json
PRESENTATION_ID=your_google_slides_id
GEMINI_API_KEY=your_key
SLACK_WEBHOOK_URL=optional
GOOGLE_CHAT_WEBHOOK_URL=optional
POLL_INTERVAL_SECONDS=60
```

At least one of `SLACK_WEBHOOK_URL` or `GOOGLE_CHAT_WEBHOOK_URL` must be set.

---

## Known Issues to Fix (priority order)

1. **Index-based diff** — `slide_diff.py` currently compares by position. Must be rewritten to use objectIds per the diff logic above.
2. **Shared auth** — `drive_monitor.py` and `slide_diff.py` each authenticate independently. Refactor so `main.py` creates one authenticated service object and passes it to both.
3. **No graceful fallback without credentials** — app crashes on missing `credentials.json`. Add a mock mode that loads a fixture from `/tests/fixtures/` so the loop can be tested without real credentials.

---

## What Not To Build (V1 scope)

- No multi-presentation support
- No Web UI
- No SQLite history log
- No visual diff attachments
- No daily digest mode
- No BYOK interface

These are explicitly out of scope. Do not implement them even if they seem like natural extensions.
