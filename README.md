# PocketPay — Smart Pocket Management & Next-Gen Payments Platform

PocketPay is a full-stack personal finance and smart budgeting platform built with Python (Flask), PostgreSQL, Vanilla CSS (Glassmorphism), PyOTP 2FA, and official Telegram Bot API integration.

---

## 🌟 Key Features

1. **Smart Pocket Budgeting**:
   - Create custom dynamic pockets (e.g. Travel, Groceries, Investments).
   - Real-time balance allocation, withdrawals, and inter-pocket money transfers.

2. **Bank Payouts & Transfers**:
   - Seamless simulated bank transfers (IMPS/NEFT/UPI) with UTR generation and receipt QR codes.

3. **Enterprise-Grade Two-Factor Authentication (TOTP 2FA)**:
   - Compatible with Google Authenticator, Microsoft Authenticator, and 1Password.
   - Server-side verification with single-use backup recovery codes.

4. **Official Telegram Chatbot (`@PocketPay_Dev_Bot`)**:
   - Interactive inline keyboards, email OTP login, balance inquiries, pocket creation, and money transfers directly inside Telegram.
   - Built on official Telegram Bot API webhooks (`POST /telegram/webhook`).

5. **Role-Protected Admin Control Center**:
   - Accessible exclusively to the configured `POCKETPAY_ADMIN_EMAIL`.
   - Real-time live database metrics, pending approval queue, user directory, transaction ledgers, and immutable audit trails (`AdminAuditLog`).

---

## 🚀 One-Click Cloud Deployment (Render)

PocketPay includes a native **`render.yaml`** Infrastructure-as-Code blueprint.

1. Fork or push this repository to your GitHub account (`https://github.com/akshendradwivedi1-source/PocketPay`).
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** $\rightarrow$ **Blueprint** and select your repository.
4. Render will automatically provision:
   - **`pocketpay-app`**: Gunicorn Python Web Service (WSGI) with auto-scaling and `/health` probes.
   - **`pocketpay-db`**: Managed PostgreSQL Database.
5. In your Render Web Service **Environment** tab, configure your secrets:
   - `POCKETPAY_ADMIN_EMAIL`
   - `TELEGRAM_BOT_TOKEN`
   - `MAIL_USERNAME` & `MAIL_PASSWORD`

---

## ⚙️ Environment Variables Reference

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `FLASK_ENV` | Application environment | `production` or `development` |
| `SECRET_KEY` | Flask session encryption key | *Auto-generated on Render* |
| `DATABASE_URL` | PostgreSQL / SQLite connection string | `postgresql://user:pass@host/db` |
| `POCKETPAY_ADMIN_EMAIL` | Authorized Admin email address | `akshendra.dwivedi1@gmail.com` |
| `TELEGRAM_BOT_TOKEN` | Bot API token from `@BotFather` | `123456789:ABCdef...` |
| `TELEGRAM_WEBHOOK_URL` | Public HTTPS Webhook endpoint | `https://your-app.onrender.com/telegram/webhook` |
| `MAIL_SERVER` | SMTP host for OTP delivery | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USE_TLS` | Enable TLS encryption | `True` |
| `MAIL_USERNAME` | SMTP account email | `your-email@gmail.com` |
| `MAIL_PASSWORD` | SMTP 16-character App Password | `xxxx xxxx xxxx xxxx` |
| `OTP_EXPIRY_MINUTES`| OTP validity duration in minutes | `5` |

---

## 🛠️ Local Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/akshendradwivedi1-source/PocketPay.git
cd PocketPay

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure local environment
cp .env.example .env

# 5. Launch the development server
python run.py
```

Open **[http://localhost:5000](http://localhost:5000)** in your browser.

---

## 🧪 Running Automated Tests

PocketPay includes a comprehensive automated test suite covering all security, auth, banking, and Telegram bot operations:

```bash
# Full User Journey & Lifecycle
python scratch/test_complete_user_journey.py

# TOTP 2FA Security Suite
python scratch/test_totp_flow.py

# Telegram Bot API Verification (20 scenarios)
python scratch/test_telegram_bot.py

# Admin Panel & Role Authorization (9 scenarios)
python scratch/test_admin_panel.py

# Production Readiness & WSGI Tests
python scratch/test_production_readiness.py
```

---

## 💾 Database Backup & Render PostgreSQL Migration

PocketPay includes tools for creating self-contained PostgreSQL database backups and migrating across Render PostgreSQL database instances without data loss:

* **Full Guide**: See [DATABASE_BACKUP_AND_MIGRATION.md](file:///c:/Users/arvin/OneDrive/Desktop/Pocketpay/docs/DATABASE_BACKUP_AND_MIGRATION.md) for step-by-step instructions.
* **Create Backup**:
  ```bash
  python scripts/backup_database.py
  # Saves to PocketPay/backups/pocketpay_backup_YYYY-MM-DD_HH-MM-SS.sql
  ```
* **Restore to New Database**:
  ```bash
  python scripts/restore_database.py --target-url "<NEW_RENDER_POSTGRESQL_URL>"
  ```
* **Verify Database Integrity**:
  ```bash
  python scripts/verify_database.py "<NEW_RENDER_POSTGRESQL_URL>"
  ```

---

## 📄 License

This project is licensed under the MIT License.
