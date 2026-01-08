# Model Management Guide

## Overview

This guide covers downloading, organizing, and managing model weights for the LLM infrastructure. Model weights are NOT included in the repository due to their size (4GB-140GB per model).

## 🔒 Security Notice

- **Model weights are NOT committed to git** (they're too large and some have licensing restrictions)
- **Verify checksums** after downloading to ensure integrity
- **Store on encrypted filesystem** (optional but recommended)
- **Set restrictive permissions**: `chmod 700 /path/to/models`

## Directory Structure

Recommended structure for model storage:

```
/path/to/models/
├── Meta-Llama-3.1-8B-Instruct/
│   ├── config.json
│   ├── model-00001-of-00004.safetensors
│   ├── model-00002-of-00004.safetensors
│   ├── model-00003-of-00004.safetensors
│   ├── model-00004-of-00004.safetensors
│   ├── tokenizer.json
│   └── tokenizer_config.json
├── Qwen2.5-Coder-7B-Instruct/
│   └── ... (similar structure)
├── Qwen2.5-72B-Instruct-AWQ/
│   └── ... (similar structure)
├── DeepSeek-R1-Distill-Llama-8B/
│   └── ... (similar structure)
├── bge-m3/
│   └── ... (similar structure)
└── bge-reranker-v2-m3/
    └── ... (similar structure)
```

## Model Download Methods

### Method 1: HuggingFace CLI (Recommended)

**Install HuggingFace CLI**:
```bash
pip install huggingface-hub
```

**Login (for gated models)**:
```bash
huggingface-cli login
# Enter your HF token
```

**Download models**:
```bash
# Llama 3.1 8B (requires approval)
huggingface-cli download meta-llama/Meta-Llama-3.1-8B-Instruct \
  --local-dir /path/to/models/Meta-Llama-3.1-8B-Instruct

# Qwen 2.5 Coder 7B
huggingface-cli download Qwen/Qwen2.5-Coder-7B-Instruct \
  --local-dir /path/to/models/Qwen2.5-Coder-7B-Instruct

# Qwen 2.5 72B AWQ (quantized)
huggingface-cli download Qwen/Qwen2.5-72B-Instruct-AWQ \
  --local-dir /path/to/models/Qwen2.5-72B-Instruct-AWQ

# DeepSeek R1 8B
huggingface-cli download deepseek-ai/DeepSeek-R1-Distill-Llama-8B \
  --local-dir /path/to/models/DeepSeek-R1-Distill-Llama-8B

# BGE-M3 (embeddings)
huggingface-cli download BAAI/bge-m3 \
  --local-dir /path/to/models/bge-m3

# BGE Reranker
huggingface-cli download BAAI/bge-reranker-v2-m3 \
  --local-dir /path/to/models/bge-reranker-v2-m3
```

### Method 2: Python Script

```python
from huggingface_hub import snapshot_download

models = [
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct-AWQ",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    "BAAI/bge-m3",
    "BAAI/bge-reranker-v2-m3",
]

base_path = "/path/to/models"

for model_id in models:
    model_name = model_id.split("/")[-1]
    print(f"Downloading {model_name}...")
    
    snapshot_download(
        repo_id=model_id,
        local_dir=f"{base_path}/{model_name}",
        local_dir_use_symlinks=False
    )
    
    print(f"✓ {model_name} downloaded")
```

### Method 3: Git LFS (Advanced)

For specific versions or offline setups:

```bash
# Install git-lfs
sudo apt install git-lfs
git lfs install

# Clone specific model
cd /path/to/models
GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct

cd Meta-Llama-3.1-8B-Instruct
git lfs pull  # Download actual weights
```

## Gated Models

Some models require approval before downloading:

### Meta Llama 3.1

1. Visit https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct
2. Click "Agree and access repository"
3. Wait for approval (usually instant)
4. Download using HF CLI (requires login)

### DeepSeek R1

DeepSeek R1 8B is open-access, no approval needed.

## Verifying Downloads

**Check file integrity**:
```bash
cd /path/to/models/Meta-Llama-3.1-8B-Instruct

# Compare file sizes
du -h *.safetensors

# Verify all required files exist
ls -lh config.json tokenizer.json *.safetensors
```

**Generate checksums** (for backup verification):
```bash
sha256sum *.safetensors > checksums.txt

# Later, verify:
sha256sum -c checksums.txt
```

## Model Configurations

### Current Models

#### Llama 3.1 8B Instruct
- **Size**: ~16GB
- **Format**: FP16 safetensors
- **Context**: 8K native, 32K extended (via RoPE)
- **Use case**: General chat, writing, analysis
- **License**: Meta Llama 3.1 Community License (commercial use allowed)

#### Qwen 2.5 Coder 7B Instruct
- **Size**: ~14GB
- **Format**: FP16 safetensors
- **Context**: 32K native
- **Use case**: Code generation, technical documentation
- **License**: Apache 2.0

#### Qwen 2.5 72B Instruct AWQ
- **Size**: ~40GB (4-bit quantized)
- **Format**: AWQ quantized safetensors
- **Context**: 32K native
- **Use case**: High-quality writing, reasoning
- **License**: Tongyi Qianwen License Agreement (commercial use with restrictions)
- **Note**: Requires tensor parallelism across 2 GPUs

#### DeepSeek R1 8B
- **Size**: ~16GB
- **Format**: FP16 safetensors
- **Context**: 32K native
- **Use case**: Reasoning, chain-of-thought tasks
- **License**: MIT
- **Note**: Experimental, may have OOM issues

#### BGE-M3 (Embeddings)
- **Size**: ~2GB
- **Format**: PyTorch weights
- **Dimensions**: 1024
- **Use case**: Semantic search, RAG
- **License**: MIT

#### BGE Reranker v2-m3
- **Size**: ~2GB
- **Format**: PyTorch weights
- **Use case**: Result reranking
- **License**: MIT

## Adding New Models

### Step 1: Download Weights

Follow download methods above for new model.

### Step 2: Update Configuration

Edit `router/config.py`:

```python
MODEL_CONFIGS = {
    # ... existing models ...
    
    "new_model_0": {
        "model_path": "/path/to/models/new-model",
        "gpu": 0,
        "max_model_len": 8192,
        "max_concurrent": 3,
        "dtype": "float16",
        "quantization": None,  # or "awq" for quantized
    },
}
```

### Step 3: Update Docker Compose

Add new service to `docker-compose.yml`:

```yaml
new_model_0:
  image: vllm/vllm-openai:v0.6.0
  container_name: new_model_0
  environment:
    NVIDIA_VISIBLE_DEVICES: "0"
  volumes:
    - ${MODEL_BASE_PATH}/new-model:/model:ro
  command:
    - --model
    - /model
    - --max-model-len
    - "8192"
    - --gpu-memory-utilization
    - "0.9"
  networks:
    - llm_net
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Step 4: Test

```bash
# Restart services
docker-compose up -d new_model_0

# Test health
curl http://localhost:8000/v1/models

# Test inference
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $ROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "new_model",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Removing Models

### Step 1: Stop Container

```bash
docker-compose stop old_model_0
docker-compose rm old_model_0
```

### Step 2: Update Configuration

Remove from `router/config.py` and `docker-compose.yml`.

### Step 3: Delete Weights (Optional)

```bash
# CAUTION: This permanently deletes the model
rm -rf /path/to/models/old-model

# Or just move to archive
mkdir -p /path/to/archive
mv /path/to/models/old-model /path/to/archive/
```

## Model Quantization

### Why Quantize?

- **VRAM savings**: 4-bit uses ~25% of FP16 VRAM
- **Faster inference**: Lower memory bandwidth
- **Trade-off**: Slight quality loss (~1-3% depending on method)

### Quantization Methods

**AWQ (Activation-aware Weight Quantization)**:
- Best quality/size trade-off
- 4-bit weights
- Pre-quantized models available on HuggingFace

**GPTQ**:
- Similar to AWQ
- Slightly different algorithm
- Also 4-bit

**GGUF** (Not supported by vLLM):
- Used by llama.cpp
- Not compatible with this infrastructure

### Using Pre-Quantized Models

Easiest approach - download AWQ/GPTQ versions:

```bash
# AWQ version (recommended)
huggingface-cli download Qwen/Qwen2.5-72B-Instruct-AWQ \
  --local-dir /path/to/models/Qwen2.5-72B-Instruct-AWQ
```

Update config:
```python
"qwen_72b_dual": {
    "model_path": "/path/to/models/Qwen2.5-72B-Instruct-AWQ",
    "quantization": "awq",  # Enable AWQ
}
```

### Quantizing Models Yourself (Advanced)

**Not recommended** - use pre-quantized models instead. If necessary:

```bash
# Install AutoAWQ
pip install autoawq

# Quantize (this is slow and complex)
python quantize_model.py \
  --model /path/to/fp16/model \
  --output /path/to/awq/model \
  --bits 4
```

See AutoAWQ documentation for details.

## Backup & Recovery

### Backup Strategy

**Model weights**:
- **Option 1**: External hard drive (simple)
- **Option 2**: NAS with RAID (redundancy)
- **Option 3**: Cloud backup (slow, expensive)

**Recommended**:
```bash
# Backup to external drive
rsync -avh --progress /path/to/models/ /mnt/backup/models/

# Verify
diff -r /path/to/models/ /mnt/backup/models/
```

### Recovery

**Restore from backup**:
```bash
rsync -avh --progress /mnt/backup/models/ /path/to/models/

# Verify checksums
cd /path/to/models/Meta-Llama-3.1-8B-Instruct
sha256sum -c checksums.txt
```

## Storage Requirements

### Disk Space

Per-model sizes (approximate):

| Model | Format | Size |
|-------|--------|------|
| Llama 3.1 8B | FP16 | 16 GB |
| Qwen Coder 7B | FP16 | 14 GB |
| Qwen 72B | AWQ 4-bit | 40 GB |
| DeepSeek R1 8B | FP16 | 16 GB |
| BGE-M3 | FP32 | 2 GB |
| BGE Reranker | FP32 | 2 GB |

**Total**: ~90 GB for current model set

**Recommended**: 200-500 GB for models + buffer for future additions

### VRAM Requirements

GPU memory usage (runtime):

| Model | VRAM (8K ctx) | VRAM (32K ctx) |
|-------|---------------|----------------|
| Llama 3.1 8B | 12-14 GB | 18-20 GB |
| Qwen Coder 7B | 11-13 GB | 16-18 GB |
| Qwen 72B (TP) | 40-44 GB | 46-48 GB |
| DeepSeek R1 8B | 12-14 GB | 18-20 GB |
| BGE-M3 | 2-3 GB | N/A |

## Troubleshooting

### "Model not found" Error

**Cause**: Model path incorrect in config

**Fix**:
```bash
# Verify path exists
ls -lh /path/to/models/Meta-Llama-3.1-8B-Instruct

# Check config.json exists
cat /path/to/models/Meta-Llama-3.1-8B-Instruct/config.json

# Update .env
nano .env
# Set: MODEL_BASE_PATH=/correct/path
```

### "Out of Memory" Error

**Cause**: Model too large for available VRAM

**Fix**:
1. Lower `max_model_len` in config
2. Reduce `gpu_memory_utilization` (default 0.9)
3. Use quantized version (AWQ)
4. Lower `max_concurrent` requests

### "Missing Files" Error

**Cause**: Incomplete download

**Fix**:
```bash
# Re-download using HF CLI
huggingface-cli download model/path --local-dir /path/to/models/model

# Verify all files present
ls -lh /path/to/models/model/*.safetensors
```

### Slow Download Speeds

**Fix**:
```bash
# Use mirror (if available)
export HF_ENDPOINT=https://hf-mirror.com

# Or download specific files
huggingface-cli download model/path \
  --include "*.safetensors" \
  --include "*.json"
```

## Model Licensing

**Always review licenses** before use, especially for commercial purposes:

- **Meta Llama 3.1**: Commercial use allowed with restrictions
- **Qwen**: Apache 2.0 (open) or Tongyi License (check specific model)
- **DeepSeek**: MIT (fully open)
- **BGE**: MIT (fully open)

**Check license**:
```bash
# View model card
cat /path/to/models/model-name/README.md

# Or on HuggingFace
# https://huggingface.co/org/model-name
```

## Best Practices

1. **Verify downloads**: Always check checksums
2. **Organize clearly**: Use consistent naming
3. **Document versions**: Track which versions you're using
4. **Backup regularly**: External drive + cloud (optional)
5. **Review licenses**: Ensure compliance
6. **Test before deploying**: Verify model works before production use
7. **Monitor VRAM**: Track usage to prevent OOM
8. **Keep config synced**: Update router config when adding/removing models

## Additional Resources

- [HuggingFace Hub](https://huggingface.co/models)
- [vLLM Supported Models](https://docs.vllm.ai/en/latest/models/supported_models.html)
- [Model Licensing Guide](https://huggingface.co/docs/hub/model-cards#model-card-metadata)
- [Quantization Comparison](https://github.com/vllm-project/vllm/blob/main/docs/source/quantization/quantization.md)

---

For more help:
- [Architecture Overview](architecture.md)
- [Setup Guide](setup.md)
- [Troubleshooting](troubleshooting.md)
