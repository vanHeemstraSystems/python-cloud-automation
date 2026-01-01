"""
Azure Resource Tagging Compliance Automation
Author: Willem van Heemstra
Purpose: Automate tag compliance checking and remediation
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient
import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

@dataclass
class ComplianceResult:
    """Data class for compliance check results"""
    resource_id: str
    resource_name: str
    resource_type: str
    resource_group: str
    subscription_id: str
    current_tags: Dict[str, str]
    missing_tags: List[str]
    compliance_status: str  # 'compliant', 'non_compliant', 'remediated'
    timestamp: str
    estimated_monthly_cost: float = 0.0

class AzureTagComplianceChecker:
    """Main class for Azure tag compliance operations"""
    
    def __init__(self, required_tags: List[str]):
        self.credential = DefaultAzureCredential()
        self.required_tags = required_tags
        self.results: List[ComplianceResult] = []
        
    def get_all_subscriptions(self) -> List[str]:
        """Retrieve all accessible Azure subscriptions"""
        console.print("[cyan]Retrieving Azure subscriptions...[/cyan]")
        sub_client = SubscriptionClient(self.credential)
        subscriptions = [sub.subscription_id for sub in sub_client.subscriptions.list()]
        console.print(f"[green]Found {len(subscriptions)} subscription(s)[/green]")
        return subscriptions
    
    def check_resource_compliance(
        self, 
        resource: dict, 
        subscription_id: str
    ) -> ComplianceResult:
        """Check if a single resource meets tagging requirements"""
        current_tags = resource.get('tags', {}) or {}
        missing_tags = [
            tag for tag in self.required_tags 
            if tag not in current_tags
        ]
        
        compliance_status = 'compliant' if not missing_tags else 'non_compliant'
        
        return ComplianceResult(
            resource_id=resource['id'],
            resource_name=resource['name'],
            resource_type=resource['type'],
            resource_group=resource['id'].split('/')[4] if len(resource['id'].split('/')) > 4 else 'unknown',
            subscription_id=subscription_id,
            current_tags=current_tags,
            missing_tags=missing_tags,
            compliance_status=compliance_status,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def scan_subscription(self, subscription_id: str) -> List[ComplianceResult]:
        """Scan all resources in a subscription for compliance"""
        resource_client = ResourceManagementClient(
            self.credential, 
            subscription_id
        )
        
        subscription_results = []
        resource_count = 0
        
        console.print(f"[yellow]Scanning subscription: {subscription_id}[/yellow]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Scanning resources...", total=None)
            
            try:
                for resource in resource_client.resources.list():
                    resource_count += 1
                    result = self.check_resource_compliance(
                        resource.as_dict(), 
                        subscription_id
                    )
                    subscription_results.append(result)
                    
                    if resource_count % 100 == 0:
                        progress.update(task, description=f"Scanned {resource_count} resources...")
            
            except Exception as e:
                console.print(f"[red]Error scanning subscription {subscription_id}: {str(e)}[/red]")
                return subscription_results
        
        console.print(f"[green]Completed: {resource_count} resources scanned[/green]")
        return subscription_results
    
    def auto_remediate(
        self, 
        resource_id: str, 
        default_tags: Dict[str, str]
    ) -> bool:
        """Apply default tags to non-compliant resources"""
        try:
            # Extract subscription and resource group from resource ID
            parts = resource_id.split('/')
            subscription_id = parts[2]
            
            resource_client = ResourceManagementClient(
                self.credential, 
                subscription_id
            )
            
            # Get current resource
            resource = resource_client.resources.get_by_id(
                resource_id, 
                api_version='2021-04-01'
            )
            
            # Merge existing tags with defaults
            updated_tags = {**(resource.tags or {}), **default_tags}
            
            # Update resource
            resource_client.resources.update_by_id(
                resource_id,
                api_version='2021-04-01',
                parameters={'tags': updated_tags}
            )
            
            console.print(f"[green]✓ Remediated: {resource_id}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]✗ Remediation failed for {resource_id}: {str(e)}[/red]")
            return False
    
    def generate_compliance_report(self) -> Dict:
        """Generate comprehensive compliance statistics"""
        df = pd.DataFrame([asdict(r) for r in self.results])
        
        if df.empty:
            return {
                'scan_timestamp': datetime.utcnow().isoformat(),
                'summary': {
                    'total_resources': 0,
                    'compliant': 0,
                    'non_compliant': 0,
                    'remediated': 0,
                    'overall_compliance_rate': 0.0
                },
                'tag_statistics': {},
                'resource_type_breakdown': {},
                'top_violators': {}
            }
        
        total_resources = len(df)
        compliant_resources = len(df[df['compliance_status'] == 'compliant'])
        non_compliant_resources = len(df[df['compliance_status'] == 'non_compliant'])
        remediated_resources = len(df[df['compliance_status'] == 'remediated'])
        
        compliance_rate = (compliant_resources / total_resources * 100) if total_resources > 0 else 0
        
        # Tag-specific statistics
        tag_statistics = {}
        for tag in self.required_tags:
            missing_count = sum(
                1 for r in self.results 
                if tag in r.missing_tags
            )
            tag_statistics[tag] = {
                'missing_count': missing_count,
                'compliance_rate': ((total_resources - missing_count) / total_resources * 100)
                if total_resources > 0 else 0
            }
        
        # Resource type breakdown
        type_breakdown = df.groupby('resource_type')['compliance_status'].value_counts().to_dict()
        
        # Top violators by resource group
        top_violators = (
            df[df['compliance_status'] == 'non_compliant']
            .groupby('resource_group')
            .size()
            .sort_values(ascending=False)
            .head(10)
            .to_dict()
        )
        
        return {
            'scan_timestamp': datetime.utcnow().isoformat(),
            'summary': {
                'total_resources': total_resources,
                'compliant': compliant_resources,
                'non_compliant': non_compliant_resources,
                'remediated': remediated_resources,
                'overall_compliance_rate': round(compliance_rate, 2)
            },
            'tag_statistics': tag_statistics,
            'resource_type_breakdown': type_breakdown,
            'top_violators': top_violators
        }
    
    def display_summary_table(self, report: Dict):
        """Display compliance summary in a formatted table"""
        table = Table(title="Compliance Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")
        
        summary = report['summary']
        table.add_row("Total Resources Scanned", str(summary['total_resources']))
        table.add_row("Compliant Resources", str(summary['compliant']))
        table.add_row("Non-Compliant Resources", str(summary['non_compliant']))
        table.add_row("Remediated Resources", str(summary['remediated']))
        table.add_row("Overall Compliance Rate", f"{summary['overall_compliance_rate']}%")
        
        console.print(table)

def load_configuration() -> Dict:
    """Load configuration from config files"""
    config_path = 'config/required_tags.json'
    
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    else:
        # Default configuration
        return {
            'required_tags': [
                'Environment',
                'CostCenter',
                'Owner',
                'Project',
                'Criticality'
            ],
            'default_tags': {
                'Environment': 'Unknown',
                'ManagedBy': 'Automation',
                'ComplianceCheck': 'Required'
            }
        }

def main():
    """Main execution function"""
    
    console.print("[bold cyan]=" * 60)
    console.print("[bold cyan]Azure Resource Tagging Compliance Checker")
    console.print("[bold cyan]=" * 60)
    
    # Load configuration
    config = load_configuration()
    required_tags = config.get('required_tags', [])
    default_tags = config.get('default_tags', {})
    
    console.print(f"\n[yellow]Required Tags:[/yellow] {', '.join(required_tags)}")
    
    # Initialize checker
    checker = AzureTagComplianceChecker(required_tags)
    
    # Get subscriptions
    subscriptions = checker.get_all_subscriptions()
    
    # Scan all subscriptions
    for sub_id in subscriptions:
        results = checker.scan_subscription(sub_id)
        checker.results.extend(results)
    
    # Generate report
    console.print("\n[cyan]Generating compliance report...[/cyan]")
    report = checker.generate_compliance_report()
    
    # Save results
    output_dir = 'results/reports'
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    # JSON report
    report_file = f'{output_dir}/compliance_report_{timestamp}.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    console.print(f"[green]✓ JSON report saved: {report_file}[/green]")
    
    # CSV export for detailed analysis
    if checker.results:
        df = pd.DataFrame([asdict(r) for r in checker.results])
        csv_file = f'{output_dir}/compliance_details_{timestamp}.csv'
        df.to_csv(csv_file, index=False)
        console.print(f"[green]✓ CSV details saved: {csv_file}[/green]")
    
    # Display summary
    console.print()
    checker.display_summary_table(report)
    
    return report

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {str(e)}[/red]")
        raise
