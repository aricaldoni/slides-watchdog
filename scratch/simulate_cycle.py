import os
import json
import logging
from mock_services import build_mock_services
from drive_monitor import DriveMonitor
from slide_diff import SlideDiffer
from analyzer import PresentationAnalyzer
from notifier import Notifier

# Disable logging for cleaner output
logging.disable(logging.CRITICAL)

def simulate():
    drive_service, slides_service = build_mock_services()
    
    monitor = DriveMonitor(drive_service, 'sim_pres_id')
    differ = SlideDiffer(slides_service)
    analyzer = PresentationAnalyzer() 
    notifier = Notifier()
    
    # 1. Initialize Baseline
    monitor.has_changed() 
    differ.get_diff('sim_pres_id') 
    
    # 2. Generate Simulated Change Data
    diff_data = {
        'presentation_id': 'sim_pres_id',
        'presentation_title': '2026 Strategic Roadmap',
        'changes': [
            {
                'slide_object_id': 's4',
                'slide_index': 3,
                'slide_title': 'Q4 Pricing',
                'change_type': 'text_modified',
                'before': 'Enterprise: $10,000/year',
                'after': 'Enterprise: $8,500/year (Promotional)'
            },
            {
                'slide_object_id': 's12',
                'slide_index': 11,
                'slide_title': 'Competitor Analysis',
                'change_type': 'slide_added',
                'before': None,
                'after': 'Analysis of new market entry by TechCorp.'
            }
        ]
    }
    
    # Add attribution from the mock
    diff_data['last_editor'] = monitor.get_last_editor_info()
    
    # Analyze
    summary = analyzer.analyze_changes(diff_data)
    
    # 3. Format Alert
    alert_text = notifier._format_alert(summary, diff_data)
    
    # 4. Report
    l = notifier._get_labels()
    print('\n' + '='*40)
    print('SIMULATED SLACK PAYLOAD (JSON)')
    print('='*40)
    print(json.dumps({'text': alert_text}, indent=2))
    
    print('\n' + '='*40)
    print('SIMULATED EMAIL PAYLOAD')
    print('='*40)
    print(f"Subject: {l['subject']} {diff_data['presentation_title']}")
    print("-" * 40)
    print(f"Body:\n{alert_text}")

if __name__ == '__main__':
    simulate()
