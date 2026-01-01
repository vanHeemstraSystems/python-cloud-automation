"""
Notification Module
Sends compliance notifications to Slack and Microsoft Teams
"""

import os
import json
import argparse
from typing import Dict, Optional
from datetime import datetime
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import pymsteams


class NotificationService:
    """Handles sending notifications to various platforms"""
    
    def __init__(self):
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.teams_webhook = os.getenv('TEAMS_WEBHOOK_URL')
        self.slack_token = os.getenv('SLACK_BOT_TOKEN')
    
    def send_slack_webhook(self, message: Dict):
        """
        Send notification via Slack webhook
        
        Args:
            message: Message payload for Slack
        """
        if not self.slack_webhook:
            print("Slack webhook URL not configured")
            return False
        
        try:
            response = requests.post(
                self.slack_webhook,
                json=message,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            print("Slack notification sent successfully")
            return True
        except Exception as e:
            print(f"Failed to send Slack notification: {str(e)}")
            return False
    
    def send_teams_webhook(self, message: Dict):
        """
        Send notification via Microsoft Teams webhook
        
        Args:
            message: Message payload for Teams
        """
        if not self.teams_webhook:
            print("Teams webhook URL not configured")
            return False
        
        try:
            teams_message = pymsteams.connectorcard(self.teams_webhook)
            teams_message.title(message.get('title', 'Azure Tag Compliance Update'))
            teams_message.text(message.get('text', ''))
            
            # Add facts/fields
            if 'fields' in message:
                for field in message['fields']:
                    teams_message.addFact(field['name'], field['value'])
            
            teams_message.send()
            print("Teams notification sent successfully")
            return True
        except Exception as e:
            print(f"Failed to send Teams notification: {str(e)}")
            return False
    
    def format_compliance_message(
        self,
        compliance_rate: float,
        total_resources: int,
        compliant: int,
        non_compliant: int,
        report_url: Optional[str] = None
    ) -> Dict:
        """
        Format compliance data into notification message
        
        Args:
            compliance_rate: Overall compliance percentage
            total_resources: Total number of resources scanned
            compliant: Number of compliant resources
            non_compliant: Number of non-compliant resources
            report_url: Optional URL to full report
            
        Returns:
            Formatted message dictionary
        """
        # Determine status emoji and color
        if compliance_rate >= 90:
            status_emoji = "✅"
            color = "good"
        elif compliance_rate >= 75:
            status_emoji = "⚠️"
            color = "warning"
        else:
            status_emoji = "❌"
            color = "danger"
        
        message = {
            'title': f'{status_emoji} Azure Tag Compliance Report',
            'text': f'Compliance Check completed at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            'color': color,
            'fields': [
                {
                    'name': 'Overall Compliance Rate',
                    'value': f'{compliance_rate}%'
                },
                {
                    'name': 'Total Resources',
                    'value': str(total_resources)
                },
                {
                    'name': 'Compliant',
                    'value': str(compliant)
                },
                {
                    'name': 'Non-Compliant',
                    'value': str(non_compliant)
                }
            ]
        }
        
        if report_url:
            message['fields'].append({
                'name': 'Full Report',
                'value': report_url
            })
        
        return message
    
    def send_compliance_notification(
        self,
        platform: str,
        compliance_rate: float,
        total_resources: int = 0,
        compliant: int = 0,
        non_compliant: int = 0,
        report_url: Optional[str] = None
    ):
        """
        Send compliance notification to specified platform
        
        Args:
            platform: 'slack' or 'teams'
            compliance_rate: Overall compliance percentage
            total_resources: Total number of resources scanned
            compliant: Number of compliant resources
            non_compliant: Number of non-compliant resources
            report_url: Optional URL to full report
        """
        message = self.format_compliance_message(
            compliance_rate,
            total_resources,
            compliant,
            non_compliant,
            report_url
        )
        
        if platform.lower() == 'slack':
            # Convert to Slack format
            slack_message = {
                'text': message['title'],
                'attachments': [{
                    'color': message['color'],
                    'fields': [
                        {
                            'title': field['name'],
                            'value': field['value'],
                            'short': True
                        }
                        for field in message['fields']
                    ],
                    'footer': 'Azure Tag Compliance Automation',
                    'ts': int(datetime.now().timestamp())
                }]
            }
            return self.send_slack_webhook(slack_message)
        
        elif platform.lower() == 'teams':
            return self.send_teams_webhook(message)
        
        else:
            print(f"Unknown platform: {platform}")
            return False


def load_latest_report() -> Dict:
    """Load the most recent compliance report"""
    import glob
    
    reports = glob.glob('results/reports/compliance_report_*.json')
    if not reports:
        raise FileNotFoundError("No compliance reports found")
    
    latest_report = max(reports, key=os.path.getctime)
    
    with open(latest_report, 'r') as f:
        return json.load(f)


def main():
    """Main entry point for notification service"""
    parser = argparse.ArgumentParser(description='Send compliance notifications')
    parser.add_argument(
        '--platform',
        choices=['slack', 'teams', 'both'],
        default='both',
        help='Notification platform'
    )
    parser.add_argument(
        '--compliance-rate',
        type=float,
        help='Compliance rate (if not loading from report)'
    )
    parser.add_argument(
        '--report-url',
        help='URL to full compliance report'
    )
    
    args = parser.parse_args()
    
    service = NotificationService()
    
    # Load data from report if not provided via args
    if args.compliance_rate is None:
        try:
            report = load_latest_report()
            compliance_rate = report['summary']['overall_compliance_rate']
            total_resources = report['summary']['total_resources']
            compliant = report['summary']['compliant']
            non_compliant = report['summary']['non_compliant']
        except Exception as e:
            print(f"Failed to load report: {str(e)}")
            return
    else:
        compliance_rate = args.compliance_rate
        total_resources = 0
        compliant = 0
        non_compliant = 0
    
    # Send notifications
    if args.platform in ['slack', 'both']:
        service.send_compliance_notification(
            'slack',
            compliance_rate,
            total_resources,
            compliant,
            non_compliant,
            args.report_url
        )
    
    if args.platform in ['teams', 'both']:
        service.send_compliance_notification(
            'teams',
            compliance_rate,
            total_resources,
            compliant,
            non_compliant,
            args.report_url
        )


if __name__ == '__main__':
    main()
