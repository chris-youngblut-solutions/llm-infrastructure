# Quick Start Guide

Get your LLM infrastructure running in under 30 minutes.

## Prerequisites

- Ubuntu 24.04 LTS
- NVIDIA GPU(s) with 24GB+ VRAM
- Docker & Docker Compose installed
- NVIDIA Container Toolkit installed
- ~100GB free disk space for models

## 🔒 Security First

This infrastructure is designed for **local-only** use. All data stays on your hardware.

**Critical**: Never commit `.env` files or API keys to git.

## 5-Step Setup

### 1. Clone & Configure

```bash
# Clone repository
git clone https://github.com/yourusername/llm-infrastructure.git
cd llm-infrastructure

# Run setup script
./scripts/setup.sh
```

The setup script will:
- ✅ Check prerequisites
- ✅ Create `.env` from template
- ✅ Validate configuration
- ✅ Create data directories

### 2. Generate API Keys

```bash
# Generate 3 unique keys
python3 -c "import secrets; print('ROUTER_API_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('N8N_API_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('WEBUI_API_KEY=' + secrets.token_urlsafe(32))"
```

Edit `.env` and paste these keys:
```bash
nano .env
```

### 3. Download Models

```bash
# Install HuggingFace CLI
pip install huggingface-hub

# Download core models (required)
huggingface-cli download meta-llama/Meta-Llama-3.1-8B-Instruct \
  --local-dir /path/to/models/Meta-Llama-3.1-8B-Instruct

huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct \
  --local-dir /path/to/models/Qwen2.5-Coder-7B-Instruct

# Download embeddings (for RAG)
huggingface-cli download BAAI/bge-m3 \
  --local-dir /path/to/models/bge-m3
```

**Optional**: Download 72B model for night mode
```bash
huggingface-cli download Qwen/Qwen2.5-72B-Instruct-AWQ \
  --local-dir /path/to/models/Qwen2.5-72B-Instruct-AWQ
```

See [Model Management Guide](docs/model-management.md) for all models.

### 4. Start Services

```bash
# Start infrastructure
docker-compose up -d

# Wait for services to initialize (30-60 seconds)
sleep 60

# Check health
./scripts/health-check.sh
```

Expected output:
```
✓ Docker running
✓ 2 GPU(s) detected
✓ Router running
✓ PostgreSQL running
✓ n8n running
✓ Core infrastructure is healthy
```

### 5. Access Services

**OpenWebUI** (Chat Interface):
```
http://localhost:8080
```

**n8n** (Workflow Automation):
```
http://localhost:5678
```

**Router API** (Direct API Access):
```
http://localhost:8000
```

## First Test

Test the API:
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $ROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama",
    "messages": [
      {"role": "user", "content": "Hello! How are you?"}
    ]
  }'
```

You should get a streaming response from Llama 3.1 8B.

## Configure OpenWebUI

1. Open http://localhost:8080
2. Create admin account (first user is admin)
3. Go to **Settings** → **Connections**
4. Add connection:
   - **Name**: Local LLM Router
   - **URL**: `http://router:8000`
   - **API Key**: (paste `WEBUI_API_KEY` from `.env`)
5. Click **Test Connection** → Should see "✓ Connected"
6. Save

Models will appear in the dropdown automatically.

## Troubleshooting

### Models not loading?
```bash
# Check GPU memory
nvidia-smi

# Check router logs
docker logs router

# Verify model paths
ls -lh /path/to/models/
```

### Connection refused?
```bash
# Check all services running
docker ps

# Restart services
docker-compose restart
```

### Out of memory?
```bash
# Check VRAM usage
nvidia-smi

# Stop non-essential models
docker stop deepseek_0 deepseek_1

# Reduce concurrent requests in .env
nano .env
# Set: GPU_0_MAX_CONCURRENT=2
```

## What's Next?

- **Learn the architecture**: [Architecture Guide](docs/architecture.md)
- **Secure your setup**: [Security Guide](docs/security.md)
- **Add more models**: [Model Management](docs/model-management.md)
- **Create workflows**: [n8n Guide](n8n/README.md)

## Common Tasks

**View running models**:
```bash
docker ps --filter "network=llm_net"
```

**Stop a specific model**:
```bash
docker stop llama_0
```

**View logs**:
```bash
docker logs -f router
docker logs -f llama_0
```

**Restart everything**:
```bash
docker-compose restart
```

**Stop everything**:
```bash
docker-compose down
```

## Getting Help

1. Check [Troubleshooting Guide](docs/troubleshooting.md)
2. Review [Architecture Guide](docs/architecture.md)
3. Open an issue on GitHub (don't include secrets!)

## Important Reminders

- 🔒 **Never commit `.env`** files
- 🔒 **Keep API keys secret**
- 🔒 **Model weights are NOT in git** (download separately)
- 🔒 **Services bind to localhost** (Tailscale for remote access)
- ⚡ **Models start on-demand** (first request may be slow)
- ⚡ **Night mode (2-6 AM)** enables 72B model

---

**You're ready to go!** The infrastructure is running and ready for inference.

For production use, see [Security Guide](docs/security.md) for hardening recommendations.
