"""
Unit tests for tag compliance checker
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from src.tag_compliance import AzureTagComplianceChecker, ComplianceResult


@pytest.fixture
def mock_credential():
    """Mock Azure credential"""
    with patch('src.tag_compliance.DefaultAzureCredential') as mock:
        yield mock.return_value


@pytest.fixture
def compliance_checker():
    """Create compliance checker instance"""
    required_tags = ['Environment', 'CostCenter', 'Owner']
    with patch('src.tag_compliance.DefaultAzureCredential'):
        return AzureTagComplianceChecker(required_tags)


@pytest.fixture
def sample_resource():
    """Sample Azure resource"""
    return {
        'id': '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm',
        'name': 'test-vm',
        'type': 'Microsoft.Compute/virtualMachines',
        'tags': {
            'Environment': 'Production',
            'Owner': 'team@example.com'
        }
    }


class TestAzureTagComplianceChecker:
    """Test suite for AzureTagComplianceChecker"""
    
    def test_initialization(self, compliance_checker):
        """Test checker initialization"""
        assert compliance_checker is not None
        assert len(compliance_checker.required_tags) == 3
        assert compliance_checker.results == []
    
    def test_check_resource_compliance_compliant(self, compliance_checker):
        """Test compliance check for compliant resource"""
        resource = {
            'id': '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm',
            'name': 'test-vm',
            'type': 'Microsoft.Compute/virtualMachines',
            'tags': {
                'Environment': 'Production',
                'CostCenter': 'IT-001',
                'Owner': 'team@example.com'
            }
        }
        
        result = compliance_checker.check_resource_compliance(resource, 'test-sub')
        
        assert result.compliance_status == 'compliant'
        assert len(result.missing_tags) == 0
        assert result.resource_name == 'test-vm'
    
    def test_check_resource_compliance_non_compliant(self, compliance_checker, sample_resource):
        """Test compliance check for non-compliant resource"""
        result = compliance_checker.check_resource_compliance(sample_resource, 'test-sub')
        
        assert result.compliance_status == 'non_compliant'
        assert 'CostCenter' in result.missing_tags
        assert len(result.missing_tags) == 1
    
    def test_check_resource_compliance_no_tags(self, compliance_checker):
        """Test compliance check for resource with no tags"""
        resource = {
            'id': '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm',
            'name': 'test-vm',
            'type': 'Microsoft.Compute/virtualMachines',
            'tags': None
        }
        
        result = compliance_checker.check_resource_compliance(resource, 'test-sub')
        
        assert result.compliance_status == 'non_compliant'
        assert len(result.missing_tags) == 3
        assert set(result.missing_tags) == {'Environment', 'CostCenter', 'Owner'}
    
    @patch('src.tag_compliance.SubscriptionClient')
    def test_get_all_subscriptions(self, mock_sub_client, compliance_checker):
        """Test subscription retrieval"""
        # Mock subscription list
        mock_subscription = Mock()
        mock_subscription.subscription_id = 'test-sub-1'
        
        mock_sub_client.return_value.subscriptions.list.return_value = [mock_subscription]
        
        subscriptions = compliance_checker.get_all_subscriptions()
        
        assert len(subscriptions) == 1
        assert subscriptions[0] == 'test-sub-1'
    
    @patch('src.tag_compliance.ResourceManagementClient')
    def test_scan_subscription(self, mock_resource_client, compliance_checker):
        """Test subscription scanning"""
        # Mock resource list
        mock_resource = Mock()
        mock_resource.as_dict.return_value = {
            'id': '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm',
            'name': 'test-vm',
            'type': 'Microsoft.Compute/virtualMachines',
            'tags': {'Environment': 'Dev'}
        }
        
        mock_resource_client.return_value.resources.list.return_value = [mock_resource]
        
        results = compliance_checker.scan_subscription('test-sub')
        
        assert len(results) == 1
        assert results[0].resource_name == 'test-vm'
        assert results[0].compliance_status == 'non_compliant'
    
    def test_generate_compliance_report_empty(self, compliance_checker):
        """Test report generation with no results"""
        report = compliance_checker.generate_compliance_report()
        
        assert report['summary']['total_resources'] == 0
        assert report['summary']['overall_compliance_rate'] == 0.0
    
    def test_generate_compliance_report_with_results(self, compliance_checker):
        """Test report generation with results"""
        # Add mock results
        compliance_checker.results = [
            ComplianceResult(
                resource_id='id1',
                resource_name='vm1',
                resource_type='Microsoft.Compute/virtualMachines',
                resource_group='rg1',
                subscription_id='sub1',
                current_tags={'Environment': 'Dev'},
                missing_tags=['CostCenter', 'Owner'],
                compliance_status='non_compliant',
                timestamp=datetime.utcnow().isoformat()
            ),
            ComplianceResult(
                resource_id='id2',
                resource_name='vm2',
                resource_type='Microsoft.Compute/virtualMachines',
                resource_group='rg1',
                subscription_id='sub1',
                current_tags={'Environment': 'Prod', 'CostCenter': 'IT', 'Owner': 'team'},
                missing_tags=[],
                compliance_status='compliant',
                timestamp=datetime.utcnow().isoformat()
            )
        ]
        
        report = compliance_checker.generate_compliance_report()
        
        assert report['summary']['total_resources'] == 2
        assert report['summary']['compliant'] == 1
        assert report['summary']['non_compliant'] == 1
        assert report['summary']['overall_compliance_rate'] == 50.0
        
        # Check tag statistics
        assert 'CostCenter' in report['tag_statistics']
        assert report['tag_statistics']['CostCenter']['missing_count'] == 1
    
    @patch('src.tag_compliance.ResourceManagementClient')
    def test_auto_remediate_success(self, mock_resource_client, compliance_checker):
        """Test successful auto-remediation"""
        # Mock existing resource
        mock_resource = Mock()
        mock_resource.tags = {'Environment': 'Dev'}
        
        mock_resource_client.return_value.resources.get_by_id.return_value = mock_resource
        mock_resource_client.return_value.resources.update_by_id.return_value = None
        
        resource_id = '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm'
        default_tags = {'CostCenter': 'Unknown', 'Owner': 'Unassigned'}
        
        result = compliance_checker.auto_remediate(resource_id, default_tags)
        
        assert result is True
    
    @patch('src.tag_compliance.ResourceManagementClient')
    def test_auto_remediate_failure(self, mock_resource_client, compliance_checker):
        """Test failed auto-remediation"""
        mock_resource_client.return_value.resources.get_by_id.side_effect = Exception("API Error")
        
        resource_id = '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm'
        default_tags = {'CostCenter': 'Unknown'}
        
        result = compliance_checker.auto_remediate(resource_id, default_tags)
        
        assert result is False


class TestComplianceResult:
    """Test suite for ComplianceResult dataclass"""
    
    def test_compliance_result_creation(self):
        """Test ComplianceResult creation"""
        result = ComplianceResult(
            resource_id='test-id',
            resource_name='test-name',
            resource_type='test-type',
            resource_group='test-rg',
            subscription_id='test-sub',
            current_tags={'key': 'value'},
            missing_tags=['tag1', 'tag2'],
            compliance_status='non_compliant',
            timestamp='2024-01-01T00:00:00'
        )
        
        assert result.resource_name == 'test-name'
        assert len(result.missing_tags) == 2
        assert result.compliance_status == 'non_compliant'
        assert result.estimated_monthly_cost == 0.0


@pytest.mark.integration
class TestIntegration:
    """Integration tests (require Azure credentials)"""
    
    @pytest.mark.skip(reason="Requires Azure credentials")
    def test_full_scan_workflow(self):
        """Test complete scan workflow"""
        # This would test against actual Azure resources
        # Skip in CI/CD unless credentials are available
        pass
