"""
Unit tests for reporter modules
"""

import pytest
import os
import json
import tempfile
from unittest.mock import Mock, patch, mock_open
from src.reporters.html_reporter import HTMLReporter
from src.reporters.csv_reporter import CSVReporter
from src.reporters.notification import NotificationService


@pytest.fixture
def sample_report():
    """Sample compliance report"""
    return {
        'scan_timestamp': '2024-01-01T00:00:00',
        'summary': {
            'total_resources': 100,
            'compliant': 75,
            'non_compliant': 25,
            'remediated': 0,
            'overall_compliance_rate': 75.0
        },
        'tag_statistics': {
            'Environment': {
                'missing_count': 10,
                'compliance_rate': 90.0
            },
            'CostCenter': {
                'missing_count': 20,
                'compliance_rate': 80.0
            },
            'Owner': {
                'missing_count': 5,
                'compliance_rate': 95.0
            }
        },
        'resource_type_breakdown': {
            ('Microsoft.Compute/virtualMachines', 'compliant'): 30,
            ('Microsoft.Compute/virtualMachines', 'non_compliant'): 10,
            ('Microsoft.Storage/storageAccounts', 'compliant'): 25,
            ('Microsoft.Storage/storageAccounts', 'non_compliant'): 5
        },
        'top_violators': {
            'resource-group-1': 10,
            'resource-group-2': 8,
            'resource-group-3': 7
        }
    }


