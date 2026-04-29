"""Tests for Bug 2 — shared authentication.

Verifies that drive_monitor.py and slide_diff.py accept pre-built service
objects as parameters and never invoke Google auth internally.
"""

import json
import os
import shutil
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from drive_monitor import DriveMonitor
from slide_diff import SlideDiffer, CACHE_DIR, SNAPSHOT_PATH


# ── Minimal mock services ───────────────────────────────────────

class _FilesResource:
    def get(self, fileId=None, fields=None):
        return self
    def execute(self):
        return {'id': fileId, 'name': 'Test', 'modifiedTime': '2026-01-01T00:00:00Z'}


class _RevisionsResource:
    def list(self, fileId=None, fields=None):
        return self
    def execute(self):
        return {'revisions': []}


class _MockDrive:
    def files(self):      return _FilesResource()
    def revisions(self):  return _RevisionsResource()


class _PresentationsResource:
    def get(self, presentationId=None):
        return self
    def execute(self):
        return {'title': 'Test', 'slides': []}


class _MockSlides:
    def presentations(self):
        return _PresentationsResource()


@pytest.fixture(autouse=True)
def clean_cache():
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
    yield
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)


# ── Bug 2 tests ─────────────────────────────────────────────────

class TestDriveMonitorSharedAuth:
    def test_accepts_injected_service(self):
        """DriveMonitor works with any injected Drive service object."""
        monitor = DriveMonitor(_MockDrive(), 'pres_001')
        result = monitor.has_changed()
        assert result is False  # first call seeds, never triggers

    def test_does_not_invoke_google_auth(self):
        """drive_monitor.py must not call google_auth_oauthlib or google.oauth2."""
        with patch('google_auth_oauthlib.flow.InstalledAppFlow') as mock_flow, \
             patch('google.auth.transport.requests.Request') as mock_request:
            monitor = DriveMonitor(_MockDrive(), 'pres_001')
            monitor.has_changed()
            monitor.get_last_editor_info()
            mock_flow.assert_not_called()
            mock_request.assert_not_called()

    def test_module_has_no_auth_imports(self):
        """drive_monitor module must not import google_auth_oauthlib or google.oauth2."""
        import drive_monitor as dm
        import sys
        # The module itself should not pull in auth libraries
        assert not hasattr(dm, 'InstalledAppFlow'), \
            "drive_monitor imported InstalledAppFlow — auth should stay in main.py"
        assert not hasattr(dm, 'flow'), \
            "drive_monitor imported google_auth_oauthlib.flow"


class TestSlideDifferSharedAuth:
    def test_accepts_injected_service(self):
        """SlideDiffer works with any injected Slides service object."""
        differ = SlideDiffer(_MockSlides())
        result = differ.get_diff('pres_001')
        assert result is not None
        assert result['changes'] == []  # first run seeds, no diff

    def test_does_not_invoke_google_auth(self):
        """slide_diff.py must not call google_auth_oauthlib or google.oauth2."""
        with patch('google_auth_oauthlib.flow.InstalledAppFlow') as mock_flow, \
             patch('google.auth.transport.requests.Request') as mock_request:
            differ = SlideDiffer(_MockSlides())
            differ.get_diff('pres_001')
            mock_flow.assert_not_called()
            mock_request.assert_not_called()

    def test_module_has_no_auth_imports(self):
        """slide_diff module must not import google_auth_oauthlib or google.oauth2."""
        import slide_diff as sd
        assert not hasattr(sd, 'InstalledAppFlow'), \
            "slide_diff imported InstalledAppFlow — auth should stay in main.py"
        assert not hasattr(sd, 'flow'), \
            "slide_diff imported google_auth_oauthlib.flow"

    def test_reset_snapshot_accepts_injected_service(self):
        """reset_snapshot also uses only the injected service, no internal auth."""
        with patch('google_auth_oauthlib.flow.InstalledAppFlow') as mock_flow:
            differ = SlideDiffer(_MockSlides())
            differ.reset_snapshot('pres_001')
            mock_flow.assert_not_called()
