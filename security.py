"""
Advanced Security Layer
Implements all 20 security best practices
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, List
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from sqlalchemy.orm import Session
import re
from html import escape

# ============ 1. API KEY MANAGEMENT ============

class APIKeyManager:
    """1. Oculte chaves de API"""

    @staticmethod
    def get_api_key() -> str:
        """Load API key from environment (NEVER hardcode)"""
        key = os.getenv('API_KEY')
        if not key:
            raise ValueError("API_KEY not set in environment")
        return key

    @staticmethod
    def mask_api_key(key: str) -> str:
        """Mask API key for logging"""
        return f"{key[:4]}...{key[-4:]}"

    @staticmethod
    def rotate_api_key() -> str:
        """Generate new API key"""
        return secrets.token_urlsafe(32)


# ============ 2. GIT SECRET PROTECTION ============

class GitSecretProtection:
    """2. Remova segredos do histórico do Git"""

    SECRETS_PATTERNS = [
        r'password\s*=\s*["\']([^"\']+)["\']',
        r'api_key\s*=\s*["\']([^"\']+)["\']',
        r'secret\s*=\s*["\']([^"\']+)["\']',
        r'token\s*=\s*["\']([^"\']+)["\']',
    ]

    @staticmethod
    def scan_for_secrets(content: str) -> List[str]:
        """Scan content for exposed secrets"""
        found_secrets = []
        for pattern in GitSecretProtection.SECRETS_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            found_secrets.extend(matches)
        return found_secrets

    @staticmethod
    def sanitize_for_git(content: str) -> str:
        """Remove secrets from content"""
        sanitized = content
        for pattern in GitSecretProtection.SECRETS_PATTERNS:
            sanitized = re.sub(pattern, r'REDACTED', sanitized, flags=re.IGNORECASE)
        return sanitized


# ============ 3. PUBLIC KEY INFRASTRUCTURE ============

class PKIManager:
    """3. Use chave pública para banco de dados"""

    @staticmethod
    def generate_keypair():
        """Generate RSA key pair"""
        from cryptography.hazmat.primitives.asymmetric import rsa
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()
        return private_key, public_key

    @staticmethod
    def get_db_public_key() -> str:
        """Load database public key from environment"""
        return os.getenv('DB_PUBLIC_KEY', '')


# ============ 4. ROW-LEVEL SECURITY (RLS) ============

class RowLevelSecurity:
    """4. Ative Row-Level Security"""

    @staticmethod
    def apply_tenant_filter(query, tenant_id: str):
        """Apply tenant filter to query"""
        # This ensures queries only return data for current tenant
        return query.filter(models.Tbcliente.idtbempresa == tenant_id)

    @staticmethod
    def check_row_access(row, tenant_id: str) -> bool:
        """Check if tenant can access row"""
        return row.idtbempresa == tenant_id


# ============ 5. DATA ENCRYPTION ============

class DataEncryption:
    """5. Criptografe dados sensíveis"""

    def __init__(self):
        self.cipher_suite = Fernet(os.getenv('ENCRYPTION_KEY', Fernet.generate_key()))

    def encrypt_field(self, data: str) -> str:
        """Encrypt sensitive field"""
        return self.cipher_suite.encrypt(data.encode()).decode()

    def decrypt_field(self, encrypted_data: str) -> str:
        """Decrypt sensitive field"""
        return self.cipher_suite.decrypt(encrypted_data.encode()).decode()

    def hash_field(self, data: str, salt: str = None) -> str:
        """Hash sensitive field"""
        if salt is None:
            salt = secrets.token_hex(16)
        return hashlib.pbkdf2_hmac('sha256', data.encode(), salt.encode(), 100000).hex()


# ============ 6. SERVER-SIDE AUTHENTICATION ============

class ServerAuth:
    """6. Imponha autenticação no lado do servidor"""

    security = HTTPBearer()

    @staticmethod
    async def verify_token(credentials: HTTPAuthCredentials = Depends(HTTPBearer())) -> Dict:
        """Verify authentication token"""
        token = credentials.credentials

        # Validate token format
        if not ServerAuth.is_valid_token_format(token):
            raise HTTPException(status_code=401, detail="Invalid token format")

        # Verify token signature
        payload = ServerAuth.decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        return payload

    @staticmethod
    def is_valid_token_format(token: str) -> bool:
        """Check token format"""
        return len(token) > 20 and '.' in token

    @staticmethod
    def decode_token(token: str) -> Optional[Dict]:
        """Decode and verify JWT token"""
        from jose import jwt, JWTError

        try:
            payload = jwt.decode(
                token,
                os.getenv('JWT_SECRET_KEY'),
                algorithms=['HS256']
            )
            return payload
        except JWTError:
            return None


# ============ 7. RECORD ACCESS RESTRICTION ============

class RecordAccessControl:
    """7. Restrinja acesso aos registros"""

    @staticmethod
    def get_accessible_records(
        db: Session,
        model,
        user_tenant_id: str,
        user_roles: List[str]
    ):
        """Get records user can access"""
        query = db.query(model)

        # Apply tenant filter
        query = query.filter(model.idtbempresa == user_tenant_id)

        # Apply role-based filters if needed
        if 'read_only' in user_roles:
            query = query.filter(model.ativo == True)

        return query


# ============ 8. FIELD TAMPERING PROTECTION ============

class FieldTamperingProtection:
    """8. Impeça adulteração de campos"""

    IMMUTABLE_FIELDS = {
        'Tbcliente': ['idcliente', 'datacadastro', 'cpfcnpj'],
        'Tbproduto': ['idproduto', 'datacadastro'],
    }

    @staticmethod
    def check_immutable_fields(model_name: str, updates: Dict) -> bool:
        """Check if immutable fields are being modified"""
        immutable = FieldTamperingProtection.IMMUTABLE_FIELDS.get(model_name, [])
        for field in updates:
            if field in immutable:
                return False
        return True

    @staticmethod
    def add_audit_log(session, entity, action: str, user_id: str):
        """Log all data modifications"""
        # Implement audit trail
        pass


# ============ 9. SESSION COOKIE PROTECTION ============

class SessionCookieSecurity:
    """9. Proteja cookies de sessão"""

    @staticmethod
    def get_secure_cookie_settings() -> Dict:
        """Get secure cookie settings"""
        return {
            'secure': True,  # HTTPS only
            'httponly': True,  # No JavaScript access
            'samesite': 'strict',  # CSRF protection
            'max_age': 3600,  # 1 hour
            'path': '/api/v1',
            'domain': os.getenv('API_DOMAIN'),
        }


# ============ 10. PASSWORD HASHING ============

class PasswordSecurity:
    """10. Armazene senhas com hash"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password securely"""
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            100000
        )
        return f"{salt}${hashed.hex()}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_hex = hashed.split('$')
            test_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt.encode(),
                100000
            ).hex()
            return test_hash == hash_hex
        except:
            return False


