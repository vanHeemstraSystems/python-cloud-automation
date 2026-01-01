"""
CSV Reporter
Generates CSV exports for compliance data analysis
"""

import os
import json
import csv
from datetime import datetime
from typing import Dict, List
import pandas as pd


class CSVReporter:
    """Generates CSV exports from compliance reports"""
    
    def __init__(self, report_path: str):
        """
        Initialize reporter with a compliance report
        
        Args:
            report_path: Path to JSON compliance report
        """
        with open(report_path, 'r') as f:
            self.report = json.load(f)
        
        # Try to find corresponding details CSV
        self.details_csv = report_path.replace('compliance_report_', 'compliance_details_').replace('.json', '.csv')
    
    def export_summary(self, output_path: str):
        """
        Export summary statistics to CSV
        
        Args:
            output_path: Path for output CSV file
        """
        summary_data = []
        
        # Overall summary
        summary_data.append({
            'Metric': 'Total Resources',
            'Value': self.report['summary']['total_resources'],
            'Category': 'Overall'
        })
        summary_data.append({
            'Metric': 'Compliant Resources',
            'Value': self.report['summary']['compliant'],
            'Category': 'Overall'
        })
        summary_data.append({
            'Metric': 'Non-Compliant Resources',
            'Value': self.report['summary']['non_compliant'],
            'Category': 'Overall'
        })
        summary_data.append({
            'Metric': 'Overall Compliance Rate (%)',
            'Value': self.report['summary']['overall_compliance_rate'],
            'Category': 'Overall'
        })
        
        # Tag-specific statistics
        for tag_name, tag_stats in self.report['tag_statistics'].items():
            summary_data.append({
                'Metric': f'{tag_name} - Missing Count',
                'Value': tag_stats['missing_count'],
                'Category': 'Tag Statistics'
            })
            summary_data.append({
                'Metric': f'{tag_name} - Compliance Rate (%)',
                'Value': round(tag_stats['compliance_rate'], 2),
                'Category': 'Tag Statistics'
            })
        
        # Write to CSV
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df = pd.DataFrame(summary_data)
        df.to_csv(output_path, index=False)
        print(f"Summary CSV exported: {output_path}")
    
    def export_top_violators(self, output_path: str, top_n: int = 20):
        """
        Export top violating resource groups to CSV
        
        Args:
            output_path: Path for output CSV file
            top_n: Number of top violators to include
        """
        violators_data = []
        
        for rg_name, count in list(self.report['top_violators'].items())[:top_n]:
            violators_data.append({
                'Resource Group': rg_name,
                'Non-Compliant Resources': count
            })
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df = pd.DataFrame(violators_data)
        df.to_csv(output_path, index=False)
        print(f"Top violators CSV exported: {output_path}")
    
    def export_tag_analysis(self, output_path: str):
        """
        Export detailed tag analysis to CSV
        
        Args:
            output_path: Path for output CSV file
        """
        tag_data = []
        
        for tag_name, tag_stats in self.report['tag_statistics'].items():
            tag_data.append({
                'Tag Name': tag_name,
                'Missing Count': tag_stats['missing_count'],
                'Compliance Rate (%)': round(tag_stats['compliance_rate'], 2),
                'Total Resources': self.report['summary']['total_resources'],
                'Compliant Resources': self.report['summary']['total_resources'] - tag_stats['missing_count']
            })
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df = pd.DataFrame(tag_data)
        df = df.sort_values('Compliance Rate (%)', ascending=True)
        df.to_csv(output_path, index=False)
        print(f"Tag analysis CSV exported: {output_path}")
    
    def export_resource_type_breakdown(self, output_path: str):
        """
        Export resource type breakdown to CSV
        
        Args:
            output_path: Path for output CSV file
        """
        # Parse the resource type breakdown
        type_breakdown = self.report.get('resource_type_breakdown', {})
        
        type_data = []
        for (resource_type, status), count in type_breakdown.items():
            type_data.append({
                'Resource Type': resource_type,
                'Status': status,
                'Count': count
            })
        
        if type_data:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            df = pd.DataFrame(type_data)
            
            # Pivot to show compliant vs non-compliant side by side
            pivot_df = df.pivot_table(
                index='Resource Type',
                columns='Status',
                values='Count',
                fill_value=0
            ).reset_index()
            
            # Calculate total and compliance rate
            if 'compliant' in pivot_df.columns and 'non_compliant' in pivot_df.columns:
                pivot_df['Total'] = pivot_df['compliant'] + pivot_df['non_compliant']
                pivot_df['Compliance Rate (%)'] = round(
                    (pivot_df['compliant'] / pivot_df['Total'] * 100), 2
                )
            
            pivot_df.to_csv(output_path, index=False)
            print(f"Resource type breakdown CSV exported: {output_path}")
        else:
            print("No resource type breakdown data available")
    
    def export_all(self, output_dir: str):
        """
        Export all CSV reports
        
        Args:
            output_dir: Directory for output CSV files
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        self.export_summary(os.path.join(output_dir, f'summary_{timestamp}.csv'))
        self.export_top_violators(os.path.join(output_dir, f'top_violators_{timestamp}.csv'))
        self.export_tag_analysis(os.path.join(output_dir, f'tag_analysis_{timestamp}.csv'))
        self.export_resource_type_breakdown(os.path.join(output_dir, f'resource_types_{timestamp}.csv'))


def main():
    """Main entry point for CSV reporter"""
    import glob
    
    # Find most recent report
    reports = glob.glob('results/reports/compliance_report_*.json')
    if not reports:
        print("No compliance reports found")
        return
    
    latest_report = max(reports, key=os.path.getctime)
    print(f"Generating CSV exports from: {latest_report}")
    
    # Generate CSV exports
    reporter = CSVReporter(latest_report)
    reporter.export_all('results/reports')


if __name__ == '__main__':
    main()
