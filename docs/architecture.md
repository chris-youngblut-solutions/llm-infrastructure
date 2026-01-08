# Architecture Overview

## System Design

The LLM infrastructure follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                     Access Layer                            │
│  ┌─────────────┐              ┌──────────────┐             │
│  │  OpenWebUI  │              │     n8n      │             │
│  │  (Tailscale)│              │ (Workflows)  │             │
│  └──────┬──────┘              └──────┬───────┘             │
│         │                             │                     │
│         │ API Key Auth                │ API Key Auth        │
└─────────┼─────────────────────────────┼─────────────────────┘
          │                             │
          │                             │
┌─────────▼─────────────────────────────▼─────────────────────┐
│                   Control Layer                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │              Router (FastAPI)                      │     │
│  │  ┌──────────────────────────────────────────────┐ │     │
│  │  │  - Model Selection (Adaptive Routing)        │ │     │
│  │  │  - Health Checks & Lifecycle                 │ │     │
│  │  │  - GPU Resource Management                   │ │     │
│  │  │  - Concurrency Control                       │ │     │
│  │  │  - OpenAI-Compatible API                     │ │     │
│  │  └──────────────────────────────────────────────┘ │     │
│  └────────────────────────────────────────────────────┘     │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           │ vLLM API Calls
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   Execution Layer                            │
│                                                              │
│  GPU 0 (Long Context)          GPU 1 (Throughput)           │
│  ┌────────────────┐             ┌────────────────┐          │
│  │  Llama 3.1 8B  │             │  Llama 3.1 8B  │          │
│  │  (32K context) │             │  (8K context)  │          │
│  └────────────────┘             └────────────────┘          │
│  ┌────────────────┐             ┌────────────────┐          │
│  │  Qwen Coder    │             │  Qwen Coder    │          │
│  │  (16K context) │             │  (8K context)  │          │
│  └────────────────┘             └────────────────┘          │
│  ┌────────────────┐             ┌────────────────┐          │
│  │  DeepSeek R1   │             │  DeepSeek R1   │          │
│  │  (24K context) │             │  (8K context)  │          │
│  └────────────────┘             └────────────────┘          │
│                                 ┌────────────────┐          │
│                                 │    BGE-M3      │          │
│                                 │  (Embeddings)  │          │
│                                 └────────────────┘          │
│                                 ┌────────────────┐          │
│                                 │  BGE Reranker  │          │
│                                 └────────────────┘          │
│                                                              │
│  Both GPUs (Tensor Parallel - Night Mode Only)              │
│  ┌────────────────────────────────────────────┐             │
│  │          Qwen 2.5 72B Instruct            │             │
│  │          (48GB VRAM, 16K context)          │             │
│  └────────────────────────────────────────────┘             │
└──────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Router (Control Plane)

**Technology**: FastAPI, Python 3.11+

**Responsibilities**:
- **Adaptive Routing**: Selects optimal model based on request characteristics
- **Health Management**: Monitors model containers, starts/stops as needed
- **Resource Safety**: Prevents GPU overload via concurrency limits
- **API Compatibility**: Provides OpenAI-compatible `/v1/chat/completions` endpoint
- **TTL Management**: Stops idle models after configurable timeout

**Why a Router?**
- **Single API Surface**: Clients call one endpoint regardless of model
- **Intelligent Selection**: Automatic GPU selection based on context length
- **Resource Optimization**: Dynamic model loading/unloading
- **Abstraction**: Model complexity hidden from clients

**Key Endpoints**:
```
POST /v1/chat/completions    # Chat completion (adaptive routing)
GET  /v1/models              # List available models
POST /v1/embeddings          # Generate embeddings
GET  /health                 # Health check
GET  /metrics                # Prometheus metrics (optional)
```

### 2. vLLM Containers (Execution Layer)

**Technology**: vLLM, CUDA 12.1, PyTorch 2.1+

**Container Strategy**:
- **One model per container**: Isolated VRAM allocation
- **Dynamic lifecycle**: Started on-demand, stopped after TTL
- **GPU assignment**: Via `NVIDIA_VISIBLE_DEVICES`

**Container Naming**:
```
{model}_{gpu}        # Single GPU: llama_0, qwen_1
{model}_dual         # Tensor parallel: qwen_72b_dual
```

