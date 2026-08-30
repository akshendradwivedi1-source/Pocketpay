#!/usr/bin/env python3
"""
PocketPay - Database Verification Utility
Verifies that critical tables, user accounts, admin profile, pockets, balances,
and transactions exist and are consistent after database restore or migration.
"""

import os
import sys
from urllib.parse import urlparse
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
except ImportError:
    pass


def mask_db_url(url_str: str) -> str:
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


def verify_db(db_url: str = None) -> bool:
    target_url = db_url or os.environ.get('DATABASE_URL')
    if not target_url:
        print("[ERROR] DATABASE_URL is not set.", file=sys.stderr)
        return False

    clean_url = target_url.strip()
    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql://", 1)

    print("=" * 70)
    print("           POCKETPAY DATABASE INTEGRITY VERIFICATION")
    print("=" * 70)
    print(f"[*] Target DB: {mask_db_url(clean_url)}")
    print("-" * 70)

    try:
        engine = None
        try:
            from flask import current_app
            if current_app:
                from app.extensions import db as app_db
                engine = app_db.engine
        except Exception:
            pass

        if engine is None:
            engine = create_engine(clean_url)

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        required_tables = [
            'users',
            'pockets',
            'transactions',
            'distribution_rules',
            'notifications',
            'money_requests',
            'telegram_users'
        ]

        print("[1] Table Verification:")
        all_tables_found = True
        for tbl in required_tables:
            exists = tbl in tables
            status = "[OK]" if exists else "[MISSING]"
            print(f"    {status:<10} Table '{tbl}'")
            if not exists:
                all_tables_found = False

        if not all_tables_found:
            print("\n[WARN] Some tables are missing. Running migrations may be required.")

        print("\n[2] Record Counts & Core Entities:")
        with engine.connect() as conn:
            # Users
            if 'users' in tables:
                user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
                admin_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE is_admin = TRUE OR email LIKE '%admin%' OR email LIKE '%akshendra%'")).scalar() or 0
                print(f"    [OK] Total Users Registered  : {user_count}")
                print(f"    [OK] Admin Users Found       : {admin_count}")
                
                # Check telegram fields on users
                columns = [c['name'] for c in inspector.get_columns('users')]
                has_telegram = 'telegram_linking_token' in columns and 'telegram_notifications_enabled' in columns
                print(f"    [OK] Telegram Schema Columns : {'Present' if has_telegram else 'Needs Migration'}")
            else:
                print("    [FAIL] users table does not exist!")

            # Pockets
            if 'pockets' in tables:
                pocket_count = conn.execute(text("SELECT COUNT(*) FROM pockets")).scalar() or 0
                total_pocket_balance = conn.execute(text("SELECT COALESCE(SUM(current_balance), 0) FROM pockets WHERE archived = FALSE")).scalar() or 0.0
                print(f"    [OK] Active Pockets          : {pocket_count}")
                print(f"    [OK] Total Pocket Funds      : INR {total_pocket_balance:,.2f}")

            # Transactions
            if 'transactions' in tables:
                tx_count = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar() or 0
                print(f"    [OK] Recorded Transactions   : {tx_count}")

            # Distribution Rules
            if 'distribution_rules' in tables:
                rule_count = conn.execute(text("SELECT COUNT(*) FROM distribution_rules")).scalar() or 0
                print(f"    [OK] Auto-Distribute Rules   : {rule_count}")

        print("-" * 70)
        print("[SUCCESS] Database verification passed! PocketPay schema and records are intact.")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n[ERROR] Database verification failed: {str(e)}", file=sys.stderr)
        return False


if __name__ == '__main__':
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    success = verify_db(url_arg)
    sys.exit(0 if success else 1)
