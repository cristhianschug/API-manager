"""Platform database (SQLite) for multi-tenant state: clients, API keys, admins, request logs"""
import sqlite3
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PLATFORM_DB_PATH = Path(__file__).parent / "platform.db"

def get_db_connection():
    """Get a SQLite connection to platform.db with WAL mode enabled"""
    conn = sqlite3.connect(str(PLATFORM_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_platform_db():
    """Initialize platform.db schema if not exists"""
    conn = get_db_connection()
    cur = conn.cursor()

    # admin_users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # clients
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # client_credentials
    cur.execute("""
        CREATE TABLE IF NOT EXISTS client_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL UNIQUE,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            database_path TEXT NOT NULL,
            db_user TEXT NOT NULL,
            db_password_encrypted TEXT NOT NULL,
            charset TEXT DEFAULT 'UTF8',
            last_tested_at TIMESTAMP,
            last_test_ok INTEGER DEFAULT 0,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    """)

    # api_keys
    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            revoked_at TIMESTAMP,
            last_used_at TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    """)

    # api_key_scopes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_key_scopes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_id INTEGER NOT NULL,
            resource TEXT NOT NULL,
            can_read INTEGER DEFAULT 1,
            can_write INTEGER DEFAULT 0,
            FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE,
            UNIQUE(api_key_id, resource)
        )
    """)

    # request_logs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_id INTEGER,
            client_id INTEGER,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE SET NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
        )
    """)

    # Create indexes for common queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_client ON api_keys(client_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_key ON request_logs(api_key_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_client ON request_logs(client_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_created ON request_logs(created_at)")

    conn.commit()

    # Seed admin user if table is empty
    cur.execute("SELECT COUNT(*) as cnt FROM admin_users")
    if cur.fetchone()['cnt'] == 0:
        _seed_admin_user(conn)

    conn.close()

def _seed_admin_user(conn: sqlite3.Connection):
    """Seed initial admin user from environment variables"""
    from passlib.context import CryptContext

    username = os.getenv('ADMIN_BOOTSTRAP_USER', 'admin')
    password = os.environ["ADMIN_BOOTSTRAP_PASSWORD"]

    pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
    password_hash = pwd_context.hash(password)

    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        logger.info("Admin user '%s' seeded in platform.db", username)
    except sqlite3.IntegrityError:
        pass
    finally:
        cur.close()

if __name__ == "__main__":
    init_platform_db()
    logger.info("Platform database initialized at %s", PLATFORM_DB_PATH)
