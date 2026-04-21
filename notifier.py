import os
import logging
import requests
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()


class Notifier:
    def __init__(self):
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.notify_email = os.getenv('NOTIFY_EMAIL')
        self.smtp_server = os.getenv('SMTP_SERVER', 'localhost')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_pass = os.getenv('SMTP_PASS')

    def notify(self, summary, diff_data):
        """Dispatches notifications to all configured channels.

        Args:
            summary: Business-language analysis from the analyzer.
            diff_data: Full diff dict from SlideDiffer.get_diff(), containing
                       presentation_id, presentation_title, and changes list.
        """
        if not summary or not diff_data:
            return

        message = self._format_alert(summary, diff_data)

        # Slack notification
        if self.slack_webhook_url:
            self._send_slack(message)

        # Email notification
        if self.notify_email:
            title = diff_data.get('presentation_title', 'Unknown Presentation')
            self._send_email(f"Change detected in {title}", message)

    def _format_alert(self, summary, diff_data):
        """Build a rich, human-readable alert from the full diff context."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = diff_data.get('presentation_title', 'Unknown Presentation')
        pres_id = diff_data.get('presentation_id', '')
        pres_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        changes = diff_data.get('changes', [])

        lines = [
            f"*📊 Presentation Change Detected*",
            f"*Title:* {title}",
            f"*URL:* {pres_url}",
            f"*Detected at:* {timestamp}",
        ]

        last_editor = diff_data.get('last_editor')
        if last_editor:
            lines.append(f"*Last editor at time of change:* {last_editor['name']} ({last_editor['email']}) at {last_editor['time']}")

        lines.extend([
            "",
            f"*Changes ({len(changes)}):*",
        ])

        for change in changes:
            slide_num = change.get('slide_index', 0) + 1
            slide_title = change.get('slide_title', 'Untitled')
            change_type = change.get('change_type', 'unknown')

            if change_type == 'slide_added':
                lines.append(f"  • *Slide {slide_num} added* — \"{slide_title}\"")
                if change.get('after'):
                    lines.append(f"    Content: {change['after']}")

            elif change_type == 'slide_removed':
                lines.append(f"  • *Slide {slide_num} removed* — \"{slide_title}\"")
                if change.get('before'):
                    lines.append(f"    Had: {change['before']}")

            elif change_type == 'text_modified':
                lines.append(f"  • *Text changed on Slide {slide_num}* — \"{slide_title}\"")
                if change.get('before'):
                    lines.append(f"    Before: {change['before']}")
                if change.get('after'):
                    lines.append(f"    After:  {change['after']}")

            else:
                lines.append(f"  • *{change_type}* on Slide {slide_num} — \"{slide_title}\"")

        lines.append("")
        lines.append(f"*Analysis:*\n{summary}")

        return "\n".join(lines)

    def _send_slack(self, text):
        try:
            response = requests.post(
                self.slack_webhook_url,
                json={"text": text},
                timeout=10
            )
            response.raise_for_status()
            logging.info("Slack notification sent successfully.")
        except Exception as e:
            logging.error(f"Failed to send Slack notification: {e}")

    def _send_email(self, subject, body):
        if not self.smtp_user or not self.smtp_pass:
            logging.warning("SMTP credentials missing. Skipping email notification.")
            return

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.smtp_user
        msg['To'] = self.notify_email

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            logging.info("Email notification sent successfully.")
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")


if __name__ == "__main__":
    # Test script usage
    # notifier = Notifier()
    # notifier.notify("The pricing has changed on slide 4.", {
    #     "presentation_id": "abc123",
    #     "presentation_title": "Test Deck",
    #     "changes": [...]
    # })
    pass
