"""
HTML Reporter
Generates interactive HTML dashboards for compliance reports
"""

import os
import json
from datetime import datetime
from typing import Dict, List
import pandas as pd
from jinja2 import Template
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure Tag Compliance Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header .subtitle {
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }
        
        .card {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .card-title {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        
        .card-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }
        
        .card-change {
            font-size: 0.9em;
            margin-top: 10px;
            color: #28a745;
        }
        
        .charts-section {
            padding: 30px;
        }
        
        .chart-container {
            margin-bottom: 40px;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .chart-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #333;
        }
        
        .table-container {
            padding: 30px;
            background: white;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        th {
            background: #667eea;
            color: white;
            font-weight: 600;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .status-compliant {
            background: #d4edda;
            color: #155724;
        }
        
        .status-non-compliant {
            background: #f8d7da;
            color: #721c24;
        }
        
        .footer {
            background: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏷️ Azure Tag Compliance Dashboard</h1>
            <div class="subtitle">Generated: {{ timestamp }}</div>
        </div>
        
        <div class="summary-cards">
            <div class="card">
                <div class="card-title">Total Resources</div>
                <div class="card-value">{{ summary.total_resources }}</div>
            </div>
            <div class="card">
                <div class="card-title">Compliant</div>
                <div class="card-value">{{ summary.compliant }}</div>
                <div class="card-change">{{ summary.compliance_percentage }}%</div>
            </div>
            <div class="card">
                <div class="card-title">Non-Compliant</div>
                <div class="card-value">{{ summary.non_compliant }}</div>
            </div>
            <div class="card">
                <div class="card-title">Overall Compliance</div>
                <div class="card-value">{{ summary.overall_compliance_rate }}%</div>
            </div>
        </div>
        
        <div class="charts-section">
            <div class="chart-container">
                <div class="chart-title">Compliance Overview</div>
                <div id="compliance-pie"></div>
            </div>
            
            <div class="chart-container">
                <div class="chart-title">Tag Compliance by Tag Name</div>
                <div id="tag-compliance-bar"></div>
            </div>
            
            <div class="chart-container">
                <div class="chart-title">Top 10 Non-Compliant Resource Groups</div>
                <div id="violators-bar"></div>
            </div>
        </div>
        
        <div class="table-container">
            <h2 class="chart-title">Top Non-Compliant Resources</h2>
            {{ non_compliant_table }}
        </div>
        
        <div class="footer">
            <p>Generated by Azure Tag Compliance Automation | Willem van Heemstra</p>
            <p>{{ timestamp }}</p>
        </div>
    </div>
    
    <script>
        // Compliance Pie Chart
        var compliancePie = {
            values: [{{ summary.compliant }}, {{ summary.non_compliant }}],
            labels: ['Compliant', 'Non-Compliant'],
            type: 'pie',
            marker: {
                colors: ['#28a745', '#dc3545']
            },
            textinfo: 'label+percent',
            textposition: 'inside'
        };
        
        Plotly.newPlot('compliance-pie', [compliancePie], {
            height: 400,
            margin: {t: 0, b: 0, l: 0, r: 0}
        });
        
        // Tag Compliance Bar Chart
        {{ tag_chart_data }}
        
        // Violators Bar Chart
        {{ violators_chart_data }}
    </script>
</body>
</html>
"""


class HTMLReporter:
    """Generates HTML dashboards from compliance reports"""
    
    def __init__(self, report_path: str):
        """
        Initialize reporter with a compliance report
        
        Args:
            report_path: Path to JSON compliance report
        """
        with open(report_path, 'r') as f:
            self.report = json.load(f)
    
    def generate_dashboard(self, output_path: str):
        """
        Generate interactive HTML dashboard
        
        Args:
            output_path: Path for output HTML file
        """
        template = Template(HTML_TEMPLATE)
        
        # Prepare summary data
        summary = {
            'total_resources': self.report['summary']['total_resources'],
            'compliant': self.report['summary']['compliant'],
            'non_compliant': self.report['summary']['non_compliant'],
            'overall_compliance_rate': self.report['summary']['overall_compliance_rate'],
            'compliance_percentage': round(
                (self.report['summary']['compliant'] / self.report['summary']['total_resources'] * 100)
                if self.report['summary']['total_resources'] > 0 else 0,
                1
            )
        }
        
        # Generate tag compliance chart data
        tag_chart_data = self._generate_tag_chart()
        
        # Generate violators chart data
        violators_chart_data = self._generate_violators_chart()
        
        # Generate non-compliant resources table
        non_compliant_table = self._generate_non_compliant_table()
        
        # Render template
        html_content = template.render(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            summary=summary,
            tag_chart_data=tag_chart_data,
            violators_chart_data=violators_chart_data,
            non_compliant_table=non_compliant_table
        )
        
        # Write to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        print(f"Dashboard generated: {output_path}")
    
    def _generate_tag_chart(self) -> str:
        """Generate JavaScript for tag compliance chart"""
        tag_stats = self.report['tag_statistics']
        
        tags = list(tag_stats.keys())
        compliance_rates = [tag_stats[tag]['compliance_rate'] for tag in tags]
        
        chart_code = f"""
        var tagComplianceBar = {{
            x: {json.dumps(tags)},
            y: {json.dumps(compliance_rates)},
            type: 'bar',
            marker: {{
                color: '#667eea'
            }}
        }};
        
        Plotly.newPlot('tag-compliance-bar', [tagComplianceBar], {{
            height: 400,
            yaxis: {{title: 'Compliance Rate (%)', range: [0, 100]}},
            xaxis: {{title: 'Tag Name'}}
        }});
        """
        
        return chart_code
    
    def _generate_violators_chart(self) -> str:
        """Generate JavaScript for top violators chart"""
        violators = self.report['top_violators']
        
        rgs = list(violators.keys())[:10]
        counts = [violators[rg] for rg in rgs]
        
        chart_code = f"""
        var violatorsBar = {{
            x: {json.dumps(counts)},
            y: {json.dumps(rgs)},
            type: 'bar',
            orientation: 'h',
            marker: {{
                color: '#dc3545'
            }}
        }};
        
        Plotly.newPlot('violators-bar', [violatorsBar], {{
            height: 400,
            xaxis: {{title: 'Number of Non-Compliant Resources'}},
            yaxis: {{title: 'Resource Group'}}
        }});
        """
        
        return chart_code
    
    def _generate_non_compliant_table(self) -> str:
        """Generate HTML table of non-compliant resources"""
        # This would typically load from the CSV file
        # For now, return a placeholder
        return """
        <table>
            <thead>
                <tr>
                    <th>Resource Name</th>
                    <th>Resource Type</th>
                    <th>Resource Group</th>
                    <th>Missing Tags</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td colspan="4" style="text-align: center; padding: 20px;">
                        Load detailed CSV report for complete resource list
                    </td>
                </tr>
            </tbody>
        </table>
        """


def main():
    """Main entry point for HTML reporter"""
    import glob
    
    # Find most recent report
    reports = glob.glob('results/reports/compliance_report_*.json')
    if not reports:
        print("No compliance reports found")
        return
    
    latest_report = max(reports, key=os.path.getctime)
    print(f"Generating dashboard from: {latest_report}")
    
    # Generate dashboard
    reporter = HTMLReporter(latest_report)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f'results/dashboards/compliance_dashboard_{timestamp}.html'
    
    reporter.generate_dashboard(output_path)


if __name__ == '__main__':
    main()
