# Setup Guide

Complete installation and configuration guide for the Azure Tag Compliance Automation Lab.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Azure Authentication Setup](#azure-authentication-setup)
4. [Configuration](#configuration)
5. [GitHub Actions Setup](#github-actions-setup)
6. [Local Development](#local-development)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.11 or higher**
- **Azure CLI** (version 2.50.0 or higher)
- **Git**
- **Azure Account** with appropriate permissions

### Required Azure Permissions

To run this automation, you need the following Azure RBAC roles:

- **Reader** - To list and read resources
- **Tag Contributor** - To update tags (if auto-remediation is enabled)
- **Cost Management Reader** - For cost data (optional)

### Recommended Setup

- **Visual Studio Code** with Python extension
- **Docker** (for containerized testing)
- **Azure subscription** with at least 100 resources for meaningful testing

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/vanHeemstraSystems/python-cloud-automation.git
cd python-cloud-automation
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt

# Verify installation
python -c "import azure.identity; print('Azure SDK installed successfully')"
```

### 4. Verify Installation

```bash
# Run tests to verify setup
pytest tests/ -v

# Check code quality
pylint src/
black src/ --check
```

---

## Azure Authentication Setup

### Option 1: Azure CLI (Recommended for Local Development)

```bash
# Login to Azure
az login

# Set default subscription
az account set --subscription "Your-Subscription-Name"

# Verify authentication
az account show
```

### Option 2: Service Principal (For Production/CI-CD)

#### Create Service Principal

```bash
# Create service principal with Reader role
az ad sp create-for-rbac \
  --name "tag-compliance-automation" \
  --role "Reader" \
  --scopes /subscriptions/YOUR-SUBSCRIPTION-ID

# Expected output:
# {
#   "appId": "00000000-0000-0000-0000-000000000000",
#   "displayName": "tag-compliance-automation",
#   "password": "your-client-secret",
#   "tenant": "00000000-0000-0000-0000-000000000000"
# }
```

#### Add Tag Contributor Role (if enabling auto-remediation)

```bash
az role assignment create \
  --assignee "00000000-0000-0000-0000-000000000000" \
  --role "Tag Contributor" \
  --scope /subscriptions/YOUR-SUBSCRIPTION-ID
```

#### Set Environment Variables

Create `.env` file in project root:

```bash
# .env file
AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000
AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000
AZURE_CLIENT_SECRET=your-client-secret
AZURE_SUBSCRIPTION_ID=00000000-0000-0000-0000-000000000000
```

**Important**: Add `.env` to `.gitignore` to prevent committing credentials!

### Option 3: Managed Identity (For Azure Resources)

If running on Azure VMs, App Services, or AKS:

```python
# No additional configuration needed
# DefaultAzureCredential automatically uses Managed Identity
```

---

## Configuration

### 1. Configure Required Tags

Edit `config/required_tags.json`:

```json
{
  "tags": [
    {
      "name": "Environment",
      "required": true,
      "allowed_values": ["Dev", "Test", "Prod"],
      "default_value": "Unknown",
      "description": "Deployment environment"
    },
    {
      "name": "CostCenter",
      "required": true,
      "description": "Cost center for billing"
    }
  ]
}
```

### 2. Configure Remediation Rules

Edit `config/remediation_rules.json`:

```json
{
  "rules": [
    {
      "resource_type": "*",
      "action": "add_tags",
      "default_tags": {
        "Environment": "Unknown",
        "ManagedBy": "Automation"
      },
      "enabled": true
    }
  ],
  "remediation_settings": {
    "auto_remediation_enabled": false
  }
}
```

**Important**: Keep `auto_remediation_enabled: false` until you've tested thoroughly!

### 3. Test Configuration

```bash
# Validate configuration files
python -c "
from src.config import get_config
config = get_config()
print(f'Required tags: {config.required_tag_names}')
print(f'Auto-remediation: {config.get_setting(\"enable_auto_remediation\", False)}')
"
```

---

## GitHub Actions Setup

### 1. Configure Repository Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions**, then add:

**Required Secrets:**

```
AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000
AZURE_TENANT_ID=00000000-0000-0000-0000-000000000000
AZURE_SUBSCRIPTION_ID=00000000-0000-0000-0000-000000000000
```

For federated identity (recommended):
- Use **OpenID Connect (OIDC)** instead of client secrets
- More secure, no credential rotation needed

**Optional Secrets:**

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/YOUR/WEBHOOK/URL
```

### 2. Configure Federated Identity (OIDC)

```bash
# Create federated credential
az ad app federated-credential create \
  --id <application-object-id> \
  --parameters '{
    "name": "github-actions-federated",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:YOUR-GITHUB-USERNAME/python-cloud-automation:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

### 3. Customize Workflow Schedule

Edit `.github/workflows/tag-compliance.yml`:

```yaml
on:
  schedule:
    # Run daily at 6 AM UTC
    - cron: '0 6 * * *'  # Customize this!
```

Cron examples:
- Every 6 hours: `'0 */6 * * *'`
- Weekdays at 9 AM: `'0 9 * * 1-5'`
- Weekly on Monday: `'0 0 * * 1'`

### 4. Test Workflow

```bash
# Commit and push workflow
git add .github/workflows/tag-compliance.yml
git commit -m "Add compliance workflow"
git push origin main

# Manually trigger workflow in GitHub Actions UI
# Or via GitHub CLI:
gh workflow run tag-compliance.yml
```

---

## Local Development

### Running Compliance Check

```bash
# Activate virtual environment
source venv/bin/activate

# Run compliance check
python src/tag_compliance.py

# Output will be in results/reports/
```

### Generating Reports

```bash
# Generate HTML dashboard
python src/reporters/html_reporter.py

# Generate CSV exports
python src/reporters/csv_reporter.py

# View HTML dashboard
open results/dashboards/compliance_dashboard_*.html
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html

# Run specific test file
pytest tests/test_compliance.py -v

# Run tests with markers
pytest tests/ -m "not integration"
```

### Code Quality Checks

```bash
# Linting
pylint src/

# Code formatting
black src/

# Security scanning
bandit -r src/

# Type checking
mypy src/
```

---

## Troubleshooting

### Authentication Issues

**Problem**: `DefaultAzureCredential failed to retrieve a token`

**Solutions**:
```bash
# Verify Azure CLI login
az account show

# Clear Azure CLI cache
az account clear
az login

# Check environment variables
echo $AZURE_TENANT_ID
echo $AZURE_CLIENT_ID
```

### Permission Errors

**Problem**: `AuthorizationFailed - does not have authorization to perform action`

**Solutions**:
```bash
# Check current role assignments
az role assignment list --assignee YOUR-SP-APP-ID --all

# Add Reader role
az role assignment create \
  --assignee YOUR-SP-APP-ID \
  --role "Reader" \
  --scope /subscriptions/YOUR-SUBSCRIPTION-ID
```

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'azure'`

**Solutions**:
```bash
# Verify virtual environment is activated
which python  # Should point to venv/bin/python

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check installed packages
pip list | grep azure
```

### GitHub Actions Failures

**Problem**: Workflow fails with authentication errors

**Solutions**:
1. Verify secrets are set correctly in repository settings
2. Check OIDC federated credential configuration
3. Ensure service principal has not expired
4. Review workflow logs for detailed error messages

### Rate Limiting

**Problem**: `TooManyRequests - The request was throttled`

**Solutions**:
```python
# Implement exponential backoff (already in code)
# Reduce scan frequency in config
# Process subscriptions sequentially instead of parallel
```

---

## Next Steps

After successful setup:

1. **Run Initial Scan**: Execute compliance check to establish baseline
2. **Review Results**: Analyze compliance report to understand current state
3. **Configure Notifications**: Set up Slack/Teams webhooks
4. **Schedule Regular Scans**: Enable GitHub Actions workflow
5. **Plan Remediation**: Create action plan for non-compliant resources
6. **Enable Auto-Remediation**: Once comfortable, enable automated fixes

## Support

For issues and questions:

- **GitHub Issues**: [Create an issue](https://github.com/vanHeemstraSystems/python-cloud-automation/issues)
- **Documentation**: See [README.md](../README.md) and [METRICS.md](METRICS.md)
- **Contact**: Willem van Heemstra

---

**Last Updated**: January 2026  
**Version**: 1.0
