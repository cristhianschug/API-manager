#!/usr/bin/env python3
"""CLI: reset admin password without needing the current one."""
import getpass
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv('.env.local')

os.environ.setdefault('ADMIN_BOOTSTRAP_PASSWORD', 'placeholder')

from platform_db import get_db_connection
from passlib.context import CryptContext

pwd = CryptContext(schemes=["argon2"], deprecated="auto")

username = input("Usuário admin [admin]: ").strip() or "admin"
new_pass = getpass.getpass("Nova senha: ")
if len(new_pass) < 8:
    print("Erro: senha deve ter pelo menos 8 caracteres.")
    sys.exit(1)
confirm = getpass.getpass("Confirmar nova senha: ")
if new_pass != confirm:
    print("Erro: senhas não coincidem.")
    sys.exit(1)

conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT id FROM admin_users WHERE username = ?", (username,))
if not cur.fetchone():
    print(f"Erro: usuário '{username}' não encontrado.")
    conn.close()
    sys.exit(1)

cur.execute("UPDATE admin_users SET password_hash = ? WHERE username = ?", (pwd.hash(new_pass), username))
conn.commit()
conn.close()
print(f"Senha do usuário '{username}' alterada com sucesso.")
