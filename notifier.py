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

    def _get_labels(self):
        lang = os.getenv('ALERT_LANGUAGE', 'en').lower()
        labels = {
            'en': {
                'header': 'Presentation Change Detected',
                'subject': 'Change detected in',
                'title': 'Title',
                'url': 'URL',
                'editor': 'Last editor',
                'detected': 'Detected at',
                'changes': 'Changes',
                'text_mod': 'Text changed on Slide {num}',
                'added': 'Slide {num} added',
                'removed': 'Slide {num} removed',
                'before': 'Before',
                'after': 'After',
                'content': 'Content',
                'analysis': 'Analysis'
            },
            'es': {
                'header': 'Cambio detectado en presentación',
                'subject': 'Cambio detectado en',
                'title': 'Título',
                'url': 'URL',
                'editor': 'Último editor',
                'detected': 'Detectado en',
                'changes': 'Cambios',
                'text_mod': 'Texto modificado en Slide {num}',
                'added': 'Slide {num} agregado',
                'removed': 'Slide {num} eliminado',
                'before': 'Antes',
                'after': 'Después',
                'content': 'Contenido',
                'analysis': 'Análisis'
            }
        }
        return labels.get(lang, labels['en'])

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
        l = self._get_labels()

        # Slack notification
        if self.slack_webhook_url:
            self._send_slack(message)

        # Email notification
        if self.notify_email:
            title = diff_data.get('presentation_title', 'Unknown Presentation')
            self._send_email(f"{l['subject']} {title}", message)

    def _format_alert(self, summary, diff_data):
        """Build a rich, human-readable alert from the full diff context."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        title = diff_data.get('presentation_title', 'Unknown Presentation')
        pres_id = diff_data.get('presentation_id', '')
        pres_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        changes = diff_data.get('changes', [])
        
        l = self._get_labels()

        lines = [
            f"*📊 {l['header']}*",
            f"*{l['title']}:* {title}",
            f"*{l['url']}:* {pres_url}",
        ]

        last_editor = diff_data.get('last_editor')
        if last_editor:
            lines.append(f"*{l['editor']}:* {last_editor['name']} ({last_editor['email']}) · {timestamp}")
        else:
            lines.append(f"*{l['detected']}:* {timestamp}")

        lines.extend([
            "",
            f"*{l['changes']}:*",
        ])

        for change in changes:
            slide_num = change.get('slide_index', 0) + 1
            slide_title = change.get('slide_title', 'Untitled')
            change_type = change.get('change_type', 'unknown')

            if change_type == 'slide_added':
                lines.append(f"  • *{l['added'].format(num=slide_num)}* — \"{slide_title}\"")
                if change.get('after'):
                    lines.append(f"    {l['content']}: {change['after']}")

            elif change_type == 'slide_removed':
                lines.append(f"  • *{l['removed'].format(num=slide_num)}* — \"{slide_title}\"")
                if change.get('before'):
                    lines.append(f"    {l['before']}: {change['before']}")

            elif change_type == 'text_modified':
                lines.append(f"  • *{l['text_mod'].format(num=slide_num)}* — \"{slide_title}\"")
                if change.get('before'):
                    lines.append(f"    {l['before']}: {change['before']}")
                if change.get('after'):
                    lines.append(f"    {l['after']}:  {change['after']}")

            else:
                lines.append(f"  • *{change_type}* on Slide {slide_num} — \"{slide_title}\"")

        lines.append("")
        lines.append(f"*{l['analysis']}:*\n{summary}")

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
