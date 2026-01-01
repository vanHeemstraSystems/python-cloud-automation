"""
Configuration Management
Handles loading and validation of configuration files
"""

import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TagRequirement:
    """Tag requirement configuration"""
    name: str
    required: bool = True
    default_value: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    description: Optional[str] = None


@dataclass
class RemediationRule:
    """Auto-remediation rule configuration"""
    resource_type: str
    action: str  # 'add_tags', 'update_tags', 'notify_only'
    default_tags: Dict[str, str]
    enabled: bool = True


class Config:
    """Main configuration class"""
    
    def __init__(self, config_dir: str = 'config'):
        self.config_dir = config_dir
        self._required_tags: List[TagRequirement] = []
        self._remediation_rules: List[RemediationRule] = []
        self._settings: Dict = {}
        self.load_configuration()
    
    def load_configuration(self):
        """Load all configuration files"""
        self._load_required_tags()
        self._load_remediation_rules()
        self._load_settings()
    
    def _load_required_tags(self):
        """Load required tags configuration"""
        config_file = os.path.join(self.config_dir, 'required_tags.json')
        
        if not os.path.exists(config_file):
            logger.warning(f"Required tags config not found: {config_file}, using defaults")
            self._set_default_required_tags()
            return
        
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
            
            for tag_config in data.get('tags', []):
                self._required_tags.append(TagRequirement(
                    name=tag_config['name'],
                    required=tag_config.get('required', True),
                    default_value=tag_config.get('default_value'),
                    allowed_values=tag_config.get('allowed_values'),
                    description=tag_config.get('description')
                ))
            
            logger.info(f"Loaded {len(self._required_tags)} required tags")
            
        except Exception as e:
            logger.error(f"Failed to load required tags config: {str(e)}")
            self._set_default_required_tags()
    
    def _load_remediation_rules(self):
        """Load remediation rules configuration"""
        config_file = os.path.join(self.config_dir, 'remediation_rules.json')
        
        if not os.path.exists(config_file):
            logger.warning(f"Remediation rules config not found: {config_file}, using defaults")
            self._set_default_remediation_rules()
            return
        
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
            
            for rule_config in data.get('rules', []):
                self._remediation_rules.append(RemediationRule(
                    resource_type=rule_config['resource_type'],
                    action=rule_config.get('action', 'add_tags'),
                    default_tags=rule_config.get('default_tags', {}),
                    enabled=rule_config.get('enabled', True)
                ))
            
            logger.info(f"Loaded {len(self._remediation_rules)} remediation rules")
            
        except Exception as e:
            logger.error(f"Failed to load remediation rules config: {str(e)}")
            self._set_default_remediation_rules()
    
    def _load_settings(self):
        """Load general settings"""
        settings_file = os.path.join(self.config_dir, 'settings.json')
        
        if not os.path.exists(settings_file):
            logger.info("Settings file not found, using defaults")
            self._set_default_settings()
            return
        
        try:
            with open(settings_file, 'r') as f:
                self._settings = json.load(f)
            logger.info("Loaded settings configuration")
        except Exception as e:
            logger.error(f"Failed to load settings: {str(e)}")
            self._set_default_settings()
    
    def _set_default_required_tags(self):
        """Set default required tags"""
        self._required_tags = [
            TagRequirement(
                name='Environment',
                required=True,
                allowed_values=['Dev', 'Test', 'Staging', 'Production'],
                description='Deployment environment'
            ),
            TagRequirement(
                name='CostCenter',
                required=True,
                description='Cost center for billing'
            ),
            TagRequirement(
                name='Owner',
                required=True,
                description='Resource owner email or team name'
            ),
            TagRequirement(
                name='Project',
                required=True,
                description='Project or initiative name'
            ),
            TagRequirement(
                name='Criticality',
                required=True,
                allowed_values=['Low', 'Medium', 'High', 'Critical'],
                description='Business criticality level'
            )
        ]
    
    def _set_default_remediation_rules(self):
        """Set default remediation rules"""
        self._remediation_rules = [
            RemediationRule(
                resource_type='*',  # Applies to all resource types
                action='add_tags',
                default_tags={
                    'Environment': 'Unknown',
                    'ManagedBy': 'Automation'
                },
                enabled=True
            )
        ]
    
    def _set_default_settings(self):
        """Set default settings"""
        self._settings = {
            'scan_interval_hours': 24,
            'enable_auto_remediation': False,
            'compliance_threshold': 80,
            'notification_enabled': True,
            'max_resources_per_scan': 10000
        }
    
    @property
    def required_tags(self) -> List[TagRequirement]:
        """Get list of required tags"""
        return self._required_tags
    
    @property
    def required_tag_names(self) -> List[str]:
        """Get list of required tag names only"""
        return [tag.name for tag in self._required_tags if tag.required]
    
    @property
    def remediation_rules(self) -> List[RemediationRule]:
        """Get list of remediation rules"""
        return self._remediation_rules
    
    def get_setting(self, key: str, default=None):
        """Get a specific setting value"""
        return self._settings.get(key, default)
    
    def get_remediation_rule(self, resource_type: str) -> Optional[RemediationRule]:
        """
        Get remediation rule for a specific resource type
        
        Args:
            resource_type: Azure resource type
            
        Returns:
            RemediationRule if found, None otherwise
        """
        # First try exact match
        for rule in self._remediation_rules:
            if rule.resource_type == resource_type and rule.enabled:
                return rule
        
        # Then try wildcard match
        for rule in self._remediation_rules:
            if rule.resource_type == '*' and rule.enabled:
                return rule
        
        return None
    
    def validate_tag_value(self, tag_name: str, tag_value: str) -> bool:
        """
        Validate a tag value against configuration
        
        Args:
            tag_name: Name of the tag
            tag_value: Value to validate
            
        Returns:
            True if valid, False otherwise
        """
        tag_req = next((t for t in self._required_tags if t.name == tag_name), None)
        
        if tag_req is None:
            return True  # Tag not in requirements, allow any value
        
        if tag_req.allowed_values:
            return tag_value in tag_req.allowed_values
        
        return True  # No restrictions on values
    
    def export_config(self, output_dir: str):
        """Export current configuration to files"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Export required tags
        tags_config = {
            'tags': [
                {
                    'name': tag.name,
                    'required': tag.required,
                    'default_value': tag.default_value,
                    'allowed_values': tag.allowed_values,
                    'description': tag.description
                }
                for tag in self._required_tags
            ]
        }
        
        with open(os.path.join(output_dir, 'required_tags.json'), 'w') as f:
            json.dump(tags_config, f, indent=2)
        
        # Export remediation rules
        rules_config = {
            'rules': [
                {
                    'resource_type': rule.resource_type,
                    'action': rule.action,
                    'default_tags': rule.default_tags,
                    'enabled': rule.enabled
                }
                for rule in self._remediation_rules
            ]
        }
        
        with open(os.path.join(output_dir, 'remediation_rules.json'), 'w') as f:
            json.dump(rules_config, f, indent=2)
        
        # Export settings
        with open(os.path.join(output_dir, 'settings.json'), 'w') as f:
            json.dump(self._settings, f, indent=2)
        
        logger.info(f"Configuration exported to {output_dir}")


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config(config_dir: str = 'config') -> Config:
    """Get or create global configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_dir)
    return _config_instance
