"""Firebird database connection using pure-Python firebirdsql driver"""
import os
import firebirdsql
from dotenv import load_dotenv

load_dotenv('.env.local')

DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', 40051))
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

def get_db():
    """FastAPI dependency for getting a connection"""
    conn = firebirdsql.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        charset='UTF8',
    )
    try:
        yield conn
    finally:
        conn.close()

# Test connection on startup
try:
    test_conn = firebirdsql.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        charset='UTF8',
    )
    test_conn.close()
    print(f"[OK] Firebird connected ({DB_HOST}:{DB_PORT})")
except Exception as e:
    print(f"[ERR] Firebird connection failed: {type(e).__name__}: {e}")
    raise RuntimeError(f"Cannot connect to Firebird: {e}")
