"""
PocketPay Telegram Bot Runner (Development Mode)
Polls the official Telegram Bot API for real-time updates.
Usage:
    python run_bot.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app.telegram.poller import run_polling

if __name__ == '__main__':
    run_polling()