@pytest.fixture
def temp_report_file(sample_report):
    """Create temporary report file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_report, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestHTMLReporter:
    """Test suite for HTMLReporter"""
    
    def test_initialization(self, temp_report_file):
        """Test HTML reporter initialization"""
        reporter = HTMLReporter(temp_report_file)
        assert reporter.report is not None
        assert reporter.report['summary']['total_resources'] == 100
    
    def test_generate_tag_chart(self, temp_report_file):
        """Test tag compliance chart generation"""
        reporter = HTMLReporter(temp_report_file)
        chart_code = reporter._generate_tag_chart()
        
        assert 'tagComplianceBar' in chart_code
        assert 'Environment' in chart_code
        assert 'CostCenter' in chart_code
    
    def test_generate_violators_chart(self, temp_report_file):
        """Test violators chart generation"""
        reporter = HTMLReporter(temp_report_file)
        chart_code = reporter._generate_violators_chart()
        
        assert 'violatorsBar' in chart_code
        assert 'resource-group-1' in chart_code
    
    def test_generate_dashboard(self, temp_report_file):
        """Test dashboard generation"""
        reporter = HTMLReporter(temp_report_file)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            output_path = f.name
        
        try:
            reporter.generate_dashboard(output_path)
            assert os.path.exists(output_path)
            
            # Check HTML content
            with open(output_path, 'r') as f:
                content = f.read()
                assert 'Azure Tag Compliance Dashboard' in content
                assert '75.0%' in content  # Compliance rate
                assert '100' in content  # Total resources
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestCSVReporter:
    """Test suite for CSVReporter"""
    
    def test_initialization(self, temp_report_file):
        """Test CSV reporter initialization"""
        reporter = CSVReporter(temp_report_file)
        assert reporter.report is not None
    
    def test_export_summary(self, temp_report_file):
        """Test summary CSV export"""
        reporter = CSVReporter(temp_report_file)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        try:
            reporter.export_summary(output_path)
            assert os.path.exists(output_path)
            
            # Verify CSV content
            import pandas as pd
            df = pd.read_csv(output_path)
            assert len(df) > 0
            assert 'Metric' in df.columns
            assert 'Value' in df.columns
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_export_top_violators(self, temp_report_file):
        """Test top violators CSV export"""
        reporter = CSVReporter(temp_report_file)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        try:
            reporter.export_top_violators(output_path, top_n=5)
            assert os.path.exists(output_path)
            
            import pandas as pd
            df = pd.read_csv(output_path)
            assert len(df) <= 5
            assert 'Resource Group' in df.columns
            assert 'Non-Compliant Resources' in df.columns
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def test_export_tag_analysis(self, temp_report_file):
        """Test tag analysis CSV export"""
        reporter = CSVReporter(temp_report_file)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name
        
        try:
            reporter.export_tag_analysis(output_path)
            assert os.path.exists(output_path)
            
            import pandas as pd
            df = pd.read_csv(output_path)
            assert 'Tag Name' in df.columns
            assert 'Compliance Rate (%)' in df.columns
            assert len(df) == 3  # Three tags in sample data
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestNotificationService:
    """Test suite for NotificationService"""
    
    @patch.dict(os.environ, {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test'})
    def test_initialization_with_slack(self):
        """Test notification service initialization with Slack"""
        service = NotificationService()
        assert service.slack_webhook == 'https://hooks.slack.com/test'
    
    def test_format_compliance_message_good(self):
        """Test message formatting for good compliance"""
        service = NotificationService()
        message = service.format_compliance_message(
            compliance_rate=95.0,
            total_resources=100,
            compliant=95,
            non_compliant=5
        )
        
        assert '✅' in message['title']
        assert message['color'] == 'good'
        assert any(f['name'] == 'Overall Compliance Rate' for f in message['fields'])
    
    def test_format_compliance_message_warning(self):
        """Test message formatting for warning compliance"""
        service = NotificationService()
        message = service.format_compliance_message(
            compliance_rate=80.0,
            total_resources=100,
            compliant=80,
            non_compliant=20
        )
        
        assert '⚠️' in message['title']
        assert message['color'] == 'warning'
    
    def test_format_compliance_message_danger(self):
        """Test message formatting for low compliance"""
        service = NotificationService()
        message = service.format_compliance_message(
            compliance_rate=50.0,
            total_resources=100,
            compliant=50,
            non_compliant=50
        )
        
        assert '❌' in message['title']
        assert message['color'] == 'danger'
    
    @patch('src.reporters.notification.requests.post')
    @patch.dict(os.environ, {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test'})
    def test_send_slack_webhook_success(self, mock_post):
        """Test successful Slack webhook send"""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        service = NotificationService()
        message = {'text': 'Test message'}
        result = service.send_slack_webhook(message)
        
        assert result is True
        mock_post.assert_called_once()
    
    @patch('src.reporters.notification.requests.post')
    @patch.dict(os.environ, {'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test'})
    def test_send_slack_webhook_failure(self, mock_post):
        """Test failed Slack webhook send"""
        mock_post.side_effect = Exception("Network error")
        
        service = NotificationService()
        message = {'text': 'Test message'}
        result = service.send_slack_webhook(message)
        
        assert result is False
    
    def test_send_slack_webhook_no_config(self):
        """Test Slack webhook without configuration"""
        service = NotificationService()
        service.slack_webhook = None
        
        message = {'text': 'Test message'}
        result = service.send_slack_webhook(message)
        
        assert result is False
    
    @patch('src.reporters.notification.pymsteams.connectorcard')
    @patch.dict(os.environ, {'TEAMS_WEBHOOK_URL': 'https://outlook.office.com/webhook/test'})
    def test_send_teams_webhook(self, mock_connector):
        """Test Teams webhook send"""
        mock_card = Mock()
        mock_connector.return_value = mock_card
        
        service = NotificationService()
        message = {
            'title': 'Test',
            'text': 'Test message',
            'fields': [
                {'name': 'Field 1', 'value': 'Value 1'}
            ]
        }
        
        result = service.send_teams_webhook(message)
        
        assert result is True
        mock_card.title.assert_called_once()
        mock_card.send.assert_called_once()


@pytest.mark.integration
class TestReporterIntegration:
    """Integration tests for reporters"""
    
    def test_full_reporting_workflow(self, temp_report_file):
        """Test complete reporting workflow"""
        # Create temp output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # HTML Report
            html_reporter = HTMLReporter(temp_report_file)
            html_path = os.path.join(temp_dir, 'dashboard.html')
            html_reporter.generate_dashboard(html_path)
            assert os.path.exists(html_path)
            
            # CSV Reports
            csv_reporter = CSVReporter(temp_report_file)
            csv_reporter.export_all(temp_dir)
            
            # Check multiple CSV files were created
            csv_files = [f for f in os.listdir(temp_dir) if f.endswith('.csv')]
            assert len(csv_files) > 0