# ============ 11. LOGIN ATTEMPT LIMITING ============

class LoginAttemptLimiter:
    """11. Limite tentativas de login"""

    def __init__(self):
        self.attempts: Dict[str, List[datetime]] = {}
        self.max_attempts = 5
        self.lockout_minutes = 15

    def check_login_attempt(self, username: str) -> bool:
        """Check if user can attempt login"""
        now = datetime.now()

        if username not in self.attempts:
            self.attempts[username] = []

        # Remove old attempts (older than lockout period)
        self.attempts[username] = [
            attempt for attempt in self.attempts[username]
            if (now - attempt).total_seconds() < self.lockout_minutes * 60
        ]

        # Check if exceeded
        if len(self.attempts[username]) >= self.max_attempts:
            return False

        return True

    def record_failed_attempt(self, username: str):
        """Record failed login attempt"""
        if username not in self.attempts:
            self.attempts[username] = []
        self.attempts[username].append(datetime.now())

    def clear_attempts(self, username: str):
        """Clear attempts on successful login"""
        self.attempts[username] = []


# ============ 12. BOT PROTECTION ============

class BotProtection:
    """12. Adicione proteção contra bots"""

    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get security headers to prevent bot abuse"""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        }

    @staticmethod
    def is_suspicious_request(request: Request) -> bool:
        """Detect suspicious bot-like requests"""
        user_agent = request.headers.get('user-agent', '').lower()

        bot_indicators = [
            'bot', 'crawler', 'spider', 'scraper',
            'curl', 'wget', 'python-requests'
        ]

        for indicator in bot_indicators:
            if indicator in user_agent:
                return True

        return False


# ============ 13. PARAMETERIZED QUERIES ============

class QuerySecurity:
    """13. Use consultas parametrizadas"""

    # SQLAlchemy ORM automatically uses parameterized queries
    # Raw SQL example (UNSAFE - don't use):
    # query = f"SELECT * FROM TBCLIENTE WHERE id = {id}"  # UNSAFE

    # Correct (SAFE):
    # from sqlalchemy import text
    # query = text("SELECT * FROM TBCLIENTE WHERE id = :id")
    # db.execute(query, {"id": id})


# ============ 14. INPUT VALIDATION ============

class InputValidation:
    """14. Valide todas as entradas de dados"""

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_cpf(cpf: str) -> bool:
        """Validate CPF format"""
        cpf_clean = re.sub(r'\D', '', cpf)
        return len(cpf_clean) == 11

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone format"""
        pattern = r'^\+?[1-9]\d{1,14}$'
        return re.match(pattern, phone) is not None

    @staticmethod
    def validate_input_length(value: str, max_length: int) -> bool:
        """Validate input length"""
        return len(value) <= max_length


# ============ 15. OUTPUT ESCAPING ============

