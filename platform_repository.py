"""Data access layer for platform.db: clients, API keys, logs, credentials"""
import sqlite3
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from cryptography.fernet import Fernet
import os

from platform_db import get_db_connection

_cipher = None

def _get_cipher():
    """Lazy-load cipher only when needed"""
    global _cipher
    if _cipher is None:
        key = os.getenv('PLATFORM_ENCRYPTION_KEY')
        if not key:
            raise ValueError("PLATFORM_ENCRYPTION_KEY env var not set — required for credential encryption")
        _cipher = Fernet(key.encode() if isinstance(key, str) else key)
    return _cipher

# ============ ENCRYPTION / DECRYPTION ============

def encrypt_password(password: str) -> str:
    """Encrypt a password for storage"""
    return _get_cipher().encrypt(password.encode()).decode()

def decrypt_password(encrypted: str) -> str:
    """Decrypt a stored password"""
    return _get_cipher().decrypt(encrypted.encode()).decode()

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

def get_client_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, slug, status FROM clients WHERE slug = ?", (slug,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_client_all_scopes(client_id: int) -> Dict[str, Dict[str, bool]]:
    """Union of scopes across all active API keys for a client"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT s.resource, MAX(s.can_read) AS can_read, MAX(s.can_write) AS can_write
               FROM api_key_scopes s
               JOIN api_keys k ON s.api_key_id = k.id
               WHERE k.client_id = ? AND k.status = 'active'
               GROUP BY s.resource""",
            (client_id,)
        )
        return {row['resource']: {'read': bool(row['can_read']), 'write': bool(row['can_write'])}
                for row in cur.fetchall()}
    finally:
        conn.close()

def list_clients(status: str = 'active', limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """List clients with pagination"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM clients WHERE status = ?", (status,))
        total = cur.fetchone()['cnt']
        cur.execute(
            """SELECT id, name, slug, status, created_at FROM clients
               WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (status, limit, offset)
        )
        return {"clients": [dict(row) for row in cur.fetchall()], "total": total}
    finally:
        conn.close()

# ── Admin users ──────────────────────────────────────────────────────────────

def list_admin_users() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, created_at FROM admin_users ORDER BY created_at")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def create_admin_user(username: str, password_hash: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO admin_users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        return {"id": cur.lastrowid, "username": username}
    except sqlite3.IntegrityError:
        raise ValueError(f"Usuário '{username}' já existe")
    finally:
        conn.close()

def delete_admin_user(admin_id: int) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM admin_users WHERE id = ?", (admin_id,))
        conn.commit()
        return cur.rowcount > 0
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

