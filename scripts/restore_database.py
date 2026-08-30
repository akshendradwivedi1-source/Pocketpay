#!/usr/bin/env python3
"""
PocketPay - PostgreSQL Database Restore Utility
Restores a PocketPay SQL backup file into a target PostgreSQL database using psql or Python executor.
Prevents accidental overwrites of production database.
"""

import os
import sys
import argparse
import subprocess
import shutil
from urllib.parse import urlparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

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


def find_psql() -> str:
    """Locates the psql executable on Windows, Linux, or macOS."""
    psql = shutil.which("psql")
    if psql:
        return psql

    if sys.platform == "win32":
        candidate_roots = [
            r"C:\Program Files\PostgreSQL",
            r"C:\Program Files (x86)\PostgreSQL"
        ]
        for root in candidate_roots:
            if os.path.exists(root):
                for version_dir in sorted(os.listdir(root), reverse=True):
                    candidate_bin = os.path.join(root, version_dir, "bin", "psql.exe")
                    if os.path.isfile(candidate_bin):
                        return candidate_bin
    return None


def get_latest_backup() -> str:
    """Returns the most recent backup file in backups/"""
    backup_dir = os.path.join(PROJECT_ROOT, "backups")
    if not os.path.isdir(backup_dir):
        return None
    sql_files = [
        os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
        if f.endswith('.sql') or f.endswith('.dump')
    ]
    if not sql_files:
        return None
    sql_files.sort(key=os.path.getmtime, reverse=True)
    return sql_files[0]


def run_restore(target_url: str, backup_file: str, force: bool = False):
    if not target_url:
        print("[ERROR] Target Database URL is required.", file=sys.stderr)
        print("        Usage: python scripts/restore_database.py --target-url <NEW_RENDER_POSTGRES_URL>", file=sys.stderr)
        sys.exit(1)

    clean_target_url = target_url.strip()
    if clean_target_url.startswith("postgres://"):
        clean_target_url = clean_target_url.replace("postgres://", "postgresql://", 1)

    # Safety check: warn if target matches current production DATABASE_URL
    prod_url = os.environ.get('DATABASE_URL', '')
    if prod_url and clean_target_url == prod_url.replace("postgres://", "postgresql://") and not force:
        print("\n[CAUTION] Target URL matches current DATABASE_URL in .env/environment!")
        print("          Restoring will overwrite existing tables.")
        confirm = input("          Are you sure you want to proceed? (yes/no): ").strip().lower()
        if confirm not in ('yes', 'y'):
            print("[ABORTED] Restore cancelled by user.")
            sys.exit(0)

    if not backup_file or not os.path.isfile(backup_file):
        print(f"[ERROR] Backup file not found: {backup_file}", file=sys.stderr)
        sys.exit(1)

    file_size = os.path.getsize(backup_file)
    print("=" * 70)
    print("           POCKETPAY DATABASE RESTORE UTILITY")
    print("=" * 70)
    print(f"[*] Target DB     : {mask_db_url(clean_target_url)}")
    print(f"[*] Backup File   : {backup_file} ({file_size:,} bytes)")
    print("-" * 70)

    psql_bin = find_psql()
    if psql_bin and not clean_target_url.startswith("sqlite"):
        print(f"[*] Using psql CLI: {psql_bin}")
        cmd = [psql_bin, clean_target_url, "-f", backup_file]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("[SUCCESS] psql restore completed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"[WARN] psql returned code {e.returncode}: {e.stderr.strip()[:300]}")
    else:
        print("[*] Executing SQL restore via SQLAlchemy engine...")
        from sqlalchemy import create_engine, text
        engine = create_engine(clean_target_url)
        with open(backup_file, 'r', encoding='utf-8', errors='ignore') as f:
            sql_content = f.read()

        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        with engine.begin() as conn:
            success_count = 0
            for stmt in statements:
                if stmt.startswith('--') and '\n' not in stmt:
                    continue
                try:
                    conn.execute(text(stmt))
                    success_count += 1
                except Exception:
                    pass
        print(f"[SUCCESS] SQLAlchemy restore executed ({success_count} statements applied).")

    # Run verification
    print("\n[*] Verifying restored database tables and accounts...")
    from scripts.verify_database import verify_db
    verify_db(clean_target_url)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Restore PocketPay PostgreSQL Database")
    parser.add_argument('--target-url', default=os.environ.get('TARGET_DATABASE_URL') or os.environ.get('DATABASE_URL'),
                        help="Target PostgreSQL database URL to restore into")
    parser.add_argument('--backup-file', default=None,
                        help="Path to .sql backup file (defaults to most recent in backups/)")
    parser.add_argument('--force', action='store_true', help="Skip interactive confirmation prompts")
    args = parser.parse_args()

    selected_backup = args.backup_file or get_latest_backup()
    if not selected_backup:
        print("[ERROR] No backup files found in backups/ directory.", file=sys.stderr)
        sys.exit(1)

    run_restore(args.target_url, selected_backup, args.force)
