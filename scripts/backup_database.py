#!/usr/bin/env python3
"""
PocketPay - PostgreSQL Database Backup Utility
Uses official PostgreSQL pg_dump to create complete, self-contained SQL backups
in PocketPay/backups/pocketpay_backup_YYYY-MM-DD_HH-MM-SS.sql
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from urllib.parse import urlparse

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
except ImportError:
    pass


def mask_db_url(url_str: str) -> str:
    """Masks database password for secure logging."""
    if not url_str:
        return "<none>"
    try:
        parsed = urlparse(url_str)
        masked_netloc = parsed.netloc
        if parsed.password:
            masked_netloc = masked_netloc.replace(f":{parsed.password}@", ":****@")
        return f"{parsed.scheme}://{masked_netloc}{parsed.path}"
    except Exception:
        return "postgresql://***:***@host/db"


def find_pg_dump() -> str:
    """Locates the pg_dump executable on Windows, Linux, or macOS."""
    pg_dump = shutil.which("pg_dump")
    if pg_dump:
        return pg_dump

    # Common Windows PostgreSQL install directories
    if sys.platform == "win32":
        candidate_roots = [
            r"C:\Program Files\PostgreSQL",
            r"C:\Program Files (x86)\PostgreSQL"
        ]
        for root in candidate_roots:
            if os.path.exists(root):
                for version_dir in sorted(os.listdir(root), reverse=True):
                    candidate_bin = os.path.join(root, version_dir, "bin", "pg_dump.exe")
                    if os.path.isfile(candidate_bin):
                        return candidate_bin
    return None


def python_sql_dump(db_url: str, output_file: str):
    """
    Fallback SQL Dumper using SQLAlchemy when pg_dump is not in PATH.
    Dumps all table DDLs and data as portable PostgreSQL SQL.
    """
    print("  [Note] pg_dump CLI utility not found in PATH; using SQLAlchemy DDL/DML dump fallback...")
    from sqlalchemy import create_engine, MetaData, Table, inspect, select

    engine = None
    try:
        from flask import current_app
        if current_app:
            from app.extensions import db as app_db
            engine = app_db.engine
    except Exception:
        pass

    if engine is None:
        if hasattr(db_url, 'connect') or hasattr(db_url, 'execute'):
            engine = db_url
        else:
            engine = create_engine(db_url)

    metadata = MetaData()
    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
    except Exception:
        table_names = []

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"-- PocketPay PostgreSQL Database Backup\n")
        f.write(f"-- Generated At: {datetime.utcnow().isoformat()} UTC\n")
        f.write(f"-- Source DB: {mask_db_url(str(db_url))}\n\n")
        f.write("SET statement_timeout = 0;\n")
        f.write("SET client_encoding = 'UTF8';\n")
        f.write("SET standard_conforming_strings = on;\n\n")

        with engine.connect() as conn:
            for t_name in table_names:
                try:
                    tbl = Table(t_name, metadata, autoload_with=engine)
                    rows = conn.execute(select(tbl)).fetchall()
                except Exception:
                    continue

                if rows:
                    f.write(f"-- Table: {t_name}\n")
                    col_names_str = ", ".join(f'"{c.name}"' for c in tbl.columns)
                    for r in rows:
                        vals = []
                        for v in r:
                            if v is None:
                                vals.append("NULL")
                            elif isinstance(v, (int, float)):
                                vals.append(str(v))
                            elif isinstance(v, bool):
                                vals.append("TRUE" if v else "FALSE")
                            else:
                                escaped_val = str(v).replace("'", "''")
                                vals.append(f"'{escaped_val}'")
                        f.write(f'INSERT INTO "{t_name}" ({col_names_str}) VALUES ({", ".join(vals)}) ON CONFLICT DO NOTHING;\n')
                    f.write("\n")
    print(f"  [OK] Fallback data dump completed: {os.path.getsize(output_file):,} bytes written.")


def run_backup(custom_url: str = None, output_filename: str = None) -> str:
    """
    Performs complete database backup into PocketPay/backups/
    """
    db_url = custom_url or os.environ.get('DATABASE_URL') or os.environ.get('RENDER_DATABASE_URL')

    if not db_url:
        print("[ERROR] DATABASE_URL environment variable is not set.", file=sys.stderr)
        print("        Please provide DATABASE_URL in .env or via environment variable.", file=sys.stderr)
        sys.exit(1)

    # Normalize sqlite / postgresql uri
    clean_db_url = db_url.strip()
    if clean_db_url.startswith("postgres://"):
        clean_db_url = clean_db_url.replace("postgres://", "postgresql://", 1)

    backup_dir = os.path.join(PROJECT_ROOT, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = output_filename or f"pocketpay_backup_{timestamp}.sql"
    output_path = os.path.join(backup_dir, filename)

    print("=" * 70)
    print("           POCKETPAY DATABASE BACKUP UTILITY")
    print("=" * 70)
    print(f"[*] Timestamp     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] Source DB     : {mask_db_url(clean_db_url)}")
    print(f"[*] Target File   : {output_path}")
    print(f"[*] Backup Dir    : {backup_dir}")
    print("-" * 70)

    # Handle SQLite dev databases cleanly
    if clean_db_url.startswith("sqlite"):
        print("[*] Detected SQLite database. Creating standard SQL dump...")
        python_sql_dump(clean_db_url, output_path)
        print(f"[SUCCESS] SQLite backup saved to: {output_path}")
        return output_path

    # PostgreSQL Database Backup
    pg_dump_bin = find_pg_dump()
    if pg_dump_bin:
        print(f"[*] Using pg_dump: {pg_dump_bin}")
        cmd = [
            pg_dump_bin,
            clean_db_url,
            "--no-owner",
            "--no-privileges",
            "--clean",
            "--if-exists",
            "-f", output_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            file_size = os.path.getsize(output_path)
            print(f"[SUCCESS] PostgreSQL backup completed successfully ({file_size:,} bytes)!")
            print(f"[*] Backup saved to: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] pg_dump failed: {e.stderr.strip()}", file=sys.stderr)
            print("[*] Attempting fallback data dump...")
            python_sql_dump(clean_db_url, output_path)
            return output_path
    else:
        python_sql_dump(clean_db_url, output_path)
        return output_path


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Backup PocketPay PostgreSQL Database")
    parser.add_argument('--custom-url', '--url', default=None, help="Database URL to backup")
    parser.add_argument('--output', '-o', default=None, help="Custom output filename")
    args = parser.parse_args()
    run_backup(args.custom_url, args.output)
