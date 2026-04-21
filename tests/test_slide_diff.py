"""Tests for slide_diff.py — objectId-based diffing logic.

These tests inject a mock Slides API service object so no credentials are needed.
They exercise the three change types: slide_added, slide_removed, text_modified,
and verify that reordering slides by index does NOT trigger false positives.
"""

import json
import os
import shutil
import pytest

from slide_diff import SlideDiffer, CACHE_DIR, SNAPSHOT_PATH


# ── Helpers ────────────────────────────────────────────────────

def _make_presentation(title, slides):
    """Build a fake Google Slides API response."""
    api_slides = []
    for s in slides:
        page_elements = []
        for elem in s.get("elements", []):
            page_elements.append({
                "objectId": elem["object_id"],
                "shape": {
                    "text": {
                        "textElements": [
                            {"textRun": {"content": elem["text"]}}
                        ]
                    }
                }
            })
        api_slides.append({
            "objectId": s["object_id"],
            "pageElements": page_elements,
        })

    return {
        "title": title,
        "slides": api_slides,
    }


class MockPresentationsResource:
    """Mimics service.presentations().get(presentationId=...).execute()"""
    def __init__(self, presentation_data):
        self._data = presentation_data

    def get(self, presentationId=None):
        return self

    def execute(self):
        return self._data


class MockSlidesService:
    """Mimics the Google Slides API service object."""
    def __init__(self, presentation_data):
        self._presentations = MockPresentationsResource(presentation_data)

    def presentations(self):
        return self._presentations


def _make_snapshot(presentation_id, title, slides):
    """Build a snapshot dict matching the contract in CLAUDE.md."""
    return {
        "presentation_id": presentation_id,
        "presentation_title": title,
        "last_reported_at": "2025-01-01T00:00:00+00:00",
        "slides": slides,
    }


