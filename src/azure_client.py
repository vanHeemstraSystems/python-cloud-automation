"""
Azure Client Wrapper
Provides abstraction layer for Azure SDK operations
"""

from typing import List, Dict, Optional
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient
from azure.mgmt.costmanagement import CostManagementClient
from azure.core.exceptions import AzureError
import logging

logger = logging.getLogger(__name__)


class AzureClient:
    """Wrapper class for Azure SDK clients"""
    
    def __init__(
        self, 
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Azure client with authentication
        
        Args:
            tenant_id: Azure AD tenant ID (optional, uses DefaultAzureCredential if not provided)
            client_id: Service principal client ID (optional)
            client_secret: Service principal secret (optional)
        """
        if tenant_id and client_id and client_secret:
            self.credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            logger.info("Using ClientSecretCredential for authentication")
        else:
            self.credential = DefaultAzureCredential()
            logger.info("Using DefaultAzureCredential for authentication")
        
        self._subscription_client = None
        self._resource_clients: Dict[str, ResourceManagementClient] = {}
        self._cost_clients: Dict[str, CostManagementClient] = {}
    
    @property
    def subscription_client(self) -> SubscriptionClient:
        """Get or create subscription client"""
        if self._subscription_client is None:
            self._subscription_client = SubscriptionClient(self.credential)
        return self._subscription_client
    
    def get_resource_client(self, subscription_id: str) -> ResourceManagementClient:
        """
        Get resource management client for a specific subscription
        
        Args:
            subscription_id: Azure subscription ID
            
        Returns:
            ResourceManagementClient instance
        """
        if subscription_id not in self._resource_clients:
            self._resource_clients[subscription_id] = ResourceManagementClient(
                self.credential,
                subscription_id
            )
        return self._resource_clients[subscription_id]
    
    def get_cost_client(self, subscription_id: str) -> CostManagementClient:
        """
        Get cost management client for a specific subscription
        
        Args:
            subscription_id: Azure subscription ID
            
        Returns:
            CostManagementClient instance
        """
        if subscription_id not in self._cost_clients:
            self._cost_clients[subscription_id] = CostManagementClient(
                self.credential,
                subscription_id
            )
        return self._cost_clients[subscription_id]
    
    def list_subscriptions(self) -> List[Dict[str, str]]:
        """
        List all accessible Azure subscriptions
        
        Returns:
            List of subscription dictionaries with id and name
        """
        try:
            subscriptions = []
            for sub in self.subscription_client.subscriptions.list():
                subscriptions.append({
                    'id': sub.subscription_id,
                    'name': sub.display_name,
                    'state': sub.state
                })
            return subscriptions
        except AzureError as e:
            logger.error(f"Failed to list subscriptions: {str(e)}")
            raise
    
    def list_resource_groups(self, subscription_id: str) -> List[Dict[str, str]]:
        """
        List all resource groups in a subscription
        
        Args:
            subscription_id: Azure subscription ID
            
        Returns:
            List of resource group dictionaries
        """
        try:
            client = self.get_resource_client(subscription_id)
            resource_groups = []
            for rg in client.resource_groups.list():
                resource_groups.append({
                    'name': rg.name,
                    'location': rg.location,
                    'tags': rg.tags or {}
                })
            return resource_groups
        except AzureError as e:
            logger.error(f"Failed to list resource groups: {str(e)}")
            raise
    
    def list_resources(
        self, 
        subscription_id: str,
        resource_group: Optional[str] = None,
        resource_type: Optional[str] = None
    ) -> List[Dict]:
        """
        List resources with optional filtering
        
        Args:
            subscription_id: Azure subscription ID
            resource_group: Optional resource group name filter
            resource_type: Optional resource type filter
            
        Returns:
            List of resource dictionaries
        """
        try:
            client = self.get_resource_client(subscription_id)
            
            # Build filter string
            filters = []
            if resource_group:
                filters.append(f"resourceGroup eq '{resource_group}'")
            if resource_type:
                filters.append(f"resourceType eq '{resource_type}'")
            
            filter_string = " and ".join(filters) if filters else None
            
            resources = []
            for resource in client.resources.list(filter=filter_string):
                resources.append({
                    'id': resource.id,
                    'name': resource.name,
                    'type': resource.type,
                    'location': resource.location,
                    'tags': resource.tags or {},
                    'resource_group': resource.id.split('/')[4] if len(resource.id.split('/')) > 4 else None
                })
            
            return resources
        except AzureError as e:
            logger.error(f"Failed to list resources: {str(e)}")
            raise
    
    def get_resource(self, resource_id: str, api_version: str = '2021-04-01') -> Dict:
        """
        Get a specific resource by ID
        
        Args:
            resource_id: Full Azure resource ID
            api_version: API version to use
            
        Returns:
            Resource dictionary
        """
        try:
            parts = resource_id.split('/')
            subscription_id = parts[2]
            client = self.get_resource_client(subscription_id)
            
            resource = client.resources.get_by_id(resource_id, api_version)
            return {
                'id': resource.id,
                'name': resource.name,
                'type': resource.type,
                'location': resource.location,
                'tags': resource.tags or {},
                'properties': resource.properties
            }
        except AzureError as e:
            logger.error(f"Failed to get resource {resource_id}: {str(e)}")
            raise
    
    def update_resource_tags(
        self, 
        resource_id: str, 
        tags: Dict[str, str],
        merge: bool = True,
        api_version: str = '2021-04-01'
    ) -> bool:
        """
        Update tags for a resource
        
        Args:
            resource_id: Full Azure resource ID
            tags: Dictionary of tags to apply
            merge: If True, merge with existing tags; if False, replace all tags
            api_version: API version to use
            
        Returns:
            True if successful, False otherwise
        """
        try:
            parts = resource_id.split('/')
            subscription_id = parts[2]
            client = self.get_resource_client(subscription_id)
            
            if merge:
                # Get existing tags and merge
                existing_resource = client.resources.get_by_id(resource_id, api_version)
                updated_tags = {**(existing_resource.tags or {}), **tags}
            else:
                updated_tags = tags
            
            # Update resource
            client.resources.update_by_id(
                resource_id,
                api_version=api_version,
                parameters={'tags': updated_tags}
            )
            
            logger.info(f"Successfully updated tags for {resource_id}")
            return True
            
        except AzureError as e:
            logger.error(f"Failed to update tags for {resource_id}: {str(e)}")
            return False
    
    def get_resource_cost(
        self,
        subscription_id: str,
        resource_id: Optional[str] = None,
        time_period: str = 'current_month'
    ) -> float:
        """
        Get cost information for a resource or subscription
        
        Args:
            subscription_id: Azure subscription ID
            resource_id: Optional resource ID (if None, returns subscription cost)
            time_period: Time period for cost query
            
        Returns:
            Estimated cost in subscription currency
        """
        # Note: This is a simplified version
        # Full implementation would use Cost Management API
        logger.warning("Cost estimation not yet implemented - returning 0.0")
        return 0.0
