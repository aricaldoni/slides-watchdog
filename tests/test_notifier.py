import pytest
from unittest.mock import MagicMock, patch
from notifier import Notifier

@pytest.fixture
def sample_diff_data():
    return {
        "presentation_id": "pres123",
        "presentation_title": "Test Deck",
        "last_editor": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "time": "2026-04-21T18:00:00Z"
        },
        "changes": [
            {
                "slide_index": 3,
                "slide_title": "Pricing",
                "change_type": "text_modified",
                "before": "$500",
                "after": "$420"
            }
        ]
    }

def test_alert_formatting_includes_attribution(sample_diff_data):
    notifier = Notifier()
    alert = notifier._format_alert("This is a summary", sample_diff_data)
    
    assert "Test Deck" in alert
    assert "Jane Doe" in alert
    assert "jane@example.com" in alert
    assert "Slide 4" in alert
    assert "Pricing" in alert
    assert "$500" in alert
    assert "$420" in alert
    assert "This is a summary" in alert

@patch("requests.post")
def test_slack_payload_format(mock_post, sample_diff_data):
    notifier = Notifier()
    notifier.slack_webhook_url = "https://hooks.slack.com/test"
    
    notifier.notify("Summary", sample_diff_data)
    
    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert kwargs['json']['text'].startswith("*📊 Presentation Change Detected*")
    assert "Jane Doe" in kwargs['json']['text']

@patch("smtplib.SMTP")
def test_email_format(mock_smtp, sample_diff_data):
    # Setup mock SMTP
    instance = mock_smtp.return_value.__enter__.return_value
    
    notifier = Notifier()
    notifier.notify_email = "boss@example.com"
    notifier.smtp_user = "bot@example.com"
    notifier.smtp_pass = "password"
    
    notifier.notify("Summary", sample_diff_data)
    
    assert instance.send_message.called
    msg = instance.send_message.call_args[0][0]
    assert msg['Subject'] == "Change detected in Test Deck"
    assert msg['From'] == "bot@example.com"
    assert msg['To'] == "boss@example.com"
    
    # MIMEText might encode payload as base64 if it contains non-ascii characters (like emojis)
    payload = msg.get_payload(decode=True).decode('utf-8')
    assert "Jane Doe" in payload
