"""
Redefine (ou cria) a senha de um administrador do painel diretamente no platform.db.
Use quando a senha foi esquecida. Não exige o servidor rodando.

Uso (na raiz do projeto, com o venv ativo):
    python scripts/reset_admin_password.py            # usuário padrão: admin
    python scripts/reset_admin_password.py --user joao

A nova senha é pedida no terminal sem eco (não passa pela linha de comando nem pelo histórico).
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from passlib.context import CryptContext
from platform_db import get_db_connection, init_platform_db


def main() -> int:
    ap = argparse.ArgumentParser(description="Redefine a senha de um admin do painel")
    ap.add_argument("--user", default="admin")
    args = ap.parse_args()

    pw1 = getpass.getpass(f"Nova senha para '{args.user}': ")
    pw2 = getpass.getpass("Confirme a nova senha: ")
    if pw1 != pw2:
        print("As senhas não coincidem.", file=sys.stderr)
        return 1
    if len(pw1) < 8:
        print("Use ao menos 8 caracteres.", file=sys.stderr)
        return 1

    init_platform_db()
    pwd_hash = CryptContext(schemes=["argon2"], deprecated="auto").hash(pw1)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE admin_users SET password_hash = ? WHERE username = ?", (pwd_hash, args.user))
        if cur.rowcount == 0:
            cur.execute("INSERT INTO admin_users (username, password_hash) VALUES (?, ?)", (args.user, pwd_hash))
            print(f"Usuário '{args.user}' criado.")
        else:
            print(f"Senha de '{args.user}' redefinida.")
        conn.commit()
    finally:
        conn.close()
    print("Se o servidor estiver rodando, o lockout de login em memória zera ao reiniciá-lo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
