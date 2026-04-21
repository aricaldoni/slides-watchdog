"""Presentation Intelligence Agent — Entry Point.

Creates shared Google API service objects and passes them to all modules.
Handles the --reset flag and the poll loop.
"""

import os
from dotenv import load_dotenv

# Load .env before any module that reads env vars at import time
load_dotenv()

import sys
import time
import logging
import argparse
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from drive_monitor import DriveMonitor
from slide_diff import SlideDiffer
from analyzer import PresentationAnalyzer
from notifier import Notifier

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler(),
    ]
)

SCOPES = [
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/presentations.readonly',
]


# ── Authentication (single source of truth) ─────────────────────

TOKEN_PATH = os.getenv('TOKEN_PATH', 'token.pickle')


def authenticate(credentials_path, token_path=None):
    """Authenticate once and return Google credentials.

    Used to build both Drive and Slides service objects.
    """
    if token_path is None:
        token_path = TOKEN_PATH

    creds = None
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found at {credentials_path}. "
                    "Set MOCK_MODE=true in .env to run without credentials."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return creds


def build_services(creds):
    """Build Drive and Slides service objects from shared credentials."""
    drive_service = build('drive', 'v3', credentials=creds)
    slides_service = build('slides', 'v1', credentials=creds)
    return drive_service, slides_service


# ── Main ────────────────────────────────────────────────────────

def run_agent():

    parser = argparse.ArgumentParser(description="Presentation Intelligence Agent")
    parser.add_argument('--reset', action='store_true',
                        help='Reset snapshot to current state and exit.')
    args = parser.parse_args()

    # Configuration
    PRESENTATION_ID = os.getenv('PRESENTATION_ID')
    POLL_INTERVAL = int(os.getenv('POLL_INTERVAL_SECONDS', 60))
    CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', './credentials.json')

    if not PRESENTATION_ID:
        logging.error("PRESENTATION_ID not set in .env. Exiting.")
        return

    # Authenticate once, build shared services
    MOCK_MODE = os.getenv('MOCK_MODE', 'false').lower() == 'true'

    if MOCK_MODE or not os.path.exists(CREDENTIALS_PATH):
        if not MOCK_MODE:
            logging.warning(f"Credentials not found at {CREDENTIALS_PATH}. Falling back to mock mode.")
        from mock_services import build_mock_services
        drive_service, slides_service = build_mock_services()
    else:
        try:
            creds = authenticate(CREDENTIALS_PATH)
            drive_service, slides_service = build_services(creds)
        except FileNotFoundError as e:
            logging.error(str(e))
            return

    # Wire modules with shared services
    monitor = DriveMonitor(drive_service, PRESENTATION_ID)
    differ = SlideDiffer(slides_service)
    analyzer = PresentationAnalyzer()
    notifier = Notifier()

    # Handle --reset
    if args.reset:
        logging.info("Resetting snapshot...")
        success = differ.reset_snapshot(PRESENTATION_ID)
        if success:
            logging.info("Snapshot reset complete. Exiting.")
        else:
            logging.error("Snapshot reset failed.")
        return

    logging.info(f"Monitoring presentation {PRESENTATION_ID} every {POLL_INTERVAL}s.")

    while True:
        try:
            if monitor.has_changed():
                diff_data = differ.get_diff(PRESENTATION_ID)

                if diff_data and diff_data['changes']:
                    logging.info(f"Processing {len(diff_data['changes'])} changes...")

                    summary = analyzer.analyze_changes(diff_data)
                    logging.info("Analysis complete.")

                    # Fetch last editor attribution
                    diff_data['last_editor'] = monitor.get_last_editor_info()

                    notifier.notify(summary, diff_data)
                    logging.info("Notification sent.")
                else:
                    logging.info("Drive reports a change but no semantic diff detected.")

        except Exception as e:
            logging.error(f"Error in main loop: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_agent()
