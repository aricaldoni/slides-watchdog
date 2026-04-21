"""Mock Google API services for testing without credentials.

Loads fixture data from tests/fixtures/ and exposes the same interface as
the real google-api-python-client service objects.
"""

import json
import os
import logging
from datetime import datetime, timezone

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'tests', 'fixtures')


class MockDriveFilesResource:
    """Mimics service.files().get(...).execute()"""

    def __init__(self):
        self._call_count = 0

    def get(self, fileId=None, fields=None):
        self._file_id = fileId
        return self

    def execute(self):
        self._call_count += 1
        # Alternate: first call returns baseline, subsequent calls simulate a change
        return {
            'id': self._file_id,
            'name': 'Mock Presentation',
            'modifiedTime': datetime.now(timezone.utc).isoformat(),
        }


class MockDriveRevisionsResource:
    """Mimics service.revisions().list(...).execute()"""

    def list(self, fileId=None, fields=None):
        return self

    def execute(self):
        return {
            'revisions': [
                {
                    'lastModifyingUser': {
                        'displayName': 'Mock Editor',
                        'emailAddress': 'mock@example.com'
                    },
                    'modifiedTime': datetime.now(timezone.utc).isoformat()
                }
            ]
        }


class MockDriveService:
    """Mimics the Google Drive API service object."""

    def __init__(self):
        self._files = MockDriveFilesResource()
        self._revisions = MockDriveRevisionsResource()

    def files(self):
        return self._files

    def revisions(self):
        return self._revisions


class MockPresentationsResource:
    """Mimics service.presentations().get(...).execute()

    Loads data from tests/fixtures/mock_presentation.json.
    """

    def __init__(self, fixture_path=None):
        self._fixture_path = fixture_path or os.path.join(FIXTURES_DIR, 'mock_presentation.json')
        if not os.path.exists(self._fixture_path):
            raise FileNotFoundError(
                f"Mock fixture not found at {self._fixture_path}. "
                "Create tests/fixtures/mock_presentation.json to use mock mode."
            )

    def get(self, presentationId=None):
        return self

    def execute(self):
        with open(self._fixture_path, 'r') as f:
            return json.load(f)


class MockSlidesService:
    """Mimics the Google Slides API service object."""

    def __init__(self, fixture_path=None):
        self._presentations = MockPresentationsResource(fixture_path)

    def presentations(self):
        return self._presentations


def build_mock_services():
    """Build mock Drive and Slides service objects.

    Returns (drive_service, slides_service) just like main.build_services().
    """
    logging.info("[MOCK MODE] Using fixture data from tests/fixtures/")
    return MockDriveService(), MockSlidesService()
