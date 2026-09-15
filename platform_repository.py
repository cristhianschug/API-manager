"""Data access layer for platform.db: clients, API keys, logs, credentials"""
import sqlite3
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from cryptography.fernet import Fernet
import os

from platform_db import get_db_connection

ENCRYPTION_KEY = os.getenv('PLATFORM_ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    raise ValueError("PLATFORM_ENCRYPTION_KEY env var not set — required for credential encryption")

cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

# ============ ENCRYPTION / DECRYPTION ============

def encrypt_password(password: str) -> str:
    """Encrypt a password for storage"""
    return cipher.encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    """Decrypt a stored password"""
    return cipher.decrypt(encrypted.encode()).decode()

# ============ CLIENTS ============

def create_client(name: str, slug: str, host: str, port: int, database_path: str,
                  db_user: str, db_password: str, charset: str = 'UTF8') -> Dict[str, Any]:
    """Create a new client with encrypted credentials"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        encrypted_pwd = encrypt_password(db_password)

        cur.execute(
            """INSERT INTO clients (name, slug, status) VALUES (?, ?, 'active')""",
            (name, slug)
        )
        client_id = cur.lastrowid

        cur.execute(
            """INSERT INTO client_credentials
               (client_id, host, port, database_path, db_user, db_password_encrypted, charset, last_test_ok)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
            (client_id, host, port, database_path, db_user, encrypted_pwd, charset)
        )

        conn.commit()
        return get_client(client_id)
    finally:
        conn.close()

def get_client(client_id: int) -> Optional[Dict[str, Any]]:
    """Get client by ID (with decrypted credentials for test/display)"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT c.id, c.name, c.slug, c.status, c.created_at,
                      cc.host, cc.port, cc.database_path, cc.db_user,
                      cc.db_password_encrypted, cc.charset, cc.last_tested_at, cc.last_test_ok
               FROM clients c
               LEFT JOIN client_credentials cc ON c.id = cc.client_id
               WHERE c.id = ?""",
            (client_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row['id'],
            'name': row['name'],
            'slug': row['slug'],
            'status': row['status'],
            'created_at': row['created_at'],
            'host': row['host'],
            'port': row['port'],
            'database_path': row['database_path'],
            'db_user': row['db_user'],
            'db_password': decrypt_password(row['db_password_encrypted']) if row['db_password_encrypted'] else None,
            'charset': row['charset'],
            'last_tested_at': row['last_tested_at'],
            'last_test_ok': bool(row['last_test_ok']),
        }
    finally:
        conn.close()