**Why vLLM?**
- **Performance**: PagedAttention, continuous batching
- **Compatibility**: OpenAI API compatible
- **GPU Efficiency**: Better VRAM utilization than alternatives
- **Production-ready**: Mature, widely deployed

### 3. OpenWebUI (Human Interface)

**Technology**: Svelte, Node.js

**Integration**:
- Calls router at `http://router:8000`
- API key: `WEBUI_API_KEY`
- Model filtering via router's `/v1/models` endpoint

**Features**:
- Chat interface with history
- Model selection dropdown
- File upload (documents, images)
- Conversation branching
- Markdown rendering

**Why OpenWebUI?**
- Self-hosted (no data leaves network)
- Feature-rich (multi-user, RAG, plugins)
- Actively maintained
- Docker-native

### 4. n8n (Automation Layer)

**Technology**: Node.js, TypeScript

**Architecture**:
```
n8n Workflow → HTTP Request → Router → vLLM Container
                  ↓
            PostgreSQL (workflow data)
```

**Use Cases**:
- Resume generation (scheduled nightly)
- Document processing pipelines
- Job listing ingestion and analysis
- Batch inference tasks

**Why n8n?**
- **Visual workflows**: Low-code interface
- **Self-hosted**: Full data control
- **Extensible**: Custom nodes, webhooks
- **Scheduling**: Cron-based execution

### 5. PostgreSQL (Data Layer)

**Purpose**: n8n workflow execution data

**Schema**:
- Workflow definitions
- Execution history
- Credentials (encrypted)
- Webhook data

**Security**:
- Isolated on `n8n_net` network
- Only n8n can access
- Regular backups

## Network Architecture

### Docker Networks

**llm_net**: Router and model containers
```yaml
llm_net:
  driver: bridge
  ipam:
    config:
      - subnet: 172.20.0.0/16
```

**n8n_net**: n8n and PostgreSQL
```yaml
n8n_net:
  driver: bridge
  ipam:
    config:
      - subnet: 172.21.0.0/16
```

**Router Bridge**: Router connected to both networks
```yaml
router:
  networks:
    - llm_net
    - n8n_net
```

### Why Network Isolation?

1. **Security**: n8n cannot directly access model containers
2. **Control**: All model access goes through router
3. **Observability**: Router logs all requests
4. **Resource Management**: Router enforces limits

### Tailscale Integration

**Access Pattern**:
```
User Device → Tailscale Mesh → Host Machine → Docker Network → Services
```

**Why Tailscale?**
- **Zero-trust**: Device authentication required
- **Encrypted**: WireGuard protocol
- **No NAT traversal**: Works everywhere
- **ACLs**: Fine-grained access control

**Service Exposure**:
- OpenWebUI: `http://hostname:8080` (via Tailscale)
- n8n: `http://hostname:5678` (via Tailscale)
- Router: Internal only (accessed via OpenWebUI/n8n)

## GPU Resource Management

### Strategy Overview

**GPU 0: Long-Context Strategy**
- Max context: 16K-32K tokens
- Concurrency: 2-3 requests
- Target: Single-user interactive sessions
- Models: Llama, Qwen Coder, DeepSeek (long-context configs)

**GPU 1: Throughput Strategy**
- Max context: 8K tokens
- Concurrency: 4-6 requests
- Target: Batch processing, parallel workflows
- Models: Llama, Qwen Coder, DeepSeek (throughput configs) + Embeddings

### Adaptive Routing Logic

```python
def select_gpu(request):
    token_count = estimate_tokens(request.messages)
    
    if token_count > 4096:
        # Long context → GPU 0
        return "gpu_0"
    elif request.source == "webui":
        # Interactive → GPU 0 (sticky)
        return "gpu_0"
    elif request.source == "n8n":
        # Automation → GPU 1
        return "gpu_1"
    else:
        # Default → GPU 1 (higher throughput)
        return "gpu_1"
```

### VRAM Allocation

**Single GPU (24GB)**:
- Model weights: 12-18GB (8B FP16)
- KV cache: 4-8GB (dynamic)
- Overhead: 1-2GB (CUDA, system)

**Dual GPU Tensor Parallel (48GB)**:
- Model weights: 36-40GB (72B AWQ 4-bit)
- KV cache: 6-8GB
- Overhead: 2-4GB

### Concurrency Control