def create_api_key(client_id: int, name: str, scopes: Dict[str, Dict[str, bool]],
                   expires_in_days: Optional[int] = None) -> Dict[str, Any]:
    """Create a new API key with scopes. Returns the full key (shown only once)."""
    full_key, prefix = generate_api_key()
    key_hash = hash_api_key(full_key)
    expires_at = (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat() if expires_in_days else None

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO api_keys (client_id, name, key_prefix, key_hash, status, expires_at)
               VALUES (?, ?, ?, ?, 'active', ?)""",
            (client_id, name, prefix, key_hash, expires_at)
        )
        api_key_id = cur.lastrowid

        for resource, perms in scopes.items():
            cur.execute(
                """INSERT INTO api_key_scopes (api_key_id, resource, can_read, can_write)
                   VALUES (?, ?, ?, ?)""",
                (api_key_id, resource, int(perms.get('read', False)), int(perms.get('write', False)))
            )

        conn.commit()

        return {
            'id': api_key_id,
            'client_id': client_id,
            'name': name,
            'full_key': full_key,
            'prefix': prefix,
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': expires_at,
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
            """SELECT id, client_id, name, key_prefix, status, created_at, revoked_at, last_used_at, expires_at
               FROM api_keys WHERE key_hash = ?""",
            (key_hash,)
        )
        row = cur.fetchone()
        if not row:
            return None

        # Treat expired keys as revoked
        if row['expires_at'] and row['expires_at'] < datetime.utcnow().isoformat():
            return None

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
            'expires_at': row['expires_at'],
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
            """SELECT id, client_id, name, key_prefix, status, created_at, revoked_at, last_used_at, expires_at
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
                'expires_at': row['expires_at'] if 'expires_at' in row.keys() else None,
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

# ============ AUDIT LOGS ============

def log_admin_action(admin_user: str, action: str, target_type: str,
                     target_id: Optional[int] = None, detail: Optional[str] = None):
    """Record an admin action (best-effort)."""
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO audit_logs (admin_user, action, target_type, target_id, detail) VALUES (?,?,?,?,?)",
            (admin_user, action, target_type, target_id, detail)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_audit_logs(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM audit_logs")
        total = cur.fetchone()['cnt']
        cur.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return {"logs": [dict(r) for r in cur.fetchall()], "total": total}
    finally:
        conn.close()

# ============ SCHEMA SNAPSHOTS ============

def save_schema_snapshot(client_id: int, schema: dict) -> None:
    import json
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO schema_snapshots (client_id, schema_json, captured_at)
           VALUES (?, ?, ?)
           ON CONFLICT(client_id) DO UPDATE SET schema_json=excluded.schema_json, captured_at=excluded.captured_at""",
        (client_id, json.dumps(schema), datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

def get_schema_snapshot(client_id: int) -> Optional[dict]:
    import json
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT schema_json, captured_at FROM schema_snapshots WHERE client_id = ?", (client_id,))
        row = cur.fetchone()
        if not row:
            return None
        data = json.loads(row['schema_json'])
        data['captured_at'] = row['captured_at']
        return data
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

# ============ CONNECTORS ============

import json as _json
import difflib as _difflib

# Rotas disponíveis na API por recurso semântico
_RESOURCE_ROUTES: Dict[str, list] = {
    'clientes':         [('/api/v1/clientes/summary', 'summary'),      ('/api/v1/clientes', 'list')],
    'produtos':         [('/api/v1/produtos/summary', 'summary'),       ('/api/v1/produtos', 'list')],
    'pedidos':          [('/api/v1/pedidos/summary', 'summary'),        ('/api/v1/pedidos', 'list')],
    'parcelas':         [('/api/v1/parcelas/summary', 'summary'),       ('/api/v1/parcelas', 'list')],
    'fornecedores':     [('/api/v1/fornecedores/summary', 'summary'),   ('/api/v1/fornecedores', 'list')],
    'atendimentos':     [('/api/v1/atendimentos/summary', 'summary'),   ('/api/v1/atendimentos', 'list')],
    'ordens servico':   [('/api/v1/ordens-servico/summary', 'summary'), ('/api/v1/ordens-servico', 'list')],
    'ordens prestacao': [('/api/v1/ordens-prestacao/summary', 'summary'), ('/api/v1/ordens-prestacao', 'list')],
}

def _normalize_table(name: str) -> str:
    """TBIAATENDIMENTO → atendimento, TBORDEMPRESTACAOSERVICO → ordens prestacao"""
    name = name.upper()
    for prefix in ('TBIA', 'TBI', 'TB'):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    # ordens: token split on known compound words
    name = name.lower()
    name = name.replace('ordemprestacaoservico', 'ordens prestacao')
    name = name.replace('ordemservico', 'ordens servico')
    name = name.rstrip('s')  # plural → singular for short names
    return name

def create_connector(name: str, description: str, contract: dict) -> dict:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO connector_definitions (name, description, contract_json) VALUES (?, ?, ?)",
            (name, description, _json.dumps(contract))
        )
        conn.commit()
        return get_connector(cur.lastrowid)
    finally:
        conn.close()

def get_connector(connector_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, name, description, contract_json, created_at FROM connector_definitions WHERE id = ?",
            (connector_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {'id': row['id'], 'name': row['name'], 'description': row['description'],
                'contract': _json.loads(row['contract_json']), 'created_at': row['created_at']}
    finally:
        conn.close()

def list_connectors() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, description, contract_json, created_at FROM connector_definitions ORDER BY name")
        return [{'id': r['id'], 'name': r['name'], 'description': r['description'],
                 'contract': _json.loads(r['contract_json']), 'created_at': r['created_at']}
                for r in cur.fetchall()]
    finally:
        conn.close()

def delete_connector(connector_id: int) -> None:
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM connector_definitions WHERE id = ?", (connector_id,))
        conn.commit()
    finally:
        conn.close()

def upsert_binding(connector_id: int, client_id: int, query_id: str,
                   route: str, params: Optional[dict] = None,
                   status: str = 'suggested', confidence: Optional[float] = None,
                   instance_name: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO connector_bindings
                (connector_id, client_id, query_id, route, params_json, status, confidence, instance_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(connector_id, client_id, query_id, instance_name)
            DO UPDATE SET route=excluded.route, params_json=excluded.params_json,
                          status=excluded.status, confidence=excluded.confidence
        """, (connector_id, client_id, query_id, route,
              _json.dumps(params or {}), status, confidence, instance_name))
        conn.commit()
        binding_id = cur.lastrowid
        return {'id': binding_id, 'connector_id': connector_id, 'client_id': client_id,
                'query_id': query_id, 'route': route, 'status': status, 'confidence': confidence}
    finally:
        conn.close()

def get_bindings(connector_id: int, client_id: int,
                 status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        if status:
            cur.execute("""
                SELECT id, connector_id, client_id, query_id, route,
                       params_json, status, confidence, instance_name, created_at
                FROM connector_bindings
                WHERE connector_id=? AND client_id=? AND status=?
                ORDER BY query_id
            """, (connector_id, client_id, status))
        else:
            cur.execute("""
                SELECT id, connector_id, client_id, query_id, route,
                       params_json, status, confidence, instance_name, created_at
                FROM connector_bindings
                WHERE connector_id=? AND client_id=?
                ORDER BY query_id
            """, (connector_id, client_id))
        return [{'id': r['id'], 'connector_id': r['connector_id'], 'client_id': r['client_id'],
                 'query_id': r['query_id'], 'route': r['route'],
                 'params': _json.loads(r['params_json']),
                 'status': r['status'], 'confidence': r['confidence'],
                 'instance_name': r['instance_name'], 'created_at': r['created_at']}
                for r in cur.fetchall()]
    finally:
        conn.close()

def update_binding_status(binding_id: int, status: str) -> None:
    conn = get_db_connection()
    try:
        conn.execute("UPDATE connector_bindings SET status=? WHERE id=?", (status, binding_id))
        conn.commit()
    finally:
        conn.close()

def delete_binding(binding_id: int) -> None:
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM connector_bindings WHERE id=?", (binding_id,))
        conn.commit()
    finally:
        conn.close()

def log_connector_miss(
    connector_id: int, client_id: int, query_id: str, route: str,
    error_code: int = None, detail: str = None, is_empty: bool = False,
) -> None:
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO connector_misses
               (connector_id, client_id, query_id, route, error_code, detail, is_empty)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (connector_id, client_id, query_id, route,
             error_code, detail[:500] if detail else None, 1 if is_empty else 0),
        )
        conn.commit()
    finally:
        conn.close()

def get_connector_misses(connector_id: int, client_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        if client_id:
            rows = conn.execute(
                "SELECT * FROM connector_misses WHERE connector_id=? AND client_id=? ORDER BY created_at DESC LIMIT ?",
                (connector_id, client_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM connector_misses WHERE connector_id=? ORDER BY created_at DESC LIMIT ?",
                (connector_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def suggest_bindings_from_catalog(client_id: int, connector_id: int) -> List[Dict[str, Any]]:
    """Score catalog tables against known API routes; return best match per query_id."""
    snap = get_schema_snapshot(client_id)
    connector = get_connector(connector_id)
    if not snap or not connector:
        return []

    tables = [t['name'] for t in snap.get('tables', []) if t.get('type') == 'table']
    contract_queries = set(connector['contract'].get('queries', {}).keys())
    if not contract_queries:
        contract_queries = {'summary', 'list'}  # fallback: suggest both

    # best match per query_id
    best: Dict[str, Dict[str, Any]] = {}
    for table in tables:
        norm = _normalize_table(table)
        top_resource, top_score = None, 0.0
        for resource_key in _RESOURCE_ROUTES:
            score = _difflib.SequenceMatcher(None, norm, resource_key).ratio()
            if score > top_score:
                top_score, top_resource = score, resource_key
        if top_score < 0.45 or not top_resource:
            continue
        for route, query_id in _RESOURCE_ROUTES[top_resource]:
            if query_id not in contract_queries:
                continue
            existing = best.get(query_id)
            if not existing or top_score > existing['confidence']:
                best[query_id] = {
                    'table': table, 'query_id': query_id,
                    'route': route, 'resource': top_resource,
                    'confidence': round(top_score, 2),
                }

    return sorted(best.values(), key=lambda x: x['confidence'], reverse=True)