def list_clients(status: str = 'active') -> List[Dict[str, Any]]:
    """List all clients, optionally filtered by status"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, name, slug, status, created_at FROM clients WHERE status = ? ORDER BY created_at DESC""",
            (status,)
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def update_client_credentials_test_status(client_id: int, success: bool):
    """Update last_tested_at and last_test_ok for a client"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE client_credentials SET last_tested_at = ?, last_test_ok = ? WHERE client_id = ?""",
            (datetime.utcnow().isoformat(), 1 if success else 0, client_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_client_credentials_for_connection(client_id: int) -> Optional[Dict[str, Any]]:
    """Get client credentials (decrypted) for opening a Firebird connection"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT host, port, database_path, db_user, db_password_encrypted, charset
               FROM client_credentials WHERE client_id = ?""",
            (client_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            'host': row['host'],
            'port': row['port'],
            'database': row['database_path'],
            'user': row['db_user'],
            'password': decrypt_password(row['db_password_encrypted']),
            'charset': row['charset'],
        }
    finally:
        conn.close()

# ============ API KEYS ============

def generate_api_key() -> Tuple[str, str]:
    """Generate a new API key (full value + prefix for display).
    Returns: (full_key, prefix)
    Full key is returned only once; only hash is stored in DB.
    """
    raw = secrets.token_urlsafe(32)
    full_key = f"sk_live_{raw}"
    prefix = full_key[:16] + "..." + full_key[-4:]
    return full_key, prefix

def hash_api_key(key: str) -> str:
    """Hash an API key for storage"""
    return hashlib.sha256(key.encode()).hexdigest()

def create_api_key(client_id: int, name: str, scopes: Dict[str, Dict[str, bool]]) -> Dict[str, Any]:
    """Create a new API key with scopes. Returns the full key (shown only once)."""
    full_key, prefix = generate_api_key()
    key_hash = hash_api_key(full_key)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO api_keys (client_id, name, key_prefix, key_hash, status)
               VALUES (?, ?, ?, ?, 'active')""",
            (client_id, name, prefix, key_hash)
        )
        api_key_id = cur.lastrowid

        # Insert scopes: scopes dict format: {'clientes': {'read': True, 'write': False}, ...}
        for resource, perms in scopes.items():
            cur.execute(
                """INSERT INTO api_key_scopes (api_key_id, resource, can_read, can_write)
                   VALUES (?, ?, ?, ?)""",
                (api_key_id, resource, int(perms.get('read', False)), int(perms.get('write', False)))
            )

        conn.commit()

        # Return key info with the full key visible (only this once)
        return {
            'id': api_key_id,
            'client_id': client_id,
            'name': name,
            'full_key': full_key,
            'prefix': prefix,
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
            'scopes': scopes,
        }
    finally:
        conn.close()

def get_api_key_by_hash(key_hash: str) -> Optional[Dict[str, Any]]:
    """Get API key by hash (lookup during request auth)"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, client_id, name, key_prefix, status, created_at, revoked_at, last_used_at
               FROM api_keys WHERE key_hash = ?""",
            (key_hash,)
        )
        row = cur.fetchone()
        if not row:
            return None

        # Load scopes
        cur.execute(
            """SELECT resource, can_read, can_write FROM api_key_scopes WHERE api_key_id = ?""",
            (row['id'],)
        )
        scopes = {}
        for scope_row in cur.fetchall():
            scopes[scope_row['resource']] = {
                'read': bool(scope_row['can_read']),
                'write': bool(scope_row['can_write']),
            }

        return {
            'id': row['id'],
            'client_id': row['client_id'],
            'name': row['name'],
            'prefix': row['key_prefix'],
            'status': row['status'],
            'created_at': row['created_at'],
            'revoked_at': row['revoked_at'],
            'last_used_at': row['last_used_at'],
            'scopes': scopes,
        }
    finally:
        conn.close()

def list_api_keys(client_id: int) -> List[Dict[str, Any]]:
    """List all API keys for a client"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, client_id, name, key_prefix, status, created_at, revoked_at, last_used_at
               FROM api_keys WHERE client_id = ? ORDER BY created_at DESC""",
            (client_id,)
        )
        keys = []
        for row in cur.fetchall():
            key_id = row['id']
            cur.execute(
                """SELECT resource, can_read, can_write FROM api_key_scopes WHERE api_key_id = ?""",
                (key_id,)
            )
            scopes = {}
            for scope_row in cur.fetchall():
                scopes[scope_row['resource']] = {
                    'read': bool(scope_row['can_read']),
                    'write': bool(scope_row['can_write']),
                }

            keys.append({
                'id': row['id'],
                'name': row['name'],
                'prefix': row['key_prefix'],
                'status': row['status'],
                'created_at': row['created_at'],
                'revoked_at': row['revoked_at'],
                'last_used_at': row['last_used_at'],
                'scopes': scopes,
            })
        return keys
    finally:
        conn.close()

def revoke_api_key(api_key_id: int):
    """Mark an API key as revoked"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE api_keys SET status = 'revoked', revoked_at = ? WHERE id = ?""",
            (datetime.utcnow().isoformat(), api_key_id)
        )
        conn.commit()
    finally:
        conn.close()

