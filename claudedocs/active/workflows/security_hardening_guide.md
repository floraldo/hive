# Security Hardening Guide for Hive Platform

## Overview
This guide provides comprehensive security recommendations for hardening the Hive platform in production environments.

## Current Security Posture

### ✅ Already Implemented
1. **SQL Injection Prevention**
   - All database queries use parameterized statements
   - No dynamic SQL construction from user input
   - Prepared statements throughout the codebase

2. **Connection Security**
   - Connection timeouts configured (30 seconds default)
   - Connection pooling with proper cleanup
   - Health checks for connection validation

3. **Error Handling**
   - Errors logged without exposing sensitive information
   - Stack traces not exposed to end users
   - Proper exception handling hierarchy

4. **Resource Management**
   - Connection pools with size limits
   - Automatic resource cleanup
   - Memory-efficient operations

## 🔒 Security Hardening Recommendations

### 1. Authentication & Authorization

#### Implement API Key Management
```python
# Add to packages/hive-auth/src/hive_auth/api_keys.py
import hashlib
import secrets
from typing import Optional

class APIKeyManager:
    def generate_api_key(self) -> str:
        """Generate secure API key."""
        return secrets.token_urlsafe(32)

    def hash_api_key(self, api_key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def verify_api_key(self, api_key: str, hashed: str) -> bool:
        """Verify API key against hash."""
        return self.hash_api_key(api_key) == hashed
```

#### Implement Role-Based Access Control (RBAC)
```python
# Add to packages/hive-auth/src/hive_auth/rbac.py
from enum import Enum
from typing import List, Dict

class Role(Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    VIEWER = "viewer"

class Permission(Enum):
    CREATE_TASK = "create_task"
    MODIFY_TASK = "modify_task"
    DELETE_TASK = "delete_task"
    VIEW_TASK = "view_task"
    DEPLOY_SERVICE = "deploy_service"

ROLE_PERMISSIONS = {
    Role.ADMIN: [p for p in Permission],
    Role.DEVELOPER: [Permission.CREATE_TASK, Permission.MODIFY_TASK, Permission.VIEW_TASK],
    Role.REVIEWER: [Permission.VIEW_TASK, Permission.MODIFY_TASK],
    Role.VIEWER: [Permission.VIEW_TASK]
}
```

### 2. Input Validation

#### Implement Request Validation
```python
# Add to packages/hive-validation/src/hive_validation/validators.py
import re
from typing import Any, Dict

class InputValidator:
    def validate_task_id(self, task_id: str) -> bool:
        """Validate task ID format."""
        pattern = r'^[a-zA-Z0-9\-]{1,64}$'
        return bool(re.match(pattern, task_id))

    def validate_json_payload(self, payload: Dict[str, Any], schema: Dict) -> bool:
        """Validate JSON payload against schema."""
        # Use jsonschema for validation
        pass

    def sanitize_user_input(self, text: str) -> str:
        """Sanitize user input for display."""
        # Remove potential XSS vectors
        text = re.sub(r'<[^>]*>', '', text)
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        return text
```

### 3. Secrets Management

#### Environment Variable Configuration
```python
# Add to packages/hive-config/src/hive_config/secrets.py
import os
from typing import Optional

class SecretManager:
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret from environment or secret manager."""
        # First try environment variable
        value = os.environ.get(key)

        if value:
            return value

        # TODO: Integrate with AWS Secrets Manager, Azure Key Vault, etc.
        # For now, return default
        return default

    def validate_secrets(self) -> bool:
        """Validate all required secrets are present."""
        required_secrets = [
            'DATABASE_URL',
            'API_KEY',
            'JWT_SECRET',
            'ENCRYPTION_KEY'
        ]

        missing = [s for s in required_secrets if not os.environ.get(s)]

        if missing:
            raise ValueError(f"Missing required secrets: {missing}")

        return True
```

### 4. Encryption

#### Implement Data Encryption
```python
# Add to packages/hive-crypto/src/hive_crypto/encryption.py
from cryptography.fernet import Fernet
from typing import Union

class DataEncryption:
    def __init__(self, encryption_key: bytes):
        self.cipher = Fernet(encryption_key)

    def encrypt(self, data: Union[str, bytes]) -> bytes:
        """Encrypt sensitive data."""
        if isinstance(data, str):
            data = data.encode()
        return self.cipher.encrypt(data)

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt sensitive data."""
        return self.cipher.decrypt(encrypted_data)
```

### 5. Rate Limiting

