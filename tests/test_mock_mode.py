"""Tests for mock mode — verifies the app can run without credentials.

Uses mock service objects that load data from tests/fixtures/.
"""

import json
import os
import shutil
import pytest
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mock_services import MockDriveService, MockSlidesService, build_mock_services
from drive_monitor import DriveMonitor
from slide_diff import SlideDiffer, CACHE_DIR, SNAPSHOT_PATH


@pytest.fixture(autouse=True)
def clean_cache():
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
    yield
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)


class TestMockServices:
    def test_build_mock_services_returns_pair(self):
        drive, slides = build_mock_services()
        assert isinstance(drive, MockDriveService)
        assert isinstance(slides, MockSlidesService)

    def test_mock_drive_returns_file_metadata(self):
        drive = MockDriveService()
        result = drive.files().get(fileId="test123", fields="id,name,modifiedTime").execute()
        assert result['id'] == "test123"
        assert 'modifiedTime' in result

    def test_mock_slides_returns_presentation(self):
        slides = MockSlidesService()
        result = slides.presentations().get(presentationId="test123").execute()
        assert 'title' in result
        assert 'slides' in result
        assert len(result['slides']) > 0


class TestMockDriveMonitor:
    def test_monitor_works_with_mock(self):
        drive = MockDriveService()
        monitor = DriveMonitor(drive, "test123")

        # First call seeds, returns False
        assert monitor.has_changed() is False

        # Second call — MockDriveService returns a new timestamp each time,
        # so it should detect a "change".
        assert monitor.has_changed() is True

    def test_monitor_fetches_editor_info(self):
        drive = MockDriveService()
        monitor = DriveMonitor(drive, "test123")

        info = monitor.get_last_editor_info()
        assert info is not None
        assert info['name'] == 'Mock Editor'
        assert info['email'] == 'mock@example.com'
        assert 'time' in info


class TestMockSlideDiffer:
    def test_differ_creates_snapshot_from_fixture(self):
        slides = MockSlidesService()
        differ = SlideDiffer(slides)
        result = differ.get_diff("test123")

        assert result is not None
        assert result['changes'] == []
        assert os.path.exists(SNAPSHOT_PATH)

        with open(SNAPSHOT_PATH) as f:
            snap = json.load(f)
        assert snap['presentation_title'].startswith("2026 Sales Expansion")
        assert len(snap['slides']) == 4

    def test_differ_detects_no_change_on_second_run(self):
        slides = MockSlidesService()
        differ = SlideDiffer(slides)

        # First run — seed
        differ.get_diff("test123")
        # Second run — fixture is unchanged
        result = differ.get_diff("test123")

        assert result['changes'] == []

    def test_reset_then_diff_shows_no_changes(self):
        slides = MockSlidesService()
        differ = SlideDiffer(slides)

        differ.reset_snapshot("test123")
        result = differ.get_diff("test123")

        assert result['changes'] == []