**Per-model limits**:
```python
MODEL_CONFIGS = {
    "llama_0": {"max_concurrent": 3},
    "llama_1": {"max_concurrent": 6},
    "qwen_72b_dual": {"max_concurrent": 2},
}
```

**Router enforcement**:
- Tracks active requests per model
- Returns 503 (Service Unavailable) if limit exceeded
- Clients can retry after backoff

### Model Lifecycle

**Startup**:
1. Router receives request for stopped model
2. Router starts container via Docker API
3. Waits for health check (up to 60s)
4. Forwards request to model

**Idle Shutdown**:
1. Router tracks last request time per model
2. Background task checks every 5 minutes
3. Stops models idle > TTL (default: 30 min)
4. Preserves models with active requests

**Why Dynamic Loading?**
- **VRAM Efficiency**: Only load needed models
- **Cost**: Lower power consumption
- **Flexibility**: Quick model swapping

## Scheduling System

### Time-Based Model Availability

**Day Mode (6 AM - 2 AM)**:
- 8B models on both GPUs
- Focus: Interactive use, development
- GPU 0: Long-context configs
- GPU 1: Throughput + embeddings

**Night Mode (2 AM - 6 AM)**:
- 72B model via tensor parallelism
- Focus: High-quality batch processing
- Use case: Resume generation workflow

### Implementation

```python
import datetime

def is_night_mode():
    hour = datetime.datetime.now().hour
    return 2 <= hour < 6

def get_available_models():
    if is_night_mode():
        return ["qwen_72b_dual"]
    else:
        return ["llama_0", "llama_1", "qwen_coder_0", ...]
```

**Why Time-Based?**
- **Resource Optimization**: 72B model needs both GPUs
- **No Conflicts**: Automated workflows run at night
- **Predictable**: Users know when 72B is available

## Data Flow Examples

### Example 1: Interactive Chat (OpenWebUI)

```
1. User types message in OpenWebUI
2. OpenWebUI → POST /v1/chat/completions (router)
   Headers: Authorization: Bearer {WEBUI_API_KEY}
   Body: {model: "llama", messages: [...]}

3. Router:
   - Validates API key
   - Estimates token count: 2K tokens
   - Selects GPU 0 (webui + low token count)
   - Model llama_0 is running → forward request
   
4. vLLM Container (llama_0):
   - Generates completion
   - Returns response
   
5. Router → OpenWebUI → User sees response
```

### Example 2: Batch Processing (n8n)

```
1. n8n cron triggers resume workflow (2:30 AM)
2. Loop: For each resume:
   
   n8n → POST /v1/chat/completions (router)
   Headers: Authorization: Bearer {N8N_API_KEY}
   Body: {model: "qwen_72b", messages: [...]}
   
3. Router:
   - Validates API key
   - Night mode active → qwen_72b_dual available
   - Checks concurrency: 1/2 active
   - Model running → forward request
   
4. vLLM Container (qwen_72b_dual):
   - Tensor parallel across GPUs 0+1
   - Generates high-quality resume
   - Returns response
   
5. n8n receives response, continues workflow
```

### Example 3: Embedding Generation

```
1. n8n document ingestion workflow
2. n8n → POST /v1/embeddings (router)
   Body: {model: "bge-m3", input: ["doc chunk 1", "doc chunk 2", ...]}
   
3. Router:
   - Forwards to bge_m3_1 (always GPU 1)
   
4. vLLM Container (bge_m3_1):
   - Batches inputs (max 32 per batch)
   - Returns 1024-dim embeddings
   
5. n8n stores embeddings in vector DB
```

## Failure Modes & Recovery

### Model Container Crashes

**Detection**: Health check fails
**Response**: 
1. Router logs error
2. Returns 503 to client
3. Restarts container
4. Client retries after backoff

### GPU OOM (Out of Memory)

**Symptoms**: CUDA OOM error in logs
**Prevention**: Concurrency limits, context limits
**Recovery**: 
1. Router stops offending model
2. Clears GPU memory
3. Restarts with lower concurrency

### Router Crashes

**Impact**: All inference stops
**Recovery**: 
1. Docker restart policy (on-failure)
2. Router restarts, reconnects to Docker
3. Discovers running models, resumes

### Network Partition

**Scenario**: Router loses connection to Docker daemon
**Detection**: Health check failures
**Response**: Restart router service

## Performance Characteristics

### Latency

