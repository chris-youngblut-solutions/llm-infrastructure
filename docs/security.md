# Security Guide

## Overview

This infrastructure is designed for **local-only deployment** with multiple layers of security. This guide covers security considerations, best practices, and threat model.

## Threat Model

### Design Assumptions

1. **Trusted Network**: Infrastructure runs on private network behind firewall
2. **Single Operator**: No multi-tenancy, single administrator
3. **Local-Only Processing**: No data leaves local network
4. **Tailscale Access**: Remote access via encrypted Tailscale mesh

### Security Posture

**Risk Level**: Medium-Low
- Services bound to localhost
- API key authentication
- Docker network isolation
- No internet-exposed services (except via Tailscale)

### Out of Scope

This infrastructure is NOT designed for:
- Multi-tenant environments
- Direct internet exposure
- Compliance requirements (HIPAA, SOC2, etc.)
- Untrusted user access

## Security Layers

### 1. Network Security

#### Docker Network Isolation

```yaml
# Separate networks for different trust zones
networks:
  llm_net:      # Router and model containers
  n8n_net:      # n8n and PostgreSQL
```

**Principles**:
- Router accessible from both networks (gateway)
- Model containers isolated on llm_net only
- n8n workflows access router, not models directly
- PostgreSQL only accessible to n8n

#### Tailscale Access

**Why Tailscale**:
- Encrypted mesh network (WireGuard-based)
- Zero-trust authentication
- No open ports on public internet
- Device-level access control

**Configuration**:
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Verify
tailscale status
```

**🔒 Security**: Set Tailscale ACLs to restrict which devices can access services.

#### Port Binding

All services bind to `127.0.0.1` (localhost) or Docker internal networks:

```yaml
# Good: Not exposed outside host
ports:
  - "127.0.0.1:8000:8000"

# Bad: Exposed to network
ports:
  - "8000:8000"
```

### 2. Authentication & Authorization

#### API Key Management

**Generation**:
```bash
# Generate cryptographically secure keys
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Output: xK8Pz9QmR7vNj3WbY6TfHg2Lc4Mp1DsA
```

**Storage**:
- Store in `.env` file (never commit)
- Use environment variables in applications
- Consider external secret management for production

**Rotation**:
```bash
# Rotate keys regularly (quarterly recommended)
./scripts/rotate-keys.sh

# Update .env with new keys
nano .env

# Restart services
docker-compose restart
```

#### API Key Validation

Router enforces API key on all endpoints:

```python
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials):
    if credentials.credentials != EXPECTED_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
```

**🔒 Best Practice**: Use different API keys for different clients (OpenWebUI, n8n, scripts).

### 3. Container Security

#### Non-Root Users

All containers run as non-root:

```dockerfile
# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash llmuser

# Switch to non-root
USER llmuser
```

**Why**: Limits damage if container is compromised.

#### Read-Only Filesystems

Where possible, use read-only volumes:

```yaml
volumes:
  - ./router:/app:ro  # Read-only application code
  - /tmp:/tmp:rw      # Writable temp space
```

#### Capability Dropping

Limit container capabilities:

```yaml
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE  # Only if needed
```

#### Resource Limits

Prevent resource exhaustion:

```yaml
deploy:
  resources:
    limits:
      memory: 8G
      cpus: '4'
```

### 4. Data Security

#### Model Weights

**Storage**:
- Store on encrypted filesystem (optional but recommended)
- Set restrictive permissions: `chmod 700 /path/to/models`
- Owner-only access: `chown yourusername:yourusername /path/to/models`

**Integrity**:
```bash
# Generate checksums after download
sha256sum model.safetensors > model.sha256

# Verify before use
sha256sum -c model.sha256
```

**🔒 Never commit model weights to git** (they're 4GB-140GB per model).

#### Sensitive Data in Prompts

**Risk**: Prompts may contain sensitive information (PII, credentials, etc.)

**Mitigations**:
1. **Logging**: Disable or sanitize logs
2. **Retention**: Clear old data regularly
3. **Access Control**: Restrict who can view logs/data
4. **Encryption**: Encrypt volumes at rest (LUKS, dm-crypt)

#### Database Security

PostgreSQL (n8n):
- Change default password in `.env`
- Use strong password (20+ characters)
- Restrict network access (n8n_net only)
- Regular backups with encryption

```bash
# Backup with encryption
pg_dump n8n | gpg --encrypt > backup.sql.gpg
```

### 5. Secrets Management

#### Current Approach (Basic)

Secrets in `.env` file:

**Pros**:
- Simple
- No external dependencies
- Fine for single-operator setup

**Cons**:
- Not suitable for teams
- No audit trail
- No rotation automation

#### Advanced Approach (Optional)

For production or team environments, consider:

1. **HashiCorp Vault**
   - Centralized secret storage
   - Audit logs
   - Dynamic secrets

2. **Docker Secrets**
   ```yaml
   secrets:
     router_api_key:
       external: true
   services:
     router:
       secrets:
         - router_api_key
   ```

3. **Environment-specific .env files**
   ```bash
   # Development
   .env.dev
   
   # Staging
   .env.staging
   
   # Production
   .env.prod
   ```

### 6. Update Management

#### Docker Images

**Pinning**:
```yaml
# Good: Pin to specific version
image: vllm/vllm-openai:v0.6.0

