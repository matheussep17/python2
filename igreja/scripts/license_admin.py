import argparse
import secrets
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from licensing_server.db import create_license, init_db, list_licenses, reset_device, set_expiration, update_status


def random_credential(length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def parse_expiration(days: int | None, expires_at: str | None):
    if expires_at:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    if days is None:
        return None
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def cmd_create(args):
    username = args.username or f"IGREJA-{random_credential(6)}"
    password = args.password or random_credential(12)
    expires_at = parse_expiration(args.days, args.expires_at)
    create_license(username, password, expires_at=expires_at, notes=args.notes or "")
    print(f"Licença criada com sucesso.\nLogin: {username}\nSenha: {password}\nValidade: {expires_at or 'permanente'}")


def cmd_list(_args):
    rows = list_licenses()
    if not rows:
        print("Nenhuma licença cadastrada.")
        return

    for row in rows:
        device = row["device_name"] or "sem vínculo"
        expires = row["expires_at"] or "permanente"
        print(
            f"{row['username']} | status={row['status']} | validade={expires} | "
            f"dispositivo={device} | criado={row['created_at']}"
        )


def cmd_revoke(args):
    update_status(args.username, "revoked")
    print(f"Licença {args.username} revogada.")


def cmd_activate_status(args):
    update_status(args.username, "active")
    print(f"Licença {args.username} reativada.")


def cmd_reset_device(args):
    reset_device(args.username)
    print(f"Vínculo do dispositivo removido para {args.username}.")


def cmd_extend(args):
    expires_at = parse_expiration(args.days, args.expires_at)
    set_expiration(args.username, expires_at)
    print(f"Nova validade de {args.username}: {expires_at or 'permanente'}")


def build_parser():
    parser = argparse.ArgumentParser(description="Gerenciador de licenças do app Igreja.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Cria login e senha para um novo cliente.")
    create_parser.add_argument("--username", help="Login fixo. Se omitido, gera automaticamente.")
    create_parser.add_argument("--password", help="Senha fixa. Se omitida, gera automaticamente.")
    create_parser.add_argument("--days", type=int, help="Validade em dias. Omitido = licença permanente.")
    create_parser.add_argument("--expires-at", help="Validade em ISO 8601. Ex.: 2026-12-31T23:59:59+00:00")
    create_parser.add_argument("--notes", help="Observações administrativas.")
    create_parser.set_defaults(func=cmd_create)

    list_parser = subparsers.add_parser("list", help="Lista as licenças cadastradas.")
    list_parser.set_defaults(func=cmd_list)

    revoke_parser = subparsers.add_parser("revoke", help="Bloqueia uma licença.")
    revoke_parser.add_argument("username")
    revoke_parser.set_defaults(func=cmd_revoke)

    activate_parser = subparsers.add_parser("reactivate", help="Reativa uma licença bloqueada.")
    activate_parser.add_argument("username")
    activate_parser.set_defaults(func=cmd_activate_status)

    reset_parser = subparsers.add_parser("reset-device", help="Libera a licença para outro computador.")
    reset_parser.add_argument("username")
    reset_parser.set_defaults(func=cmd_reset_device)

    extend_parser = subparsers.add_parser("extend", help="Define ou altera a validade da licença.")
    extend_parser.add_argument("username")
    extend_parser.add_argument("--days", type=int, help="Quantidade de dias a partir de agora.")
    extend_parser.add_argument("--expires-at", help="Validade em ISO 8601. Omitido com ambos vazios = permanente.")
    extend_parser.set_defaults(func=cmd_extend)

    return parser


def main():
    init_db()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