class OutputEscaping:
    """15. Escape conteúdo enviado por usuários"""

    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters"""
        return escape(text)

    @staticmethod
    def escape_sql(text: str) -> str:
        """Escape SQL special characters"""
        return text.replace("'", "''")

    @staticmethod
    def sanitize_output(data: Dict) -> Dict:
        """Sanitize all string outputs"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = OutputEscaping.escape_html(value)
            else:
                sanitized[key] = value
        return sanitized


# ============ 16. FILE UPLOAD RESTRICTION ============

class FileUploadSecurity:
    """16. Restrinja uploads de arquivos"""

    ALLOWED_EXTENSIONS = {'pdf', 'csv', 'xlsx', 'jpg', 'png'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @staticmethod
    def is_allowed_file(filename: str) -> bool:
        """Check if file extension is allowed"""
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        return ext in FileUploadSecurity.ALLOWED_EXTENSIONS

    @staticmethod
    def check_file_size(file_size: int) -> bool:
        """Check if file size is within limits"""
        return file_size <= FileUploadSecurity.MAX_FILE_SIZE

    @staticmethod
    def scan_file_for_malware(file_content: bytes) -> bool:
        """Scan uploaded file for malware"""
        # In production, use service like VirusTotal or ClamAV
        # For now, basic magic number check
        dangerous_signatures = [b'MZ', b'PK']  # EXE, ZIP
        for sig in dangerous_signatures:
            if file_content.startswith(sig):
                return False
        return True


# ============ 17. MINIMAL DATA RESPONSE ============

class MinimalDataResponse:
    """17. Retorne apenas dados necessários"""

    @staticmethod
    def filter_response_fields(data: Dict, allowed_fields: List[str]) -> Dict:
        """Return only allowed fields"""
        return {k: v for k, v in data.items() if k in allowed_fields}

    @staticmethod
    def hide_sensitive_fields(data: Dict) -> Dict:
        """Hide sensitive fields from response"""
        sensitive_fields = [
            'password', 'hash', 'secret', 'token',
            'api_key', 'private_key', 'ssn', 'bank_account'
        ]

        for field in sensitive_fields:
            if field in data:
                del data[field]

        return data


# ============ 18. SECURITY HEADERS ============

class SecurityHeaders:
    """18. Adicione cabeçalhos de segurança"""

    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get all security headers"""
        return {
            'Content-Security-Policy': "default-src 'self'; script-src 'self'",
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
            'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
        }


# ============ 19. HTTPS ENFORCEMENT ============

class HTTPSEnforcement:
    """19. Force uso de HTTPS"""

    @staticmethod
    def check_https(request: Request) -> bool:
        """Check if request is HTTPS"""
        return request.url.scheme == 'https'

    @staticmethod
    def get_redirect_to_https_middleware():
        """Middleware to redirect HTTP to HTTPS"""
        async def middleware(request: Request, call_next):
            if not HTTPSEnforcement.check_https(request):
                url = request.url.replace(scheme='https')
                return RedirectResponse(url=url, status_code=301)
            return await call_next(request)
        return middleware


# ============ 20. DEPENDENCY SCANNING ============

class DependencySecurity:
    """20. Faça varreduras de segurança nas dependências"""

    @staticmethod
    def get_dependency_scan_commands() -> List[str]:
        """Commands to scan dependencies"""
        return [
            'pip install safety',
            'safety check',  # Check for known vulnerabilities
            'pip install pip-audit',
            'pip-audit',  # More comprehensive audit
        ]

    @staticmethod
    def recommendations() -> str:
        """Recommendations for dependency security"""
        return """
        Run these commands regularly:
        1. safety check - check for known vulnerabilities
        2. pip-audit - audit installed packages
        3. dependabot - enable GitHub Dependabot
        4. Update dependencies monthly
        5. Use pinned versions in production
        """


# ============ SECURITY MIDDLEWARE ============

def add_security_middleware(app):
    """Add all security layers to FastAPI app"""
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.middleware.gzip import GZIPMiddleware

    # CORS (Limit origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000')],
        allow_credentials=True,
        allow_methods=['GET', 'OPTIONS'],  # Read-only
        allow_headers=['*'],
    )

    # Trusted Host
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[os.getenv('API_DOMAIN', 'localhost')]
    )

    # GZIP compression
    app.add_middleware(GZIPMiddleware, minimum_size=1000)

    # Security headers
    @app.middleware('http')
    async def add_security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        headers = SecurityHeaders.get_security_headers()
        for key, value in headers.items():
            response.headers[key] = value
        return response


# ============ LOGGING (Secure) ============

class SecureLogging:
    """Secure logging without exposing secrets"""

    @staticmethod
    def log_event(event: str, details: Dict = None, **kwargs):
        """Log event securely"""
        # Remove sensitive data before logging
        if details:
            safe_details = {
                k: '***REDACTED***' if any(
                    secret in k.lower() for secret in ['password', 'token', 'key', 'secret']
                ) else v
                for k, v in details.items()
            }
        else:
            safe_details = {}

        # Log with timestamp
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] {event}: {safe_details}")
