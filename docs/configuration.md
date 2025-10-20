# OMOP MCP Server Configuration Guide

This comprehensive guide covers configuring the OMOP MCP server for different environments, databases, and AI clients.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Database Configurations](#database-configurations)
  - [DuckDB (Local Development)](#duckdb-local-development)
  - [BigQuery (Cloud Analytics)](#bigquery-cloud-analytics)
  - [Snowflake (Cloud Analytics)](#snowflake-cloud-analytics)
  - [PostgreSQL (Local/Cloud)](#postgresql-localcloud)
- [AI Client Integrations](#ai-client-integrations)
  - [Ollama](#ollama)
  - [LM Studio](#lm-studio)
  - [Claude Desktop](#claude-desktop)
  - [LibreChat](#librechat)
- [Cloud Deployment](#cloud-deployment)
  - [AWS](#aws)
  - [Google Cloud Platform](#google-cloud-platform)
  - [Azure](#azure)
- [Development Environments](#development-environments)
  - [Visual Studio Code](#visual-studio-code)
  - [PyCharm](#pycharm)
- [Security Configuration](#security-configuration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.11+ (recommended: Python 3.12)
- UV package manager (recommended) or pip
- Database access credentials
- AI client software (Ollama, LM Studio, etc.)

## Environment Setup

### 1. Installation

Choose the appropriate installation method:

```bash
# Using UV (recommended)
uv pip install omop-mcp[all-backends]

# Using pip
pip install omop-mcp[all-backends]

# For specific backends only
uv pip install omop-mcp[duckdb]        # Local development
uv pip install omop-mcp[bigquery]      # BigQuery only
uv pip install omop-mcp[snowflake]     # Snowflake only
uv pip install omop-mcp[postgres]      # PostgreSQL only
uv pip install omop-mcp[cloud]        # BigQuery + Snowflake
```

### 2. Environment Variables

Create a `.env` file in your project root:

```bash
# Copy example configuration
cp .env.example .env
```

## Database Configurations

### DuckDB (Local Development)

**Use Case**: Local development, testing, small datasets

```bash
# .env configuration
BACKEND=duckdb
DUCKDB_PATH=./data/omop_sample.duckdb
DUCKDB_SCHEMA=main

# Optional: Enable debugging
LOG_LEVEL=DEBUG
```

**Setup Steps**:

1. **Create sample data**:
```bash
# Download OMOP sample data
mkdir -p data
# Place your OMOP CDM data in DuckDB format at ./data/omop_sample.duckdb
```

2. **Start server**:
```bash
python -m omop_mcp.server --stdio
# or
python -m omop_mcp.server --http --port 8000
```

**Advantages**:
- No external dependencies
- Fast for small datasets
- Perfect for development/testing
- No network latency

### BigQuery (Cloud Analytics)

**Use Case**: Large-scale analytics, production environments

```bash
# .env configuration
BACKEND=bigquery
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
BIGQUERY_DATASET=omop_cdm
BIGQUERY_LOCATION=US

# Security settings
MAX_COST_USD=1.0
STRICT_TABLE_VALIDATION=true
PHI_MODE=true
```

**Setup Steps**:

1. **Create Google Cloud Project**:
```bash
# Install Google Cloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth login
gcloud config set project your-project-id
```

2. **Create Service Account**:
```bash
# Create service account
gcloud iam service-accounts create omop-mcp-server \
    --description="OMOP MCP Server Service Account" \
    --display-name="OMOP MCP Server"

# Grant necessary permissions
gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:omop-mcp-server@your-project-id.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:omop-mcp-server@your-project-id.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"
```

3. **Download credentials**:
```bash
gcloud iam service-accounts keys create omop-mcp-key.json \
    --iam-account=omop-mcp-server@your-project-id.iam.gserviceaccount.com
```

4. **Set environment variables**:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/omop-mcp-key.json
export GOOGLE_CLOUD_PROJECT=your-project-id
```

#### Authentication Methods

The OMOP MCP server supports multiple authentication methods for BigQuery access:

##### Method 1: Service Account (Recommended for Production)

**Configuration**:
```bash
# .env file
BIGQUERY_PROJECT_ID=your-project-id
BIGQUERY_DATASET_ID=omop_cdm
BIGQUERY_CREDENTIALS_PATH=/path/to/service-account.json
```

**Setup**:
```bash
# Create service account key
gcloud iam service-accounts keys create omop-mcp-key.json \
    --iam-account=omop-mcp-server@your-project-id.iam.gserviceaccount.com

# Set environment variable
export BIGQUERY_CREDENTIALS_PATH=/path/to/omop-mcp-key.json
```

**Advantages**:
- Explicit credential management
- Fine-grained permissions
- Audit trail
- Production-ready

##### Method 2: Application Default Credentials (ADC)

**Configuration**:
```bash
# .env file - leave credentials path empty
BIGQUERY_PROJECT_ID=your-project-id
BIGQUERY_DATASET_ID=omop_cdm
BIGQUERY_CREDENTIALS_PATH=  # Empty to use ADC
```

**ADC Options**:

1. **User Credentials (Development)**:
```bash
# Authenticate with your user account
gcloud auth application-default login
```

2. **Service Account via Environment Variable**:
```bash
# Set the standard Google Cloud environment variable
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

3. **Metadata Service (GCP Environments)**:
```bash
# Automatically available in:
# - Cloud Run
# - Compute Engine
# - App Engine
# - Cloud Functions
# - Kubernetes Engine (with Workload Identity)
```

4. **Workload Identity (Kubernetes)**:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: omop-mcp
  annotations:
    iam.gke.io/gcp-service-account: omop-mcp-server@your-project-id.iam.gserviceaccount.com
```

**ADC Advantages**:
- Simplified deployment
- Automatic credential rotation
- Cloud-native integration
- No credential file management

**Authentication Priority**:
1. Service account JSON file (if `BIGQUERY_CREDENTIALS_PATH` is set and file exists)
2. Application Default Credentials (ADC)
   - `GOOGLE_APPLICATION_CREDENTIALS` environment variable
   - Metadata service (GCP environments)
   - User credentials (`gcloud auth application-default login`)

**Advantages**:
- Handles massive datasets
- Built-in security features
- Cost estimation and limits
- Scalable infrastructure

### Snowflake (Cloud Analytics)

**Use Case**: Enterprise data warehousing, complex analytics

```bash
# .env configuration
BACKEND=snowflake
SNOWFLAKE_ACCOUNT=your-account.snowflakecomputing.com
SNOWFLAKE_USER=your-username
SNOWFLAKE_PASSWORD=your-password
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=OMOP_CDM
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_ROLE=ACCOUNTADMIN
```

**Setup Steps**:

1. **Create Snowflake account**:
   - Sign up at [snowflake.com](https://snowflake.com)
   - Create a warehouse, database, and schema

2. **Configure connection**:
```bash
# Test connection
python -c "
from omop_mcp.backends.snowflake import SnowflakeBackend
backend = SnowflakeBackend()
print('Snowflake connection successful!')
"
```

**Advantages**:
- Enterprise-grade security
- Advanced analytics capabilities
- Multi-cloud support
- Excellent performance

### PostgreSQL (Local/Cloud)

**Use Case**: Traditional relational database, existing PostgreSQL infrastructure

```bash
# .env configuration
BACKEND=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=omop_cdm
POSTGRES_USER=omop_user
POSTGRES_PASSWORD=your-password
POSTGRES_SCHEMA=public
```

**Setup Steps**:

1. **Install PostgreSQL**:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql
brew services start postgresql

# Windows
# Download from postgresql.org
```

2. **Create database and user**:
```sql
-- Connect as postgres user
sudo -u postgres psql

-- Create database and user
CREATE DATABASE omop_cdm;
CREATE USER omop_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE omop_cdm TO omop_user;
```

3. **Load OMOP CDM data**:
```bash
# Use your preferred ETL tool to load OMOP CDM data
# Example with psql:
psql -h localhost -U omop_user -d omop_cdm -f omop_cdm_ddl.sql
```

**Advantages**:
- Mature ecosystem
- Rich SQL features
- Good performance
- Familiar to many developers

## AI Client Integrations

### Ollama

**Use Case**: Local AI models, privacy-focused environments

**Setup Steps**:

1. **Install Ollama**:
```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from ollama.ai
```

2. **Start Ollama**:
```bash
ollama serve
```

3. **Configure MCP Server**:
```bash
# Create Ollama MCP configuration
mkdir -p ~/.config/ollama
cat > ~/.config/ollama/mcp.json << EOF
{
  "mcpServers": {
    "omop_mcp": {
      "command": "python",
      "args": ["-m", "omop_mcp.server", "--stdio"],
      "env": {
        "BACKEND": "duckdb",
        "DUCKDB_PATH": "./data/omop_sample.duckdb"
      }
    }
  }
}
EOF
```

4. **Test integration**:
```bash
# Start OMOP MCP server
python -m omop_mcp.server --stdio

# In another terminal, test with Ollama
ollama run llama2 "What concepts are available in the OMOP database?"
```

**Configuration Options**:
```bash
# .env for Ollama integration
BACKEND=duckdb
DUCKDB_PATH=./data/omop_sample.duckdb
LOG_LEVEL=INFO
QUERY_TIMEOUT_SEC=30
```

### LM Studio

**Use Case**: Local AI with GUI, model management

**Setup Steps**:

1. **Install LM Studio**:
   - Download from [lmstudio.ai](https://lmstudio.ai)
   - Install and launch

2. **Configure MCP Server**:
```bash
# Create LM Studio MCP configuration
# macOS
mkdir -p ~/Library/Application\ Support/LMStudio
cat > ~/Library/Application\ Support/LMStudio/mcp.json << EOF
{
  "mcpServers": {
    "omop_mcp": {
      "command": "python",
      "args": ["-m", "omop_mcp.server", "--stdio"],
      "env": {
        "BACKEND": "bigquery",
        "GOOGLE_CLOUD_PROJECT": "your-project-id",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/credentials.json"
      }
    }
  }
}
EOF

# Linux
mkdir -p ~/.config/LMStudio
cat > ~/.config/LMStudio/mcp.json << EOF
{
  "mcpServers": {
    "omop_mcp": {
      "command": "python",
      "args": ["-m", "omop_mcp.server", "--stdio"],
      "env": {
        "BACKEND": "bigquery",
        "GOOGLE_CLOUD_PROJECT": "your-project-id",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/credentials.json"
      }
    }
  }
}
EOF

# Windows
# Create %APPDATA%\LMStudio\mcp.json
```

3. **Restart LM Studio**:
   - Close and reopen LM Studio
   - The OMOP MCP server should appear in available tools

**Usage Examples**:
```
"Find all diabetes-related concepts in the OMOP database"
"Generate SQL to analyze patient demographics by age group"
"Show me the schema for the condition_occurrence table"
"What's the most common condition in the database?"
```

### Claude Desktop

**Use Case**: Anthropic's Claude AI with MCP support

**Setup Steps**:

1. **Install Claude Desktop**:
   - Download from [claude.ai](https://claude.ai)
   - Install and launch

2. **Configure MCP Server**:
```bash
# macOS
mkdir -p ~/Library/Application\ Support/Claude
cat > ~/Library/Application\ Support/Claude/claude_desktop_config.json << EOF
{
  "mcpServers": {
    "omop_mcp": {
      "command": "python",
      "args": ["-m", "omop_mcp.server", "--stdio"],
      "env": {
        "BACKEND": "bigquery",
        "GOOGLE_CLOUD_PROJECT": "your-project-id",
        "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/credentials.json",
        "STRICT_TABLE_VALIDATION": "true",
        "PHI_MODE": "true"
      }
    }
  }
}
EOF
```

3. **Restart Claude Desktop**:
   - Close and reopen Claude Desktop
   - OMOP tools should be available in the interface

### LibreChat

**Use Case**: Self-hosted chat interface with multiple AI providers

**Setup Steps**:

1. **Install LibreChat**:
```bash
git clone https://github.com/danny-avila/LibreChat.git
cd LibreChat
npm install
```

2. **Configure MCP Server**:
```bash
# Add to LibreChat configuration
cat > .env << EOF
# LibreChat configuration
MONGO_URI=mongodb://localhost:27017/LibreChat
JWT_SECRET=your-jwt-secret

# OMOP MCP Server configuration
OMOP_MCP_SERVER_URL=http://localhost:8000
OMOP_MCP_SERVER_ENABLED=true
EOF
```

3. **Start services**:
```bash
# Start OMOP MCP server
python -m omop_mcp.server --http --port 8000

# Start LibreChat
npm run dev
```

## Cloud Deployment

### AWS

**Use Case**: Scalable cloud deployment with AWS services

**Setup Steps**:

1. **Create EC2 Instance**:
```bash
# Launch EC2 instance (Ubuntu 22.04 LTS)
# Instance type: t3.medium or larger
# Security group: Allow SSH (22) and HTTP (8000)
```

2. **Install dependencies**:
```bash
# Connect to EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install Python and dependencies
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Install OMOP MCP server
uv pip install omop-mcp[all-backends]
```

3. **Configure environment**:
```bash
# Create systemd service
sudo cat > /etc/systemd/system/omop-mcp.service << EOF
[Unit]
Description=OMOP MCP Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
Environment=BACKEND=bigquery
Environment=GOOGLE_CLOUD_PROJECT=your-project-id
Environment=GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/credentials.json
ExecStart=/home/ubuntu/.local/bin/python -m omop_mcp.server --http --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable omop-mcp
sudo systemctl start omop-mcp
sudo systemctl status omop-mcp
```

4. **Configure reverse proxy (optional)**:
```bash
# Install nginx
sudo apt install nginx

# Configure nginx
sudo cat > /etc/nginx/sites-available/omop-mcp << EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/omop-mcp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Google Cloud Platform

**Use Case**: Native GCP integration with BigQuery

**Setup Steps**:

1. **Create Cloud Run service**:
```bash
# Create Dockerfile
cat > Dockerfile << EOF
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "-m", "omop_mcp.server", "--http", "--port", "8000"]
EOF

# Create requirements.txt
cat > requirements.txt << EOF
omop-mcp[all-backends]
EOF

# Build and deploy
gcloud builds submit --tag gcr.io/your-project-id/omop-mcp
gcloud run deploy omop-mcp \
    --image gcr.io/your-project-id/omop-mcp \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars BACKEND=bigquery,GOOGLE_CLOUD_PROJECT=your-project-id
```

2. **Configure IAM**:
```bash
# Grant Cloud Run service account access to BigQuery
gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:your-project-id@appspot.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer"
```

### Azure

**Use Case**: Microsoft Azure cloud deployment

**Setup Steps**:

1. **Create Azure Container Instance**:
```bash
# Create resource group
az group create --name omop-mcp-rg --location eastus

# Create container instance
az container create \
    --resource-group omop-mcp-rg \
    --name omop-mcp \
    --image python:3.12-slim \
    --cpu 1 \
    --memory 2 \
    --ports 8000 \
    --environment-variables \
        BACKEND=bigquery \
        GOOGLE_CLOUD_PROJECT=your-project-id \
    --command-line "pip install omop-mcp[all-backends] && python -m omop_mcp.server --http --port 8000"
```

## Development Environments

### Visual Studio Code

**Use Case**: Development and debugging

**Setup Steps**:

1. **Install MCP Extension**:
   - Open VS Code
   - Go to Extensions (`Ctrl+Shift+X`)
   - Search for "MCP" and install

2. **Configure MCP Server**:
```bash
# Create .vscode/mcp.json
mkdir -p .vscode
cat > .vscode/mcp.json << EOF
{
  "servers": {
    "omop_mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "omop_mcp.server", "--stdio"],
      "env": {
        "BACKEND": "duckdb",
        "DUCKDB_PATH": "./data/omop_sample.duckdb",
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
EOF
```

3. **Configure launch.json for debugging**:
```bash
cat > .vscode/launch.json << EOF
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "OMOP MCP Server (stdio)",
            "type": "python",
            "request": "launch",
            "module": "omop_mcp.server",
            "args": ["--stdio"],
            "env": {
                "BACKEND": "duckdb",
                "DUCKDB_PATH": "./data/omop_sample.duckdb",
                "LOG_LEVEL": "DEBUG"
            },
            "console": "integratedTerminal"
        },
        {
            "name": "OMOP MCP Server (http)",
            "type": "python",
            "request": "launch",
            "module": "omop_mcp.server",
            "args": ["--http", "--port", "8000"],
            "env": {
                "BACKEND": "bigquery",
                "GOOGLE_CLOUD_PROJECT": "your-project-id",
                "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/credentials.json"
            },
            "console": "integratedTerminal"
        }
    ]
}
EOF
```

### PyCharm

**Use Case**: Professional Python development

**Setup Steps**:

1. **Create Run Configuration**:
   - Go to Run → Edit Configurations
   - Add new Python configuration
   - Module name: `omop_mcp.server`
   - Parameters: `--stdio` or `--http --port 8000`
   - Environment variables: Set your `.env` variables

2. **Configure Debugging**:
   - Set breakpoints in your code
   - Use the debugger to step through MCP server execution

## Security Configuration

### Production Security Settings

```bash
# .env for production
STRICT_TABLE_VALIDATION=true
PHI_MODE=true
MAX_COST_USD=0.1
ALLOW_PATIENT_LIST=false
OMOP_BLOCKED_COLUMNS=person_source_value,provider_source_value,location_source_value,care_site_source_value
QUERY_TIMEOUT_SEC=30
LOG_LEVEL=WARNING

# Authentication (if using OAuth)
OAUTH_ENABLED=true
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_AUDIENCE=your-audience
OAUTH_ISSUER=https://your-domain.com
```

### Network Security

```bash
# Firewall rules (example for Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8000/tcp # MCP Server
sudo ufw enable

# For cloud deployments, configure security groups/network ACLs
# to only allow necessary traffic
```

## Troubleshooting

### Common Issues

1. **Connection Errors**:
```bash
# Check if server is running
ps aux | grep omop_mcp

# Check logs
tail -f /var/log/omop-mcp.log

# Test connection
curl http://localhost:8000/health
```

2. **Database Connection Issues**:
```bash
# Test database connection
python -c "
from omop_mcp.backends.registry import get_backend
backend = get_backend('bigquery')
print('Database connection successful!')
"
```

3. **Permission Issues**:
```bash
# Check file permissions
ls -la /path/to/credentials.json

# Check environment variables
env | grep GOOGLE
```

4. **Memory Issues**:
```bash
# Monitor memory usage
htop

# Increase memory limits
export PYTHONHASHSEED=0
export MALLOC_ARENA_MAX=2
```

### Performance Optimization

1. **Caching**:
```bash
# Enable query result caching
ENABLE_QUERY_CACHE=true
QUERY_CACHE_TTL_SEC=3600
MAX_CACHE_SIZE_MB=1000
```

2. **Connection Pooling**:
```bash
# For PostgreSQL
POSTGRES_POOL_SIZE=10
POSTGRES_MAX_OVERFLOW=20
```

3. **Query Optimization**:
```bash
# Set appropriate limits
DEFAULT_ROW_LIMIT=1000
MAX_ROW_LIMIT=10000
QUERY_TIMEOUT_SEC=30
```

### Monitoring and Logging

1. **Structured Logging**:
```bash
# Enable structured logging
LOG_FORMAT=json
LOG_LEVEL=INFO
```

2. **Metrics Collection**:
```bash
# Enable metrics
ENABLE_METRICS=true
METRICS_PORT=9090
```

3. **Health Checks**:
```bash
# Add health check endpoint
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

This comprehensive configuration guide covers all major deployment scenarios for the OMOP MCP server. Choose the configuration that best fits your use case and follow the step-by-step instructions for your specific environment.
