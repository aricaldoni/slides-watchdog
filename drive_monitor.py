import os
import logging


class DriveMonitor:
    """Checks if a specific presentation was modified via Google Drive API.

    Receives a pre-authenticated Drive service object — does not manage auth.
    """

    def __init__(self, drive_service, presentation_id):
        self.service = drive_service
        self.presentation_id = presentation_id
        self.last_modified_time = None

    def has_changed(self):
        """Check if the monitored presentation has been modified since last check.

        Returns True if a change is detected, False otherwise.
        On the very first call, records the current modifiedTime and returns False.
        """
        try:
            file_meta = self.service.files().get(
                fileId=self.presentation_id,
                fields='id, name, modifiedTime'
            ).execute()

            current_modified = file_meta.get('modifiedTime')
            name = file_meta.get('name', 'Unknown')

            if self.last_modified_time is None:
                # First check — seed the timestamp, don't trigger.
                self.last_modified_time = current_modified
                logging.info(f"Drive monitor initialized for '{name}' (modified: {current_modified})")
                return False

            if current_modified != self.last_modified_time:
                self.last_modified_time = current_modified
                logging.info(f"Change detected in '{name}' (new modifiedTime: {current_modified})")
                return True

            return False

        except Exception as e:
            logging.error(f"Error checking Drive file {self.presentation_id}: {e}")
            return False

    def get_last_editor_info(self):
        """Fetch the most recent revision to identify the last editor.

        Returns a dict with name, email, and time, or None on error.
        """
        try:
            response = self.service.revisions().list(
                fileId=self.presentation_id,
                fields='revisions(lastModifyingUser, modifiedTime)'
            ).execute()

            revisions = response.get('revisions', [])
            if not revisions:
                return None

            last_rev = revisions[-1]
            user = last_rev.get('lastModifyingUser', {})

            return {
                'name': user.get('displayName', 'Unknown'),
                'email': user.get('emailAddress', 'Unknown'),
                'time': last_rev.get('modifiedTime', 'Unknown')
            }
        except Exception as e:
            logging.error(f"Error fetching revisions for {self.presentation_id}: {e}")
            return None
