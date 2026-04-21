import os
import json
import logging
from datetime import datetime, timezone

CACHE_DIR = os.getenv('CACHE_DIR', './cache')
SNAPSHOT_PATH = os.path.join(CACHE_DIR, 'snapshot.json')


class SlideDiffer:
    """Fetches slide content via Slides API and compares against a local snapshot.

    All comparisons use objectIds as stable identifiers — never slide index.
    The snapshot is only fully overwritten on explicit reset.
    """

    def __init__(self, slides_service):
        self.service = slides_service
        os.makedirs(CACHE_DIR, exist_ok=True)

    # ── Public API ──────────────────────────────────────────────

    def get_diff(self, presentation_id):
        """Compare current API state vs snapshot by objectId.

        Returns a diff dict with changes, or None on error.
        Only updates ``last_reported_at`` in the snapshot — never overwrites it.
        If no snapshot exists yet, creates one and returns no changes.
        """
        current_state = self._fetch_presentation(presentation_id)
        if current_state is None:
            return None

        snapshot = self._load_snapshot()

        # First run — no snapshot exists. Seed it and report no changes.
        if snapshot is None:
            logging.info("No snapshot found. Creating initial snapshot.")
            self._save_snapshot(current_state)
            return {
                "presentation_id": presentation_id,
                "presentation_title": current_state["presentation_title"],
                "changes": [],
            }

        changes = self._compute_changes(snapshot, current_state)

        # Only touch last_reported_at, never overwrite the full snapshot.
        if changes:
            self._update_last_reported_at()

        return {
            "presentation_id": presentation_id,
            "presentation_title": current_state["presentation_title"],
            "changes": changes,
        }

    def reset_snapshot(self, presentation_id):
        """Fetch current state and fully overwrite snapshot.json.

        Used by ``python main.py --reset``.
        """
        current_state = self._fetch_presentation(presentation_id)
        if current_state is None:
            logging.error("Failed to fetch presentation for reset.")
            return False

        self._save_snapshot(current_state)
        logging.info(f"Snapshot reset for '{current_state['presentation_title']}'.")
        return True

    # ── Diff Logic ──────────────────────────────────────────────

    def _compute_changes(self, snapshot, current_state):
        """Compare snapshot vs current by objectId only."""
        changes = []

        snap_slides = {s["slide_object_id"]: s for s in snapshot.get("slides", [])}
        curr_slides = {s["slide_object_id"]: s for s in current_state.get("slides", [])}

        snap_ids = set(snap_slides.keys())
        curr_ids = set(curr_slides.keys())

        # 1. Slides removed
        for oid in snap_ids - curr_ids:
            slide = snap_slides[oid]
            changes.append({
                "slide_object_id": oid,
                "slide_index": slide["slide_index"],
                "slide_title": slide.get("title") or f"Slide (position {slide['slide_index'] + 1})",
                "change_type": "slide_removed",
                "before": self._slide_text_summary(slide),
                "after": None,
            })

        # 2. Slides added
        for oid in curr_ids - snap_ids:
            slide = curr_slides[oid]
            changes.append({
                "slide_object_id": oid,
                "slide_index": slide["slide_index"],
                "slide_title": slide.get("title") or f"Slide (position {slide['slide_index'] + 1})",
                "change_type": "slide_added",
                "before": None,
                "after": self._slide_text_summary(slide),
            })

        # 3. Text modified — only for slides present in both
        for oid in snap_ids & curr_ids:
            snap_slide = snap_slides[oid]
            curr_slide = curr_slides[oid]
            text_changes = self._diff_text_elements(snap_slide, curr_slide)
            if text_changes:
                title = curr_slide.get("title") or f"Slide (position {curr_slide['slide_index'] + 1})"
                changes.append({
                    "slide_object_id": oid,
                    "slide_index": curr_slide["slide_index"],
                    "slide_title": title,
                    "change_type": "text_modified",
                    "before": text_changes["before"],
                    "after": text_changes["after"],
                })

        return changes

    def _diff_text_elements(self, snap_slide, curr_slide):
        """Compare text elements within a single slide by object_id."""
        snap_elems = {e["object_id"]: e["text"] for e in snap_slide.get("text_elements", [])}
        curr_elems = {e["object_id"]: e["text"] for e in curr_slide.get("text_elements", [])}

        before_parts = []
        after_parts = []

        all_ids = set(snap_elems.keys()) | set(curr_elems.keys())

        for eid in all_ids:
            old_text = snap_elems.get(eid)
            new_text = curr_elems.get(eid)

            if old_text != new_text:
                before_parts.append(old_text or "(element removed)")
                after_parts.append(new_text or "(element removed)")

        if not before_parts:
            return None

        return {
            "before": "\n".join(before_parts),
            "after": "\n".join(after_parts),
        }

    # ── Extraction ──────────────────────────────────────────────

    def _fetch_presentation(self, presentation_id):
        """Fetch slides from API and return structured state matching snapshot format."""
        try:
            presentation = self.service.presentations().get(
                presentationId=presentation_id
            ).execute()

            title = presentation.get("title", "Untitled")
            slides = presentation.get("slides", [])

            structured_slides = []
            for i, slide in enumerate(slides):
                slide_obj_id = slide.get("objectId")
                slide_title = None
                text_elements = []

                for element in slide.get("pageElements", []):
                    elem_obj_id = element.get("objectId")
                    if "shape" in element and "text" in element["shape"]:
                        parts = []
                        for text_run in element["shape"]["text"].get("textElements", []):
                            if "textRun" in text_run:
                                parts.append(text_run["textRun"]["content"])
                        full_text = "".join(parts).strip()
                        if full_text:
                            text_elements.append({
                                "object_id": elem_obj_id,
                                "text": full_text,
                            })
                            # Heuristic: first text element is the slide title
                            if slide_title is None:
                                slide_title = full_text

                structured_slides.append({
                    "slide_object_id": slide_obj_id,
                    "slide_index": i,
                    "title": slide_title,
                    "text_elements": text_elements,
                })

            return {
                "presentation_id": presentation_id,
                "presentation_title": title,
                "last_reported_at": datetime.now(timezone.utc).isoformat(),
                "slides": structured_slides,
            }

        except Exception as e:
            logging.error(f"Error fetching presentation {presentation_id}: {e}")
            return None

    # ── Snapshot I/O ────────────────────────────────────────────

    def _load_snapshot(self):
        """Load snapshot.json, or return None if it doesn't exist."""
        if not os.path.exists(SNAPSHOT_PATH):
            return None
        try:
            with open(SNAPSHOT_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logging.error(f"Failed to read snapshot: {e}")
            return None

    def _save_snapshot(self, state):
        """Fully overwrite snapshot.json (used only on reset or first run)."""
        with open(SNAPSHOT_PATH, "w") as f:
            json.dump(state, f, indent=2)

    def _update_last_reported_at(self):
        """Update only the last_reported_at field in the existing snapshot."""
        snapshot = self._load_snapshot()
        if snapshot:
            snapshot["last_reported_at"] = datetime.now(timezone.utc).isoformat()
            self._save_snapshot(snapshot)

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _slide_text_summary(slide):
        """Concatenate all text elements in a slide for display."""
        texts = [e["text"] for e in slide.get("text_elements", []) if e.get("text")]
        return "\n".join(texts) if texts else None