def rotate_api_key(api_key_id: int) -> Dict[str, Any]:
    """Revoke current key and generate a new one with same name/scopes"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get old key info
        cur.execute(
            """SELECT client_id, name FROM api_keys WHERE id = ?""",
            (api_key_id,)
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("API key not found")

        client_id = row['client_id']
        name = row['name']

        # Get scopes of old key
        cur.execute(
            """SELECT resource, can_read, can_write FROM api_key_scopes WHERE api_key_id = ?""",
            (api_key_id,)
        )
        scopes = {}
        for scope_row in cur.fetchall():
            scopes[scope_row['resource']] = {
                'read': bool(scope_row['can_read']),
                'write': bool(scope_row['can_write']),
            }

        # Revoke old key
        cur.execute(
            """UPDATE api_keys SET status = 'revoked', revoked_at = ? WHERE id = ?""",
            (datetime.utcnow().isoformat(), api_key_id)
        )
        conn.commit()

        # Create new key with same name/scopes
        return create_api_key(client_id, name, scopes)
    finally:
        conn.close()

def update_api_key_last_used(api_key_id: int):
    """Update last_used_at timestamp for an API key (best-effort, can fail silently)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """UPDATE api_keys SET last_used_at = ? WHERE id = ?""",
            (datetime.utcnow().isoformat(), api_key_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

# ============ REQUEST LOGS ============

def log_request(api_key_id: Optional[int], client_id: Optional[int], method: str, path: str,
                status_code: int, duration_ms: int, error_message: Optional[str] = None):
    """Log a request (best-effort, can fail silently)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO request_logs
               (api_key_id, client_id, method, path, status_code, duration_ms, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (api_key_id, client_id, method, path, status_code, duration_ms, error_message)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_request_logs(client_id: Optional[int] = None, api_key_id: Optional[int] = None,
                     method: Optional[str] = None, path_filter: Optional[str] = None,
                     status_code: Optional[int] = None, hours: int = 24, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Get filtered request logs"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = "SELECT * FROM request_logs WHERE created_at >= ?"
        params = [datetime.utcnow() - timedelta(hours=hours)]

        if client_id is not None:
            query += " AND client_id = ?"
            params.append(client_id)
        if api_key_id is not None:
            query += " AND api_key_id = ?"
            params.append(api_key_id)
        if method is not None:
            query += " AND method = ?"
            params.append(method)
        if path_filter is not None:
            query += " AND path LIKE ?"
            params.append(f"%{path_filter}%")
        if status_code is not None:
            query += " AND status_code = ?"
            params.append(status_code)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def get_request_logs_total_count(client_id: Optional[int] = None, hours: int = 24) -> int:
    """Get total count of requests (for pagination)"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        query = "SELECT COUNT(*) as cnt FROM request_logs WHERE created_at >= ?"
        params = [datetime.utcnow() - timedelta(hours=hours)]

        if client_id is not None:
            query += " AND client_id = ?"
            params.append(client_id)

        cur.execute(query, params)
        return cur.fetchone()['cnt']
    finally:
        conn.close()

def get_request_metrics(client_id: Optional[int] = None, hours: int = 24) -> Dict[str, Any]:
    """Get request metrics: total, errors, top routes"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Total requests
        query = "SELECT COUNT(*) as total FROM request_logs WHERE created_at >= ?"
        params = [datetime.utcnow() - timedelta(hours=hours)]
        if client_id is not None:
            query += " AND client_id = ?"
            params.append(client_id)
        cur.execute(query, params)
        total = cur.fetchone()['total']

        # Error count (4xx/5xx)
        query = "SELECT COUNT(*) as errors FROM request_logs WHERE created_at >= ? AND status_code >= 400"
        params = [datetime.utcnow() - timedelta(hours=hours)]
        if client_id is not None:
            query += " AND client_id = ?"
            params.append(client_id)
        cur.execute(query, params)
        errors = cur.fetchone()['errors']

        # Top 10 routes
        query = "SELECT path, COUNT(*) as count FROM request_logs WHERE created_at >= ?"
        params = [datetime.utcnow() - timedelta(hours=hours)]
        if client_id is not None:
            query += " AND client_id = ?"
            params.append(client_id)
        query += " GROUP BY path ORDER BY count DESC LIMIT 10"
        cur.execute(query, params)
        top_routes = [dict(row) for row in cur.fetchall()]

        return {
            'total_requests': total,
            'error_count': errors,
            'error_rate': (errors / total * 100) if total > 0 else 0,
            'top_routes': top_routes,
        }
    finally:
        conn.close()
