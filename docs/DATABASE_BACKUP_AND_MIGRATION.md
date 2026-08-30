# PocketPay — Render PostgreSQL Database Backup & Migration Guide

This guide outlines the safe procedure for creating complete, self-contained backups of your PocketPay PostgreSQL database hosted on Render, and restoring your data when migrating to a new PostgreSQL instance.

---

## Architecture & Storage Overview

```
Existing Render PostgreSQL DB
            │
      pg_dump / Python
            ▼
PocketPay/backups/pocketpay_backup_YYYY-MM-DD_HH-MM-SS.sql  (Local Secure Storage)
            │
        psql / Python
            ▼
  New Render PostgreSQL DB
            │
            ▼
Updated DATABASE_URL in Render Dashboard
```

* **Local Backup Folder**: `PocketPay/backups/`
* **File Naming Format**: `pocketpay_backup_YYYY-MM-DD_HH-MM-SS.sql`
* **Security Protection**:
  * Added to `.gitignore` so no database dumps or credentials can ever be pushed to GitHub.
  * Stored outside web-accessible public/static folders.
  * Passwords and credentials are automatically masked in log outputs.

---

## Step-by-Step Render Database Migration (Step 1 to Step 8)

When your Render Free PostgreSQL database approaches its expiration or when performing maintenance:

### Step 1: Create a Full Database Backup Locally

Run the backup script from the PocketPay project directory:

```bash
# Windows (PowerShell / CMD)
python scripts/backup_database.py
# Or using the batch wrapper:
scripts\backup_database.bat

# Linux / macOS
python3 scripts/backup_database.py
# Or using the shell wrapper:
bash scripts/backup_database.sh
```

**Output**:
The script reads `DATABASE_URL` from `.env`, runs `pg_dump` (with fallback support), and saves the file to:
`PocketPay/backups/pocketpay_backup_YYYY-MM-DD_HH-MM-SS.sql`

---

### Step 2: Keep the Backup File Safely

Copy the generated `.sql` file from `PocketPay/backups/` to a secure local folder or private encrypted storage on your computer.

> **IMPORTANT**: Do NOT rely on the temporary ephemeral filesystem of the deployed Render container as permanent storage. Always maintain your copy locally.

---

### Step 3: Create a New PostgreSQL Database on Render

1. Log into your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** $\rightarrow$ **PostgreSQL**.
3. Set a database name (e.g. `pocketpay-db-new`).
4. Select the Region matching your Web Service.
5. Click **Create Database**.
6. Once provisioned, copy the **External Database URL** (e.g., `postgresql://pocketpay_user:password@dpg-xxxx.oregon-postgres.render.com/pocketpay_db`).

---

### Step 4: Restore Data into the New Render Database

Run the restore utility pointing to the newly created Render database URL:

```bash
# Using python directly:
python scripts/restore_database.py --target-url "postgresql://pocketpay_user:password@dpg-xxxx.oregon-postgres.render.com/pocketpay_db"

# Or specifying a specific backup file:
python scripts/restore_database.py --target-url "<NEW_RENDER_POSTGRES_URL>" --backup-file "backups/pocketpay_backup_2026-08-30_143000.sql"
```

The script restores all tables, schema definitions, constraints, indexes, users, pockets, distribution rules, transactions, and notification records.

---

### Step 5: Verify Data Integrity in the Restored Database

Verify all tables, users, balances, and records using the verification utility:

```bash
python scripts/verify_database.py "<NEW_RENDER_POSTGRES_URL>"
```

Expected Output:
```text
[1] Table Verification:
    [OK]       Table 'users'
    [OK]       Table 'pockets'
    [OK]       Table 'transactions'
    [OK]       Table 'distribution_rules'
    [OK]       Table 'notifications'
    [OK]       Table 'money_requests'
    [OK]       Table 'telegram_users'

[2] Record Counts & Core Entities:
    [OK] Total Users Registered  : X
    [OK] Admin Users Found       : X
    [OK] Telegram Schema Columns : Present
    [OK] Active Pockets          : X
    [OK] Total Pocket Funds      : ₹XX,XXX.XX
    [OK] Recorded Transactions   : X
[SUCCESS] Database verification passed!
```

---

### Step 6: Update `DATABASE_URL` in Render Web Service

1. In the Render Dashboard, open your **PocketPay Web Service** (`pocketpay-1` / `pocketpay-web`).
2. Navigate to **Environment** tab.
3. Locate the `DATABASE_URL` environment variable.
4. Replace the old database connection string with the **Internal Database URL** of the new database (or External URL if using different regions).
5. Click **Save Changes**.

---

### Step 7: Redeploy PocketPay

1. Render will automatically trigger a new deployment upon saving environment variables.
2. If not triggered automatically, click **Manual Deploy** $\rightarrow$ **Deploy latest commit**.
3. Monitor the build and startup logs to confirm Gunicorn starts without errors.

---

### Step 8: Complete End-to-End Verification

Open your live deployed PocketPay application and verify:
1. **User Sign-In**: Log in with your existing credentials.
2. **Wallets & Pockets**: Check all pocket balances and budget allocations.
3. **Transaction History**: Confirm all past transfer receipts and ledger records are present.
4. **Peer Transfers & QR**: Perform a ₹1.00 test transfer with Wallet ID verification and Transaction QR receipt generation.
5. **Admin Panel**: Log into `/admin` and confirm statistics and telemetry display correctly.

---

## Security Invariants

* **No Hardcoded Secrets**: Credentials are always loaded dynamically from `DATABASE_URL`.
* **Zero Logging of Passwords**: Passwords and secrets in connection strings are always masked as `****`.
* **No Git Leaks**: Backups are explicitly excluded in `.gitignore`.
* **Safe Restores**: The restore script warns and requires explicit confirmation before executing against any database to prevent accidental production overwrite.
