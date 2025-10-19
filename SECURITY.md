# Security Policy

## 🔒 Security Measures

The OMOP MCP server implements multiple layers of security for healthcare data protection:

### 1. **Query Security**

- **Cost limits**: Prevents expensive queries (configurable via `MAX_COST_USD`)
- **Timeout protection**: Query timeout limits (`MAX_QUERY_TIMEOUT_SEC`)
- **PHI protection**: Patient identifiers are restricted by default (`PHI_MODE=false`)
- **SQL injection prevention**: Parameterized queries and input validation

### 2. **Automated Security Scanning**

We use three complementary tools to detect vulnerabilities:

#### **Bandit** - Python Security Linter
```bash
make security  # Runs bandit
```
- Detects hardcoded passwords, SQL injection patterns
- Scans for insecure cryptographic usage
- Identifies subprocess shell injection risks
- Severity levels: Low, Medium, High

#### **pip-audit** - PyPI Vulnerability Scanner
```bash
make security  # Runs pip-audit
```
- Checks installed packages against PyPI Advisory Database
- Identifies known CVEs in dependencies
- Provides fix versions when available

#### **Safety** - Dependency Vulnerability Database
```bash
make audit  # Runs comprehensive security audit
```
- Checks packages against Safety DB (40,000+ vulnerabilities)
- Covers CVEs, security advisories, and malicious packages
- JSON output for CI/CD integration

### 3. **OAuth 2.0 Authentication** (Optional)

For production deployments:

```bash
# Enable OAuth
export OAUTH_ISSUER=https://your-auth0-domain.auth0.com
export OAUTH_AUDIENCE=omop-mcp-api
```

Supports:
- ✅ JWT token validation
- ✅ Scope-based authorization
- ✅ Token expiration checks
- ✅ Issuer verification

### 4. **Data Protection**

- **No PHI by default**: Patient IDs require explicit `PHI_MODE=true`
- **Aggregated queries**: Demographic breakdowns return counts, not individuals
- **Audit logging**: All queries logged with structlog (when configured)
- **Environment isolation**: Secrets stored in `.env`, never in code

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability, please:

### **DO:**
1. **Email** security@your-domain.com (private disclosure)
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if available)
3. Allow 72 hours for initial response
4. Work with us on coordinated disclosure

### **DO NOT:**
- Open public GitHub issues for security vulnerabilities
- Share exploit code publicly before patch
- Test vulnerabilities on production systems without permission

---

## 🛡️ Security Best Practices

### For Developers

1. **Run security scans before commits**:
   ```bash
   make security  # Quick scan
   make audit     # Comprehensive scan
   ```

2. **Keep dependencies updated**:
   ```bash
   uv sync --upgrade
   pip-audit  # Check for new vulnerabilities
   ```

3. **Review bandit findings**:
   - Medium/High severity issues should be addressed
   - Low severity can be suppressed with `# nosec` (with justification)

4. **Use pre-commit hooks**:
   ```bash
   make pre-commit-install
   ```

### For Operators

1. **Enable OAuth in production**:
   ```bash
   export OAUTH_ISSUER=https://your-provider.com
   export OAUTH_AUDIENCE=omop-mcp-api
   ```

2. **Set restrictive cost limits**:
   ```bash
   export MAX_COST_USD=1.0          # Lower for tighter control
   export MAX_QUERY_TIMEOUT_SEC=30  # Prevent long-running queries
   ```

3. **Disable PHI access unless needed**:
   ```bash
   export PHI_MODE=false  # Default, but be explicit
   ```

4. **Use service accounts with minimal permissions**:
   - BigQuery: Read-only access to OMOP dataset
   - Snowflake: Usage on warehouse, SELECT on CDM tables only

5. **Enable audit logging**:
   ```python
   # In production config
   import structlog
   structlog.configure(
       processors=[
           structlog.stdlib.filter_by_level,
           structlog.stdlib.add_log_level,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.processors.JSONRenderer()
       ]
   )
   ```

6. **Monitor with Prometheus** (optional):
   ```bash
   uv sync --extra observability
   # Access metrics at http://localhost:8000/metrics
   ```

---

## 📊 Security Scanning Results

Our CI/CD pipeline runs security scans on every commit:

- **Bandit**: Scans ~3800 lines of Python code
- **pip-audit**: Checks all dependencies
- **Safety**: Validates against 40,000+ known vulnerabilities

Current status: [![Security Scan](https://github.com/aandresalvarez/omop-mcp/workflows/Quality%20Checks/badge.svg)](https://github.com/aandresalvarez/omop-mcp/actions)

---

## 🔐 Known Security Considerations

### SQL Generation (Bandit B608 warnings)
**Issue**: Dynamic SQL construction triggers bandit warnings  
**Risk**: Low - All queries use parameterization and input validation  
**Mitigation**: 
- Concept IDs validated as integers
- Table names whitelisted against OMOP CDM schema
- No user-provided SQL fragments allowed

### Healthcare Data (HIPAA/PHI)
**Issue**: Healthcare data requires special handling  
**Risk**: Medium - Improper PHI exposure  
**Mitigation**:
- PHI_MODE=false by default (blocks patient_id queries)
- Aggregated queries only return counts
- Recommend: Deploy behind OAuth + audit logging

### Third-party APIs (ATHENA)
**Issue**: Dependency on external ATHENA vocabulary service  
**Risk**: Low - Read-only access to public vocabulary  
**Mitigation**:
- Timeout protection (ATHENA_TIMEOUT_SEC)
- LRU caching to reduce API calls
- Graceful degradation if API unavailable

---

## 📚 Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/index.html)
- [OMOP CDM Security Guidelines](https://ohdsi.github.io/TheBookOfOhdsi/)

---

## 🔄 Security Update Policy

- **Critical vulnerabilities**: Patch within 24-48 hours
- **High severity**: Patch within 1 week
- **Medium/Low severity**: Next regular release

Stay updated:
- Watch this repository for security advisories
- Subscribe to [GitHub Security Advisories](https://github.com/aandresalvarez/omop-mcp/security/advisories)
- Follow releases for security patches

---

**Last Updated**: January 2025  
**Maintained by**: OMOP MCP Security Team
