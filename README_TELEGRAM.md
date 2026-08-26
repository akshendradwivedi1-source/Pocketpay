# PocketPay Telegram Bot Development Setup

Integrate your PocketPay Flask application with a personal Telegram chatbot using the official **Telegram Bot API**.

---

## 1. Prerequisites & Dependencies

Dependencies are managed in `requirements.txt`. To ensure everything is installed in your virtual environment:

```bash
# Activate your virtual environment
.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate  # macOS/Linux

# Install requirements
pip install -r requirements.txt
```

---

## 2. Environment Configuration (`.env`)

1. Open your local `.env` file in the root directory (do not commit this file; it is already ignored in `.gitignore`).
2. Add your Bot Token obtained from **@BotFather** on Telegram:

```env
# Telegram Bot API Configuration
TELEGRAM_BOT_TOKEN=your_actual_bot_token_from_botfather
```

*(Optional: If deploying to a public HTTPS server or using a webhook tunnel, you can also specify `TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook`)*

---

## 3. Starting the Application

### Option A: Local Development Mode (Recommended — Zero-Config Polling)
You do **NOT** need any public webhook URL, SSL certificate, or tunnel service for local development.

1. **Terminal 1** — Start the PocketPay Flask Server:
   ```bash
   python run.py
   ```
   *(Server starts at `http://localhost:5000`)*

2. **Terminal 2** — Start the Telegram Bot Poller:
   ```bash
   python run_bot.py
   ```
   *(The poller connects to Telegram's long-polling stream and processes updates in real time using your PocketPay database).*

---

### Option B: Webhook Mode (Production / HTTPS)
If you deploy your app with HTTPS or use a development tunnel (e.g. ngrok):

1. Expose port 5000:
   ```bash
   ngrok http 5000
   ```
2. Set the webhook in Telegram:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<your-subdomain>.ngrok-free.app/telegram/webhook
   ```
3. Inbound updates will be received directly by Flask at `POST /telegram/webhook`.

---

## 4. How to Open and Test the Telegram Bot

1. Open Telegram on your phone or desktop.
2. Search for your bot username (created in @BotFather) or tap the bot link: `https://t.me/YourBotUsername`.
3. Tap **Start** (or send `/start`).

---

## 5. Telegram User Journey & Commands

### 🏦 Unauthenticated Menu
- `/start` — Displays the welcome screen with interactive buttons:
  - **[🔐 Login]**: Initiates phone/email login flow.
  - **[📝 Create Account]**: Guides you to the web registration portal.
  - **[ℹ️ Help & Guide]**: Explains commands and security.

### 🔐 Login Flow
1. Tap **[🔐 Login]**.
2. Enter your registered PocketPay phone number or email (e.g. `+919876543210` or `demo@pocketpay.app`).
3. PocketPay sends a 6-digit OTP to your registered email/phone.
4. Enter the 6-digit OTP in Telegram.
5. **Logged in!** Your unique Telegram account is now securely bound to your PocketPay user profile.

### 💰 Authenticated Menu Features
- **[💰 Balance]**: Real-time available wallet balance, smart pockets total, and net worth from the database.
- **[🗂️ My Pockets]**: Lists all your smart pockets with their real balances and budget tracking.
- **[➕ Create Pocket]**: Interactive multi-step flow to name a pocket, allocate initial balance from available funds, and confirm creation.
- **[💸 Transfer]**: Guided flow to transfer money between Available Balance and Pockets with instant balance recalculation and transaction receipt logging.
- **[📜 Transactions]**: Displays your 8 most recent transactions with status, category, and timestamps.
- **[🏦 Bank Account]**: View linked sandbox bank accounts and virtual UPI ID (`alice@pocketpay`).
- **[⚙️ Account]**: Profile details, 2FA status, transaction PIN status.
- **[🗑️ Delete Account]**: Enforces the ₹0.00 balance rule (blocks deletion if funds exist) and permanently removes account upon explicit confirmation.
- **[🚪 Logout]**: Safely unlinks your Telegram session.

---

## 6. Automated Testing

To run the complete 20-phase automated test suite:

```bash
python scratch/test_telegram_bot.py
```