**First Token (TTFT)**:
- 8B models: 50-200ms
- 72B model: 200-500ms

**Generation Speed**:
- 8B models: 40-60 tokens/sec
- 72B model: 15-25 tokens/sec

### Throughput

**GPU 0 (Long Context)**:
- ~3 concurrent 16K context requests
- ~120 tokens/sec aggregate

**GPU 1 (Throughput)**:
- ~6 concurrent 8K context requests
- ~300 tokens/sec aggregate

### Embeddings

**BGE-M3 on GPU 1**:
- ~1500 documents/sec (512 tokens each)
- ~32 docs per batch optimal

## Scaling Considerations

### Current Limits

- **GPU Count**: 2 (3090s)
- **Max Concurrent**: ~9 requests (3 GPU0 + 6 GPU1)
- **Largest Model**: 72B (tensor parallel)

### Expansion Paths

**Horizontal Scaling** (Not Implemented):
- Add more GPU nodes
- Load balancer in front of multiple routers
- Shared state via Redis

**Vertical Scaling** (Planned):
- DGX with H100 GPUs (80GB VRAM each)
- Enables larger models (405B, DeepSeek V3)
- Higher throughput per GPU

### DGX Integration (Future)

**Architecture**:
```
          ┌─────────────┐
          │   Router    │
          └──────┬──────┘
                 │
        ┌────────┴────────┐
        │                 │
  ┌─────▼─────┐    ┌─────▼─────┐
  │  RTX 3090 │    │  DGX H100 │
  │  (Current)│    │  (Future) │
  └───────────┘    └───────────┘
```

**Router Logic**:
- 8B models → 3090s (day mode)
- 70B+ models → DGX (night mode)
- Automatic backend selection

## Monitoring & Observability

### Health Checks

**Router**:
```
GET /health
Response: {"status": "healthy", "models": {...}}
```

**Model Containers**:
```
GET /health
Response: {"status": "ready", "vram_used": "12.3 GB"}
```

### Metrics (Optional)

**Prometheus Integration**:
- Request latency histograms
- GPU utilization
- Model hit rates
- Error rates

**Grafana Dashboard**:
- Real-time GPU VRAM
- Requests per model
- Queue depths

### Logging

**Router**: Structured JSON logs
```json
{
  "timestamp": "2026-01-08T10:30:45Z",
  "level": "INFO",
  "model": "llama_0",
  "tokens": 2048,
  "latency_ms": 1250,
  "source": "webui"
}
```

**Model Containers**: vLLM logs (stdout)

## Security Architecture

See [Security Guide](security.md) for comprehensive details.

**Defense in Depth**:
1. **Network**: Tailscale + Docker isolation
2. **Authentication**: API keys
3. **Authorization**: Rate limiting (future)
4. **Container**: Non-root users, capability dropping
5. **Data**: Local-only processing

## Design Principles

1. **Separation of Concerns**: Router controls, vLLM executes
2. **API Stability**: OpenAI-compatible interface
3. **Resource Safety**: Concurrency and VRAM limits
4. **Observability**: Logs, metrics, health checks
5. **Simplicity**: Avoid over-engineering for 2-GPU setup
6. **Extensibility**: Easy to add models/GPUs/features

## Trade-offs

### Router as Single Point of Failure
- **Pro**: Simplifies architecture, easy to manage
- **Con**: If router fails, all inference stops
- **Mitigation**: Docker restart policies, monitoring

### Dynamic Model Loading
- **Pro**: VRAM efficiency, flexibility
- **Con**: Startup latency (30-60s)
- **Mitigation**: Sticky routing, TTL tuning

### Time-Based Scheduling
- **Pro**: Predictable, simple
- **Con**: Inflexible (can't run 72B during day)
- **Mitigation**: Manual override (future feature)

### OpenAI API Compatibility
- **Pro**: Easy integration, familiar
- **Con**: Constrained by OpenAI schema
- **Mitigation**: Custom endpoints for specialized features

## Future Considerations

1. **Multi-node Support**: Distribute models across machines
2. **Advanced Scheduling**: Priority queues, preemption
3. **Caching**: KV cache persistence between requests
4. **Speculative Decoding**: Faster generation for common patterns
5. **Multi-modal**: Vision, audio models

---

For implementation details, see:
- [Setup Guide](setup.md)
- [Model Management](model-management.md)
- [Troubleshooting](troubleshooting.md)
