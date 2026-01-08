# Local LLM Infrastructure

A production-ready, self-hosted LLM infrastructure for running multiple language models with intelligent routing, GPU resource management, and workflow automation.

## 🔒 Security & Privacy Notice

**This infrastructure is designed for LOCAL-ONLY deployment:**
- All inference happens on your hardware
- No data leaves your network
- API keys are stored locally (never committed to git)
- Network access controlled via Tailscale
- Services bound to localhost by default

**⚠️ NEVER commit `.env` files or API keys to version control.**

## Features

- **Multi-GPU Support**: Intelligent routing across NVIDIA RTX 3090s
- **Adaptive Model Selection**: Automatic routing based on context length and workload
- **Resource Management**: Dynamic model loading/unloading to optimize VRAM
- **Workflow Automation**: n8n integration for batch processing
- **Time-Based Scheduling**: Day/night mode for different model availability
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI SDK
- **Health Monitoring**: Built-in health checks and metrics

## Architecture

```
┌─────────────┐     ┌──────────────┐
│  OpenWebUI  │────▶│    Router    │
└─────────────┘     │   (FastAPI)  │
                    └──────┬───────┘
┌─────────────┐            │
│     n8n     │────────────┤
└─────────────┘            │
                    ┌──────▼────────┐
                    │  vLLM Models  │
                    │  (Containers) │
                    └───────────────┘
                    GPU 0      GPU 1
```

### GPU Resource Strategy

- **GPU 0**: Long-context strategy (16K-32K tokens, 2-3 concurrent)
- **GPU 1**: Throughput strategy (8K tokens, 4-6 concurrent)
- **Tensor Parallel** (Both GPUs): 70B models during night mode

## Models Included

### Day Mode (8B Models)
- **Llama 3.1 8B Instruct**: General-purpose chat and generation
- **Qwen 2.5 Coder 7B**: Code generation and technical tasks
- **DeepSeek R1 8B**: Reasoning and analysis (experimental)

### Night Mode (70B Model)
- **Qwen 2.5 72B Instruct**: Premium quality for high-stakes documents

### Retrieval Models
- **BGE-M3**: Document embeddings
- **BGE Reranker**: Result ranking

## Quick Start

### Prerequisites

- Ubuntu 24.04 LTS
- NVIDIA GPU(s) with 24GB+ VRAM
- Docker & Docker Compose
- NVIDIA Container Toolkit
- Tailscale (for remote access)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/llm-infrastructure.git
cd llm-infrastructure
```

2. **🔒 Create environment file (NEVER COMMIT THIS)**
```bash
cp .env.example .env
# Edit .env with your values
nano .env
```

3. **Generate API keys**
```bash
# Generate secure random keys
python3 -c "import secrets; print('ROUTER_API_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('N8N_API_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('WEBUI_API_KEY=' + secrets.token_urlsafe(32))"
```

4. **Download model weights**
```bash
# Models NOT included in repo due to size
# See docs/model-management.md for download instructions
mkdir -p /path/to/models
# Use HuggingFace CLI or direct download
```

5. **Start the infrastructure**
```bash
docker-compose up -d
```

6. **Verify health**
```bash
./scripts/health-check.sh
```

## Configuration

### Environment Variables

See `.env.example` for all available options. Key variables:

- `ROUTER_API_KEY`: Router authentication (🔒 REQUIRED)
- `MODEL_BASE_PATH`: Path to model weights on host
- `GPU_0_MAX_CONCURRENT`: GPU 0 concurrency limit
- `GPU_1_MAX_CONCURRENT`: GPU 1 concurrency limit
- `NIGHT_MODE_START`: Hour to enable 70B models (default: 2)
- `NIGHT_MODE_END`: Hour to disable 70B models (default: 6)

### Model Configuration

Edit `router/config.py` to:
- Add/remove models
- Adjust context lengths
- Modify routing thresholds
- Configure GPU assignments

## Usage

### API Access

```python
from openai import OpenAI

# 🔒 Never hardcode API keys - use environment variables
import os

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key=os.getenv("ROUTER_API_KEY")
)

response = client.chat.completions.create(
    model="llama",  # Router handles model selection
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### OpenWebUI Integration

1. Add custom connection:
   - URL: `http://router:8000`
   - API Key: `${WEBUI_API_KEY}` (from .env)

2. Models will appear automatically via `/v1/models` endpoint

### n8n Workflows

1. Access n8n at configured Tailscale URL
2. Use HTTP Request nodes to call router
3. Headers: `Authorization: Bearer ${N8N_API_KEY}`

## Security Best Practices

### 🔒 Secrets Management

1. **Never commit secrets to git**
   - Use `.env` files (in `.gitignore`)
   - Use environment variables
   - Consider external secret management (Vault, etc.)

2. **Rotate API keys regularly**
```bash
# Generate new keys
./scripts/rotate-keys.sh
# Update .env and restart services
```

3. **Network isolation**
   - Services bound to localhost
   - Use Tailscale for remote access
   - Separate Docker networks for different components

### 🔒 Container Security

1. **Run as non-root user** (already configured)
2. **Limit container capabilities**
3. **Use read-only volumes where possible**
4. **Regular image updates** for security patches

### 🔒 Model Weights Security

1. **Do not commit model weights to git** (100GB+ files)
2. **Use checksums to verify downloads**
3. **Store weights on encrypted filesystem** (optional but recommended)
4. **Backup weights separately** (models directory excluded from git)

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Setup Guide](docs/setup.md)
- [Security Guide](docs/security.md)
- [Model Management](docs/model-management.md)
- [Troubleshooting](docs/troubleshooting.md)

## Monitoring

Health check endpoint:
```bash
curl http://localhost:8000/health
```

Model status:
```bash
curl -H "Authorization: Bearer $ROUTER_API_KEY" \
     http://localhost:8000/v1/models
```

## Troubleshooting

### Common Issues

**Models not loading:**
- Check VRAM availability: `nvidia-smi`
- Verify model paths in `.env`
- Check container logs: `docker logs router`

**Connection refused:**
- Verify services are running: `docker ps`
- Check Tailscale connectivity
- Review firewall rules

**OOM Errors:**
- Reduce concurrent requests
- Lower context lengths
- Use smaller models during day mode

See [Troubleshooting Guide](docs/troubleshooting.md) for more details.

## Backup & Recovery

```bash
# Backup workflows and data
./scripts/backup.sh

# Restore from backup
./scripts/restore.sh /path/to/backup.tar.gz
```

## Contributing

This is a personal infrastructure project, but contributions are welcome:

1. Fork the repository
2. Create a feature branch
3. **🔒 NEVER include real API keys or model weights**
4. Submit a pull request

## License

MIT License - see LICENSE file

## Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm): High-performance inference engine
- [n8n](https://n8n.io/): Workflow automation
- [OpenWebUI](https://github.com/open-webui/open-webui): Chat interface
- Model providers: Meta, Qwen, DeepSeek, BAAI

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- See documentation in `docs/`
- Check troubleshooting guide

---

**⚠️ Security Reminder**: This infrastructure handles potentially sensitive data. Always follow security best practices, keep API keys secret, and never expose services directly to the internet without proper authentication and encryption.
