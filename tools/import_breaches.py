"""Import breach combo lists into a SQLite FTS5 database."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def parse_line(line: str):
    line = line.strip()
    if not line or "@" not in line:
        return None, None, line

    for sep in (":", "|", ";"):
        if sep in line:
            email, password = line.split(sep, 1)
            return email.strip(), password.strip(), line

    return line, None, line


def import_file(path: Path, db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS breaches USING fts5(email, password, raw, source)"
    )
    conn.commit()

    try:
        from rich.progress import Progress
        use_rich = True
    except Exception:
        use_rich = False

    total = 0
    inserted = 0
    seen = set()

    def handle_line(line: str, source: str):
        nonlocal inserted
        email, password, raw = parse_line(line)
        if not email:
            return
        key = (email.lower(), password or "")
        if key in seen:
            return
        seen.add(key)
        conn.execute(
            "INSERT INTO breaches (email, password, raw, source) VALUES (?, ?, ?, ?)",
            (email, password, raw, source)
        )
        inserted += 1

    if use_rich:
        with Progress() as progress:
            task = progress.add_task("Importing", total=None)
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    total += 1
                    handle_line(line, path.name)
                    if total % 5000 == 0:
                        conn.commit()
                        progress.advance(task, 5000)
        conn.commit()
    else:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                total += 1
                handle_line(line, path.name)
                if total % 5000 == 0:
                    conn.commit()
                    print(f"Processed {total} lines...", file=sys.stderr)
        conn.commit()

    conn.close()
    return total, inserted


def main():
    parser = argparse.ArgumentParser(description="Import breach combo list into SQLite FTS5 database")
    parser.add_argument("input", help="Path to combo list file (txt)")
    parser.add_argument(
        "--db",
        default="data/breaches/breach_index.db",
        help="Path to output SQLite DB (default: data/breaches/breach_index.db)"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    total, inserted = import_file(input_path, db_path)
    print(f"Imported {inserted} of {total} lines into {db_path}")


if __name__ == "__main__":
    main()