# Bad: Latest tag (unpredictable updates)
image: vllm/vllm-openai:latest
```

**Update Process**:
1. Review release notes
2. Test in development
3. Backup data
4. Update image tags
5. Restart services
6. Verify health

#### Python Dependencies

**Pinning**:
```txt
# requirements.txt
fastapi==0.104.1  # Pin exact versions
uvicorn==0.24.0
```

**Security Scanning**:
```bash
# Check for vulnerabilities
pip install safety
safety check -r requirements.txt
```

## Security Checklist

### Initial Setup

- [ ] Generate unique API keys for each service
- [ ] Store API keys in `.env` (not in code)
- [ ] Add `.env` to `.gitignore`
- [ ] Set restrictive permissions on model directories (700)
- [ ] Configure Tailscale for remote access
- [ ] Verify services bind to localhost only
- [ ] Test API key validation works
- [ ] Set up regular backup schedule

### Ongoing Maintenance

- [ ] Rotate API keys quarterly
- [ ] Review Docker image versions monthly
- [ ] Check for Python dependency vulnerabilities
- [ ] Monitor logs for unusual activity
- [ ] Test backup/restore procedures
- [ ] Review Tailscale ACLs
- [ ] Update documentation

### Before Production

- [ ] Change all default passwords
- [ ] Disable debug logging
- [ ] Enable rate limiting
- [ ] Set up monitoring/alerting
- [ ] Document incident response procedures
- [ ] Test disaster recovery
- [ ] Review all exposed ports/services
- [ ] Conduct security review

## Common Security Mistakes

### ❌ Hardcoded API Keys

```python
# DON'T DO THIS
api_key = "sk-abc123..."
```

```python
# DO THIS
import os
api_key = os.getenv("ROUTER_API_KEY")
```

### ❌ Committing .env Files

```bash
# Check before committing
git status

# If .env is showing, make sure it's in .gitignore
echo ".env" >> .gitignore
```

### ❌ Exposing Services Publicly

```yaml
# DON'T DO THIS
ports:
  - "8000:8000"  # Accessible from network

# DO THIS
ports:
  - "127.0.0.1:8000:8000"  # Localhost only
```

### ❌ Using Default Passwords

```bash
# Change ALL default passwords
POSTGRES_PASSWORD=super_secret_password_here
```

### ❌ Running as Root

```dockerfile
# DON'T DO THIS
USER root

# DO THIS
USER llmuser
```

## Incident Response

### If API Key is Compromised

1. **Immediately rotate key**:
   ```bash
   # Generate new key
   NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
   
   # Update .env
   sed -i "s/ROUTER_API_KEY=.*/ROUTER_API_KEY=$NEW_KEY/" .env
   
   # Restart services
   docker-compose restart
   ```

2. **Review logs** for unauthorized access
3. **Check for data exfiltration**
4. **Document incident**

### If Container is Compromised

1. **Isolate**: Stop affected container
2. **Investigate**: Review logs, check filesystem
3. **Rebuild**: Fresh container from known-good image
4. **Restore**: From backup if needed
5. **Postmortem**: Document and improve

## Compliance Considerations

This infrastructure is designed for personal/small team use. For regulated environments (healthcare, finance, etc.):

- **Encryption at Rest**: Enable LUKS/dm-crypt
- **Audit Logging**: Implement comprehensive logging
- **Access Controls**: Implement RBAC
- **Data Retention**: Define and enforce policies
- **Incident Response**: Formalize procedures
- **Regular Audits**: Schedule security reviews

## Additional Resources

- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Tailscale Security](https://tailscale.com/security)

## Questions?

For security concerns or questions:
1. Review this guide
2. Check documentation in `docs/`
3. Open an issue on GitHub (don't include secrets!)
4. Consult security professionals for production deployments

---

**Remember**: Security is a continuous process, not a one-time setup. Regularly review and update your security practices.
