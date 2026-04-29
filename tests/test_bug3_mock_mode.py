"""Tests for Bug 3 — mock mode / graceful fallback without credentials.

Covers:
1. With --mock or without credentials.json, no Google API or credentials file
   is accessed.
2. Integration: running one diff cycle in mock mode detects exactly 1 change
   (the text change in elem_002b on slide_002 between the two fixtures).
"""

import json
import os
import shutil
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mock_services import (
    MockDriveService,
    MockSlidesService,
    StatefulMockSlidesService,
    build_mock_services,
    SNAPSHOT_FIXTURE,
    CURRENT_STATE_FIXTURE,
)
from drive_monitor import DriveMonitor
from slide_diff import SlideDiffer, CACHE_DIR, SNAPSHOT_PATH

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture(autouse=True)
def clean_cache():
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
    yield
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)


# ── No-credentials tests ────────────────────────────────────────

class TestNoCrendentialsNeverReadCredentialsFile:
    def test_mock_services_build_without_credentials_json(self, tmp_path):
        """build_mock_services() succeeds even if credentials.json is absent."""
        fake_creds = tmp_path / "credentials.json"
        assert not fake_creds.exists()
        # Must not raise
        drive, slides = build_mock_services()
        assert drive is not None
        assert slides is not None

    def test_mock_mode_never_opens_credentials_file(self):
        """In mock mode, builtins.open is never called on a credentials path."""
        real_open = open

        def guarded_open(path, *args, **kwargs):
            assert 'credentials' not in str(path).lower(), \
                f"Mock mode opened credentials file: {path}"
            return real_open(path, *args, **kwargs)

        with patch('builtins.open', side_effect=guarded_open):
            drive, slides = build_mock_services()
            monitor = DriveMonitor(drive, 'pres_001')
            differ = SlideDiffer(slides)
            monitor.has_changed()
            differ.get_diff('pres_001')

    def test_mock_mode_does_not_call_google_api_build(self):
        """build_mock_services() must not call googleapiclient.discovery.build."""
        with patch('googleapiclient.discovery.build') as mock_build:
            build_mock_services()
            mock_build.assert_not_called()

    def test_mock_mode_does_not_invoke_auth_flow(self):
        """Mock mode must never trigger InstalledAppFlow or Request."""
        with patch('google_auth_oauthlib.flow.InstalledAppFlow') as mock_flow, \
             patch('google.auth.transport.requests.Request') as mock_request:
            drive, slides = build_mock_services()
            monitor = DriveMonitor(drive, 'pres_001')
            differ = SlideDiffer(slides)
            monitor.has_changed()
            differ.get_diff('pres_001')
            mock_flow.assert_not_called()
            mock_request.assert_not_called()


# ── Integration tests ────────────────────────────────────────────

class TestMockModeIntegration:
    def test_first_poll_seeds_snapshot_no_changes(self):
        """First get_diff() with snapshot_fixture seeds the cache and returns no changes."""
        slides = MockSlidesService(fixture_path=SNAPSHOT_FIXTURE)
        differ = SlideDiffer(slides)

        result = differ.get_diff('pres_001')

        assert result is not None
        assert result['changes'] == []
        assert os.path.exists(SNAPSHOT_PATH)

    def test_second_poll_detects_exactly_one_change(self):
        """After seeding from snapshot_fixture, switching to current_state_fixture detects 1 change."""
        # Seed snapshot from snapshot_fixture (baseline state)
        slides_seed = MockSlidesService(fixture_path=SNAPSHOT_FIXTURE)
        differ = SlideDiffer(slides_seed)
        seed_result = differ.get_diff('pres_001')
        assert seed_result['changes'] == []

        # Swap in current_state_fixture (slide_002 / elem_002b text changed)
        differ.service = MockSlidesService(fixture_path=CURRENT_STATE_FIXTURE)
        result = differ.get_diff('pres_001')

        assert len(result['changes']) == 1
        change = result['changes'][0]
        assert change['change_type'] == 'text_modified'
        assert change['slide_object_id'] == 'slide_002'
        assert '$4.2B' in change['before']
        assert '$5.8B' in change['after']

    def test_stateful_service_detects_change_on_second_call(self):
        """StatefulMockSlidesService seeds on call 1 and triggers a diff on call 2."""
        differ = SlideDiffer(StatefulMockSlidesService())

        first = differ.get_diff('pres_001')
        assert first['changes'] == []

        second = differ.get_diff('pres_001')
        assert len(second['changes']) == 1
        assert second['changes'][0]['change_type'] == 'text_modified'

    def test_build_mock_services_returns_stateful_slides(self):
        """build_mock_services() returns a StatefulMockSlidesService."""
        drive, slides = build_mock_services()
        assert isinstance(slides, StatefulMockSlidesService)

    def test_full_mock_cycle_logs_mock_mode(self, caplog):
        """build_mock_services() logs [MOCK MODE] Running without real credentials."""
        import logging
        with caplog.at_level(logging.INFO):
            build_mock_services()
        assert any('[MOCK MODE]' in r.message for r in caplog.records)
