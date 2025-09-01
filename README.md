# Paperless-NGX Telegram Concierge

A Telegram bot for uploading documents and querying your Paperless-NGX instance directly from Telegram.

## Features

- Document upload via Telegram with real-time processing status
- AI-powered document queries (e.g., "When did I buy that laptop?")
- Phone camera and share sheet integration
- Multi-user support with per-user configurations

## Setup

1. **Quick Setup**:
   ```bash
   python setup.py
   ```

2. **Configure**:
   ```bash
   cp .env.example .env
   # Edit .env with your tokens and URLs
   ```
   
   Required settings:
   - `TELEGRAM_BOT_TOKEN` - Get from @BotFather
   - `AUTHORIZED_USERS` - Your Telegram user ID
   - `PAPERLESS_URL` - Your Paperless-NGX instance
   - `PAPERLESS_TOKEN` - Paperless-NGX API token

3. **Get Your User ID**:
   ```bash
   python get_user_id.py
   ```

4. **Run**:
   ```bash
   python bot.py
   ```

## Usage

**Upload Documents**: Send any photo or document file to the bot

**Query Documents**: `/query When did I buy that laptop?`

**Commands**: `/start`, `/help`, `/query <question>`

## Development

```bash
make help    # See all commands
make test    # Run tests
make dev     # Development mode
```

## Requirements

- Python 3.8+
- Paperless-NGX instance with API access
- Telegram Bot Token

## License

MIT License
