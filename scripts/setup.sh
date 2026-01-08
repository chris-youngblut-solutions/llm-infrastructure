#!/bin/bash
#
# Quick Setup Script for LLM Infrastructure
#
# This script helps with initial setup and validates configuration.
# It does NOT download model weights (those must be done separately).
#
# Usage: ./setup.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "============================================"
echo "LLM Infrastructure Setup"
echo "============================================"
echo ""

# Function to print step
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check prerequisites
print_step "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Please install Docker first."
    exit 1
fi
print_success "Docker installed"

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose not found. Please install Docker Compose first."
    exit 1
fi
print_success "Docker Compose installed"

if ! command -v nvidia-smi &> /dev/null; then
    print_warning "nvidia-smi not found. GPU support may not work."
else
    gpu_count=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
    print_success "$gpu_count GPU(s) detected"
fi

# Check if .env exists
print_step "Checking environment configuration..."

if [ -f .env ]; then
    print_warning ".env file already exists. Skipping creation."
    print_warning "If you want to recreate it, run: rm .env && ./setup.sh"
else
    print_step "Creating .env file from template..."
    cp .env.example .env
    print_success ".env file created"
    
    print_warning "🔒 IMPORTANT: You must edit .env and set:"
    echo "  1. Generate API keys: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    echo "  2. Set MODEL_BASE_PATH to your models directory"
    echo "  3. Update any other paths or settings"
    echo ""
    
    read -p "Press Enter to edit .env now (or edit it later manually)..."
    ${EDITOR:-nano} .env
fi

# Validate .env
print_step "Validating .env configuration..."

source .env

if [ "$ROUTER_API_KEY" == "your_secure_random_key_here" ]; then
    print_error "ROUTER_API_KEY not set in .env"
    print_warning "Generate with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    exit 1
fi

if [ "$N8N_API_KEY" == "your_secure_random_key_here" ]; then
    print_error "N8N_API_KEY not set in .env"
    exit 1
fi

if [ "$WEBUI_API_KEY" == "your_secure_random_key_here" ]; then
    print_error "WEBUI_API_KEY not set in .env"
    exit 1
fi

print_success "API keys configured"

if [ ! -d "$MODEL_BASE_PATH" ]; then
    print_error "MODEL_BASE_PATH ($MODEL_BASE_PATH) does not exist"
    print_warning "Create directory: mkdir -p $MODEL_BASE_PATH"
    print_warning "Then download models (see docs/model-management.md)"
    exit 1
fi

print_success "MODEL_BASE_PATH exists"

# Check if any models exist
model_count=$(find "$MODEL_BASE_PATH" -mindepth 1 -maxdepth 1 -type d | wc -l)
if [ "$model_count" -eq 0 ]; then
    print_warning "No models found in MODEL_BASE_PATH"
    print_warning "You need to download models before starting services"
    print_warning "See: docs/model-management.md for instructions"
    
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    print_success "$model_count model(s) found in MODEL_BASE_PATH"
fi

# Create necessary directories
print_step "Creating data directories..."

mkdir -p n8n-data
mkdir -p pgdata
mkdir -p webui-data
mkdir -p backups

# Set permissions
chmod 700 n8n-data pgdata webui-data backups

print_success "Data directories created"

# Validate Docker Compose
print_step "Validating docker-compose.yml..."

if docker-compose config > /dev/null 2>&1 || docker compose config > /dev/null 2>&1; then
    print_success "docker-compose.yml is valid"
else
    print_error "docker-compose.yml has errors"
    exit 1
fi

# Security check
print_step "Running security checks..."

# Check .gitignore
if grep -q "^\.env$" .gitignore; then
    print_success ".env is in .gitignore"
else
    print_warning ".env not in .gitignore - adding it"
    echo ".env" >> .gitignore
fi

# Check permissions on .env
env_perms=$(stat -c "%a" .env)
if [ "$env_perms" != "600" ]; then
    print_warning ".env permissions are $env_perms, setting to 600"
    chmod 600 .env
fi

# Check for exposed ports
if grep -q '"8000:8000"' docker-compose.yml; then
    print_warning "Router port is exposed to network (not bound to 127.0.0.1)"
    print_warning "Consider changing to: '127.0.0.1:8000:8000'"
fi

# Summary
echo ""
echo "============================================"
echo "Setup Summary"
echo "============================================"
echo ""

print_success "Prerequisites checked"
print_success "Environment configured"
print_success "Data directories created"

if [ "$model_count" -eq 0 ]; then
    print_warning "No models found - download required"
fi

echo ""
echo "Next steps:"
echo ""
echo "1. Download models (if not done already):"
echo "   See: docs/model-management.md"
echo ""
echo "2. Review configuration:"
echo "   nano .env"
echo ""
echo "3. Start services:"
echo "   docker-compose up -d"
echo ""
echo "4. Check health:"
echo "   ./scripts/health-check.sh"
echo ""
echo "5. Access services:"
echo "   - OpenWebUI: http://localhost:8080"
echo "   - n8n: http://localhost:5678"
echo "   - Router API: http://localhost:8000"
echo ""
echo "For more information, see:"
echo "   - docs/setup.md (detailed setup guide)"
echo "   - docs/security.md (security best practices)"
echo "   - docs/architecture.md (system design)"
echo ""

print_success "Setup complete!"
