#!/usr/bin/env python3
"""
Utility script to help find your Telegram user ID.
Run this temporarily to get your user ID, then add it to AUTHORIZED_USERS.
"""

import logging

# ruff: noqa: T201
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the user's Telegram ID."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    first_name = update.effective_user.first_name or "Unknown"

    message = (
        f"📋 Your Telegram Information:\n\n"
        f"🆔 User ID: {user_id}\n"
        f"👤 Username: @{username}\n"
        f"📝 First Name: {first_name}\n\n"
        f"Add this User ID to your AUTHORIZED_USERS in .env:\n"
        f"AUTHORIZED_USERS={user_id}\n\n"
        f"⚠️ Remember to restart the bot after updating .env"
    )

    await update.message.reply_text(message)
    logger.info(f"User ID request from {user_id} (@{username})")


def main():
    """Run the user ID bot."""
    print("🤖 Starting Telegram User ID Helper Bot...")
    print("Send any message to get your user ID")
    print("Press Ctrl+C to stop")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers for any message type
    application.add_handler(CommandHandler("start", get_my_id))
    application.add_handler(MessageHandler(filters.ALL, get_my_id))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
