# Model Weights Directory

## ⚠️ IMPORTANT: Model Weights NOT Included

Model weights are **NOT** stored in this repository because:

1. **Size**: Models range from 2GB to 140GB each (total ~90GB for full set)
2. **Licensing**: Some models have specific licensing requirements
3. **Git limitations**: Git is not designed for large binary files
4. **Security**: Model weights should be stored separately with proper access controls

## What Goes Here

This directory structure documents **how** models should be organized, not the actual model files.

Expected structure after you download models:

```
models/
├── README.md (this file)
├── Meta-Llama-3.1-8B-Instruct/
│   ├── config.json
│   ├── model-*.safetensors
│   ├── tokenizer.json
│   └── tokenizer_config.json
├── Qwen2.5-Coder-7B-Instruct/
│   └── (model files)
├── Qwen2.5-72B-Instruct-AWQ/
│   └── (model files)
├── DeepSeek-R1-Distill-Llama-8B/
│   └── (model files)
├── bge-m3/
│   └── (model files)
└── bge-reranker-v2-m3/
    └── (model files)
```

## Downloading Models

See [Model Management Guide](../docs/model-management.md) for complete instructions.

Quick reference:

```bash
# Install HuggingFace CLI
pip install huggingface-hub

# Download models
huggingface-cli download meta-llama/Meta-Llama-3.1-8B-Instruct \
  --local-dir /path/to/models/Meta-Llama-3.1-8B-Instruct

# Repeat for other models
```

## 🔒 Security Considerations

1. **Permissions**: Set restrictive permissions on model directory
   ```bash
   chmod 700 /path/to/models
   chown yourusername:yourusername /path/to/models
   ```

2. **Checksums**: Verify downloads with checksums
   ```bash
   sha256sum *.safetensors > checksums.txt
   sha256sum -c checksums.txt
   ```

3. **Encryption**: Consider storing on encrypted filesystem (optional but recommended)
   ```bash
   # Example with LUKS
   sudo cryptsetup luksFormat /dev/sdX
   sudo cryptsetup open /dev/sdX models_encrypted
   sudo mkfs.ext4 /dev/mapper/models_encrypted
   ```

4. **Backups**: Backup to external storage (models are large and slow to re-download)
   ```bash
   rsync -avh --progress /path/to/models/ /mnt/backup/models/
   ```

## Model Licensing

**Always review model licenses before use**, especially for commercial purposes:

- **Meta Llama 3.1**: Meta Llama 3.1 Community License (commercial use with restrictions)
- **Qwen**: Apache 2.0 or Tongyi License (check specific model)
- **DeepSeek**: MIT (fully open)
- **BGE**: MIT (fully open)

Review licenses at:
- https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct
- https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct
- https://huggingface.co/Qwen/Qwen2.5-72B-Instruct-AWQ
- https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B
- https://huggingface.co/BAAI/bge-m3
- https://huggingface.co/BAAI/bge-reranker-v2-m3

## Storage Requirements

| Model | Format | Disk Space |
|-------|--------|------------|
| Llama 3.1 8B | FP16 | 16 GB |
| Qwen Coder 7B | FP16 | 14 GB |
| Qwen 72B | AWQ 4-bit | 40 GB |
| DeepSeek R1 8B | FP16 | 16 GB |
| BGE-M3 | FP32 | 2 GB |
| BGE Reranker | FP32 | 2 GB |

**Total**: ~90 GB

**Recommended**: 200-500 GB partition for models + future additions

## Troubleshooting

**"Model not found" error?**
- Verify MODEL_BASE_PATH in .env points to correct directory
- Check that model subdirectories exist
- Ensure config.json and .safetensors files are present

**Download failed?**
- Check internet connection
- Verify HuggingFace credentials (for gated models)
- Try resuming download with `--resume-download` flag

**Out of disk space?**
- Check available space: `df -h`
- Remove unused models
- Consider larger disk or separate partition for models

## Additional Resources

- [Model Management Guide](../docs/model-management.md) - Complete guide
- [HuggingFace Hub](https://huggingface.co/models) - Browse models
- [Setup Guide](../docs/setup.md) - Initial setup instructions

---

**Remember**: Never commit model weights to git. They are too large and often have licensing restrictions.