def _write_snapshot(snapshot):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f)


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure a clean cache directory for every test."""
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
    yield
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)


# ── Tests ──────────────────────────────────────────────────────

class TestFirstRun:
    def test_creates_snapshot_on_first_run(self):
        api_data = _make_presentation("Deck A", [
            {"object_id": "s1", "elements": [{"object_id": "e1", "text": "Hello"}]},
        ])
        service = MockSlidesService(api_data)
        differ = SlideDiffer(service)

        result = differ.get_diff("pres123")

        assert result is not None
        assert result["changes"] == []
        assert os.path.exists(SNAPSHOT_PATH)

    def test_snapshot_contains_object_ids(self):
        api_data = _make_presentation("Deck A", [
            {"object_id": "s1", "elements": [{"object_id": "e1", "text": "Hello"}]},
        ])
        service = MockSlidesService(api_data)
        differ = SlideDiffer(service)
        differ.get_diff("pres123")

        with open(SNAPSHOT_PATH) as f:
            snap = json.load(f)

        assert snap["slides"][0]["slide_object_id"] == "s1"
        assert snap["slides"][0]["text_elements"][0]["object_id"] == "e1"


class TestSlideAdded:
    def test_detects_added_slide(self):
        snapshot = _make_snapshot("pres123", "Deck A", [
            {"slide_object_id": "s1", "slide_index": 0, "title": "Intro",
             "text_elements": [{"object_id": "e1", "text": "Hello"}]},
        ])
        _write_snapshot(snapshot)

        api_data = _make_presentation("Deck A", [
            {"object_id": "s1", "elements": [{"object_id": "e1", "text": "Hello"}]},
            {"object_id": "s2", "elements": [{"object_id": "e2", "text": "New slide content"}]},
        ])
        service = MockSlidesService(api_data)
        differ = SlideDiffer(service)

        result = differ.get_diff("pres123")

        assert len(result["changes"]) == 1
        assert result["changes"][0]["change_type"] == "slide_added"
        assert result["changes"][0]["slide_object_id"] == "s2"


class TestSlideRemoved:
    def test_detects_removed_slide(self):
        snapshot = _make_snapshot("pres123", "Deck A", [
            {"slide_object_id": "s1", "slide_index": 0, "title": "Intro",
             "text_elements": [{"object_id": "e1", "text": "Hello"}]},
            {"slide_object_id": "s2", "slide_index": 1, "title": "Details",
             "text_elements": [{"object_id": "e2", "text": "World"}]},
        ])
        _write_snapshot(snapshot)

        api_data = _make_presentation("Deck A", [
            {"object_id": "s1", "elements": [{"object_id": "e1", "text": "Hello"}]},
        ])
        service = MockSlidesService(api_data)
        differ = SlideDiffer(service)

        result = differ.get_diff("pres123")

        assert len(result["changes"]) == 1
        assert result["changes"][0]["change_type"] == "slide_removed"
        assert result["changes"][0]["slide_object_id"] == "s2"


class TestTextModified:
    def test_detects_text_change(self):
        snapshot = _make_snapshot("pres123", "Deck A", [
            {"slide_object_id": "s1", "slide_index": 0, "title": "Pricing",
             "text_elements": [{"object_id": "e1", "text": "$500/mo"}]},
        ])
        _write_snapshot(snapshot)

        api_data = _make_presentation("Deck A", [
            {"object_id": "s1", "elements": [{"object_id": "e1", "text": "$420/mo"}]},
        ])
        service = MockSlidesService(api_data)
        differ = SlideDiffer(service)

        result = differ.get_diff("pres123")

        assert len(result["changes"]) == 1
        change = result["changes"][0]
        assert change["change_type"] == "text_modified"
        assert "$500/mo" in change["before"]
        assert "$420/mo" in change["after"]


class TestReorderDoesNotTriggerDiff:
    def test_reordering_slides_no_false_positive(self):
        """If slides are reordered but content is identical, no changes should appear."""
        snapshot = _make_snapshot("pres123", "Deck A", [
            {"slide_object_id": "s1", "slide_index": 0, "title": "Slide A",
             "text_elements": [{"object_id": "e1", "text": "AAA"}]},
            {"slide_object_id": "s2", "slide_index": 1, "title": "Slide B",
             "text_elements": [{"object_id": "e2", "text": "BBB"}]},
        ])
        _write_snapshot(snapshot)

        # API returns same slides in reversed order
        api_data = _make_presentation("Deck A", [
            {"object_id": "s2", "elements": [{"object_id": "e2", "text": "BBB"}]},
            {"object_id": "s1", "elements": [{"object_id": "e1", "text": "AAA"}]},
        ])
        service = MockSlidesService(api_data)
        differ = SlideDiffer(service)

        result = differ.get_diff("pres123")

        assert result["changes"] == []


class TestNoChangeUpdatesNothing:
    def test_no_change_does_not_update_timestamp(self):
        original_ts = "2025-01-01T00:00:00+00:00"
        snapshot = _make_snapshot("pres123", "Deck A", [
            {"slide_object_id": "s1", "slide_index": 0, "title": "Intro",
             "text_elements": [{"object_id": "e1", "text": "Hello"}]},
        ])
        _write_snapshot(snapshot)

        api_data = _make_presentation("Deck A", [
            {"object_id": "s1", "elements": [{"object_id": "e1", "text": "Hello"}]},
        ])
        service = MockSlidesService(api_data)
        differ = SlideDiffer(service)
        differ.get_diff("pres123")

        with open(SNAPSHOT_PATH) as f:
            snap = json.load(f)
        assert snap["last_reported_at"] == original_ts


class TestResetSnapshot:
    def test_reset_overwrites_snapshot(self):
        old_snapshot = _make_snapshot("pres123", "Old Title", [
            {"slide_object_id": "old_s1", "slide_index": 0, "title": "Old",
             "text_elements": []},
        ])
        _write_snapshot(old_snapshot)

        api_data = _make_presentation("New Title", [
            {"object_id": "new_s1", "elements": [{"object_id": "ne1", "text": "Fresh"}]},
        ])
        service = MockSlidesService(api_data)
        differ = SlideDiffer(service)

        result = differ.reset_snapshot("pres123")

        assert result is True
        with open(SNAPSHOT_PATH) as f:
            snap = json.load(f)
        assert snap["presentation_title"] == "New Title"
        assert snap["slides"][0]["slide_object_id"] == "new_s1"
