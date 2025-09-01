import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Detect mode based on what's configured
USER_CONFIG_FILE = os.getenv("USER_CONFIG_FILE")
AUTHORIZED_USERS_STR = os.getenv("AUTHORIZED_USERS")

# Mode detection
if USER_CONFIG_FILE:
    # User-scoped mode
    AUTH_MODE = "user_scoped"
    AUTHORIZED_USERS = set()  # Will be loaded from YAML
    PAPERLESS_URL = None  # Per-user
    PAPERLESS_TOKEN = None  # Per-user
    PAPERLESS_AI_URL = None  # Per-user
    PAPERLESS_AI_TOKEN = None  # Per-user
elif AUTHORIZED_USERS_STR:
    # Global mode
    AUTH_MODE = "global"
    try:
        AUTHORIZED_USERS = {
            int(user_id.strip())
            for user_id in AUTHORIZED_USERS_STR.split(",")
            if user_id.strip()
        }
    except ValueError as e:
        raise ValueError(
            "AUTHORIZED_USERS must be comma-separated integers (Telegram user IDs)"
        ) from e

    PAPERLESS_URL = os.getenv("PAPERLESS_URL")
    PAPERLESS_TOKEN = os.getenv("PAPERLESS_TOKEN")
    PAPERLESS_AI_URL = os.getenv("PAPERLESS_AI_URL")
    PAPERLESS_AI_TOKEN = os.getenv("PAPERLESS_AI_TOKEN")

    if not PAPERLESS_URL:
        raise ValueError(
            "❌ PAPERLESS_URL missing!\n\n"
            "Please add this to your .env file:\n"
            "   PAPERLESS_URL=http://your-paperless-server:8000\n\n"
            "💡 This should be the full URL to your Paperless-NGX instance"
        )
    if not PAPERLESS_TOKEN:
        raise ValueError(
            "❌ PAPERLESS_TOKEN missing!\n\n"
            "Please add this to your .env file:\n"
            "   PAPERLESS_TOKEN=your_paperless_api_token\n\n"
            "💡 Get this from Paperless-NGX Settings → API Tokens"
        )
else:
    raise ValueError(
        "❌ Configuration missing!\n\n"
        "Please create a .env file with either:\n\n"
        "📋 Global mode (single Paperless instance for all users):\n"
        "   TELEGRAM_BOT_TOKEN=your_bot_token_from_@BotFather\n"
        "   AUTHORIZED_USERS=123456789,987654321  # Your Telegram user IDs\n"
        "   PAPERLESS_URL=http://your-paperless-server:8000\n"
        "   PAPERLESS_TOKEN=your_paperless_api_token\n\n"
        "🔧 User-scoped mode (per-user configurations):\n"
        "   TELEGRAM_BOT_TOKEN=your_bot_token_from_@BotFather\n"
        "   USER_CONFIG_FILE=users.yaml\n\n"
        "💡 Run 'python setup.py' for an interactive setup wizard!"
    )

if not TELEGRAM_BOT_TOKEN:
    raise ValueError(
        "❌ TELEGRAM_BOT_TOKEN missing!\n\n"
        "Please add this to your .env file:\n"
        "   TELEGRAM_BOT_TOKEN=your_bot_token_here\n\n"
        "💡 Get a bot token from @BotFather on Telegram:\n"
        "   1. Start a chat with @BotFather\n"
        "   2. Send /newbot and follow instructions\n"
        "   3. Copy the token to your .env file\n\n"
        "🔧 Run 'python setup.py' for help!"
    )
