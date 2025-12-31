#!/bin/bash
# Run this on your Mac to create the directory structure

PROJECT_DIR="$HOME/Documents/Finance/local-ibkr-api"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Create all directories
mkdir -p services/stocks-api/app/{routers,models,schemas,utils}
mkdir -p services/stocks-api/tests/{unit,integration,e2e}
mkdir -p services/stocks-webapp/src/{components,pages,utils}
mkdir -p monitoring/{prometheus,grafana/dashboards}
mkdir -p nginx

echo "✅ Directory structure created at: $PROJECT_DIR"