# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please follow these steps:

1. **DO NOT** open a public issue
2. Email the maintainer directly with details (see CONTACT.md or GitHub profile)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## What to Report

Please report:
- Authentication bypass
- API key leakage
- Container escape vulnerabilities
- Privilege escalation
- Data exposure issues
- Dependency vulnerabilities (critical severity)

## What NOT to Report

Please don't report:
- Issues in upstream dependencies (report to upstream maintainers)
- Theoretical vulnerabilities without proof of concept
- Social engineering or phishing
- Issues related to user configuration errors

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 7 days
- **Fix timeline**: Depends on severity
  - Critical: 1-7 days
  - High: 7-30 days
  - Medium: 30-90 days

## Security Best Practices

This project follows security best practices:

1. **Local-only deployment** (no cloud services)
2. **API key authentication** for all services
3. **Network isolation** via Docker networks
4. **Non-root containers** where possible
5. **Encrypted remote access** via Tailscale
6. **Regular dependency updates**
7. **Principle of least privilege**

## Known Limitations

This infrastructure is designed for:
- **Single-user or small team use**
- **Trusted network environment**
- **Local processing only**

It is **NOT** designed for:
- Multi-tenant environments
- Direct internet exposure
- Untrusted users
- Compliance requirements (HIPAA, SOC2, etc.)

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| Older   | :x:                |

We only support the latest version. Please update before reporting issues.

## Security Updates

Security updates will be:
- Announced in release notes
- Tagged with `security` label
- Documented in CHANGELOG.md

## Additional Security Resources

- [Security Guide](docs/security.md) - Comprehensive security documentation
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

## Responsible Disclosure

We appreciate responsible disclosure of security vulnerabilities. We will:
- Acknowledge your contribution
- Keep you informed of our progress
- Credit you in release notes (if desired)

Thank you for helping keep this project secure!
