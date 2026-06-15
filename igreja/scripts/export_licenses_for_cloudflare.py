import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta o SQLite de licencas para o Cloudflare D1.")
    parser.add_argument("database", type=Path, help="Caminho para licenses.db")
    parser.add_argument("-o", "--output", type=Path, default=Path("licenses-backup.json"))
    args = parser.parse_args()

    database = args.database.resolve()
    if not database.is_file():
        raise SystemExit(f"Banco nao encontrado: {database}")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("SELECT * FROM licenses ORDER BY id").fetchall()
    finally:
        connection.close()

    payload = {"version": 1, "licenses": [dict(row) for row in rows]}
    args.output.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"{len(rows)} licencas exportadas para {args.output.resolve()}")


if __name__ == "__main__":
    main()
