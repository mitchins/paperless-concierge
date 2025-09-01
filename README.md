# Paperless-NGX Telegram Concierge 🤖📄

A Telegram bot that serves as a concierge for your Paperless-NGX instance, enabling easy document uploads and intelligent queries directly from Telegram.

## Features

### MVP Features ✅
- **📤 Document Upload**: Upload documents via Telegram with phone share sheet integration
- **✅ Upload Confirmation**: Get real-time confirmation when documents are processed
- **📱 Mobile-Friendly**: Works seamlessly with phone camera and share sheet

### Stage Two Features ✅
- **🔍 Intelligent Queries**: Ask questions like "When did I buy that laptop?" or "Show me my tax receipts"
- **🤖 AI Integration**: Leverages Paperless-AI for intelligent document search and answers
- **📋 Fallback Search**: Falls back to regular document search if AI is unavailable

## Quick Start

### Automated Setup
```bash
python setup.py
```

### Manual Setup

1. **Create Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Choose Your Configuration Mode**:

   **👍 RECOMMENDED: Simple Global Mode** (most users)
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and uncomment MODE 1 section:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token (get from @BotFather)
   - `AUTHORIZED_USERS`: Comma-separated Telegram user IDs  
   - `PAPERLESS_URL`: Your Paperless-NGX instance URL
   - `PAPERLESS_TOKEN`: Your Paperless-NGX API token
   - `PAPERLESS_AI_URL`: (Optional) Your Paperless-AI instance URL
   - `PAPERLESS_AI_TOKEN`: (Optional) Your Paperless-AI API token

   **🔧 ADVANCED: User-Scoped Mode** (multi-tenant)
   ```bash
   cp .env.example .env
   cp users.yml.example users.yml
   ```
   - Edit `.env`: uncomment `USER_CONFIG_FILE=users.yml` (MODE 2)
   - Edit `users.yml` with per-user configurations
   - Each user gets their own Paperless instance

4. **Get Your Telegram User ID** (for authorization):
   ```bash
   python get_user_id.py
   ```
   Send any message to the bot, copy your User ID, and add it to `.env`

5. **Test Configuration**:
   ```bash
   python test_bot.py        # Test with real tokens
   python test_with_mock.py  # Test bot logic without external deps
   ```

5. **Run the Bot**:
   ```bash
   python bot.py
   # Or use the quick start script: ./start.sh
   ```

## Usage

### Document Upload
- Send any photo or document file to the bot
- Works with phone camera and share sheet
- Get real-time upload and processing status
- Automatic confirmation when document is ready

### Document Queries
Use `/query` followed by your question:
- `/query When did I buy that laptop?`
- `/query Show me my tax receipts`
- `/query Find invoices from last month`

### Commands
- `/start` - Welcome message and overview
- `/help` - Detailed help and usage instructions
- `/query <question>` - Search and query your documents

## Architecture

- **bot.py**: Main Telegram bot implementation
- **paperless_client.py**: Paperless-NGX and Paperless-AI API client
- **config.py**: Configuration and environment variable handling

## Requirements

- Python 3.8+
- Paperless-NGX instance with API access
- Telegram Bot Token
- (Optional) Paperless-AI for intelligent queries

## Development

The bot is built with:
- `python-telegram-bot` for Telegram integration
- `aiohttp` for async HTTP requests
- `python-dotenv` for environment management

## License

MIT License# paperless-concierge