#### Implement Rate Limiting
```python
# Add to packages/hive-middleware/src/hive_middleware/rate_limit.py
import time
from typing import Dict, Tuple

class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> Tuple[bool, int]:
        """Check if client is allowed to make request."""
        current_time = time.time()

        if client_id not in self.requests:
            self.requests[client_id] = []

        # Remove old requests outside window
        self.requests[client_id] = [
            t for t in self.requests[client_id]
            if current_time - t < self.window_seconds
        ]

        if len(self.requests[client_id]) >= self.max_requests:
            return False, 0

        self.requests[client_id].append(current_time)
        remaining = self.max_requests - len(self.requests[client_id])

        return True, remaining
```

### 6. Audit Logging

#### Implement Security Audit Logging
```python
# Add to packages/hive-audit/src/hive_audit/security_logger.py
import json
from datetime import datetime
from typing import Any, Dict

class SecurityAuditLogger:
    def log_authentication(self, user_id: str, success: bool, ip: str):
        """Log authentication attempts."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "authentication",
            "user_id": user_id,
            "success": success,
            "ip_address": ip
        }
        self._write_audit_log(event)

    def log_authorization(self, user_id: str, resource: str, action: str, allowed: bool):
        """Log authorization decisions."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "authorization",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "allowed": allowed
        }
        self._write_audit_log(event)

    def log_data_access(self, user_id: str, table: str, operation: str, record_count: int):
        """Log data access patterns."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "data_access",
            "user_id": user_id,
            "table": table,
            "operation": operation,
            "record_count": record_count
        }
        self._write_audit_log(event)

    def _write_audit_log(self, event: Dict[str, Any]):
        """Write to audit log file."""
        # Write to secure, append-only audit log
        with open('/var/log/hive/audit.log', 'a') as f:
            f.write(json.dumps(event) + '\n')
```

### 7. Security Headers

#### Implement Security Headers (for API endpoints)
```python
# Add to packages/hive-middleware/src/hive_middleware/security_headers.py
def add_security_headers(response):
    """Add security headers to HTTP responses."""
    headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'",
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }

    for header, value in headers.items():
        response.headers[header] = value

    return response
```

## 🔐 Security Checklist

### Pre-Deployment
- [ ] All secrets in environment variables or secret manager
- [ ] No hardcoded credentials in code
- [ ] API authentication implemented
- [ ] Rate limiting configured
- [ ] Input validation on all endpoints
- [ ] Security headers configured
- [ ] Audit logging enabled

### Runtime Security
- [ ] Regular security updates applied
- [ ] Monitoring for suspicious activity
- [ ] Regular backup of critical data
- [ ] Incident response plan in place
- [ ] Regular security audits
- [ ] Penetration testing performed

### Data Protection
- [ ] Sensitive data encrypted at rest
- [ ] TLS/SSL for data in transit
- [ ] PII data minimization
- [ ] Data retention policies implemented
- [ ] GDPR/compliance requirements met

## Security Testing

### Automated Security Tests
```python
# Add to tests/security/test_security.py
import pytest

def test_sql_injection_prevention():
    """Test SQL injection prevention."""
    malicious_input = "'; DROP TABLE tasks; --"
    # Verify parameterized queries handle this safely
    pass

def test_xss_prevention():
    """Test XSS prevention."""
    xss_payload = "<script>alert('XSS')</script>"
    # Verify input sanitization
    pass

def test_rate_limiting():
    """Test rate limiting."""
    # Verify rate limits are enforced
    pass

def test_authentication_required():
    """Test authentication is required."""
    # Verify unauthenticated requests are rejected
    pass
```

## Security Tools Integration

### Recommended Tools
1. **Static Analysis**: Bandit for Python security issues
2. **Dependency Scanning**: Safety for vulnerable dependencies
3. **Container Scanning**: Trivy for Docker images
4. **Secret Scanning**: TruffleHog for exposed secrets
5. **SAST**: SonarQube for code quality and security

## Incident Response

### Security Incident Procedure
1. **Detect**: Monitor audit logs and alerts
2. **Contain**: Isolate affected systems
3. **Investigate**: Analyze root cause
4. **Remediate**: Fix vulnerability
5. **Document**: Create incident report
6. **Improve**: Update security measures

## Compliance

### Standards to Consider
- **OWASP Top 10**: Address common web vulnerabilities
- **CIS Controls**: Implement security best practices
- **SOC 2**: For service organizations
- **ISO 27001**: Information security management
- **PCI DSS**: If handling payment data

## Conclusion

This guide provides a comprehensive approach to securing the Hive platform. Implement these recommendations incrementally, prioritizing based on your specific threat model and compliance requirements. Regular security assessments and updates are essential for maintaining a strong security posture.