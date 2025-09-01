import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Detect mode based on what's configured
USER_CONFIG_FILE = os.getenv('USER_CONFIG_FILE')
AUTHORIZED_USERS_STR = os.getenv('AUTHORIZED_USERS')

# Mode detection
if USER_CONFIG_FILE:
    # User-scoped mode
    AUTH_MODE = 'user_scoped'
    AUTHORIZED_USERS = set()  # Will be loaded from YAML
    PAPERLESS_URL = None      # Per-user
    PAPERLESS_TOKEN = None    # Per-user
    PAPERLESS_AI_URL = None   # Per-user
    PAPERLESS_AI_TOKEN = None # Per-user
elif AUTHORIZED_USERS_STR:
    # Global mode
    AUTH_MODE = 'global'
    try:
        AUTHORIZED_USERS = {int(user_id.strip()) for user_id in AUTHORIZED_USERS_STR.split(',') if user_id.strip()}
    except ValueError:
        raise ValueError("AUTHORIZED_USERS must be comma-separated integers (Telegram user IDs)")
    
    PAPERLESS_URL = os.getenv('PAPERLESS_URL')
    PAPERLESS_TOKEN = os.getenv('PAPERLESS_TOKEN')
    PAPERLESS_AI_URL = os.getenv('PAPERLESS_AI_URL')
    PAPERLESS_AI_TOKEN = os.getenv('PAPERLESS_AI_TOKEN')
    
    if not PAPERLESS_URL:
        raise ValueError("PAPERLESS_URL is required in global mode")
    if not PAPERLESS_TOKEN:
        raise ValueError("PAPERLESS_TOKEN is required in global mode")
else:
    raise ValueError("Either AUTHORIZED_USERS (global mode) or USER_CONFIG_FILE (user-scoped mode) must be set")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")