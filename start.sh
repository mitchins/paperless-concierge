#!/bin/bash

# Quick start script for Paperless-NGX Telegram Concierge

echo "🚀 Starting Paperless-NGX Telegram Concierge..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup first:"
    echo "   python setup.py"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please configure your environment:"
    echo "   cp .env.example .env"
    echo "   # Then edit .env with your actual tokens"
    exit 1
fi

# Activate virtual environment and start bot
echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "🧪 Running quick tests..."
python test_with_mock.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🤖 Starting Telegram bot..."
    python bot.py
else
    echo "❌ Tests failed. Please check your configuration."
    exit 1
fi
