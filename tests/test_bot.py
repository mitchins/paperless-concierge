#!/usr/bin/env python3
"""
Test script for the Paperless-NGX Telegram Concierge bot.
This script validates the basic functionality without requiring a full Paperless-NGX setup.
"""

import asyncio
import os
import sys
from config import TELEGRAM_BOT_TOKEN, PAPERLESS_URL, PAPERLESS_TOKEN

def test_config():
    """Test configuration validation."""
    print("🔧 Testing Configuration...")
    
    try:
        print(f"✓ TELEGRAM_BOT_TOKEN: {'Set' if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != 'your_telegram_bot_token_here' else 'Missing/Placeholder'}")
        print(f"✓ PAPERLESS_URL: {PAPERLESS_URL}")
        print(f"✓ PAPERLESS_TOKEN: {'Set' if PAPERLESS_TOKEN and PAPERLESS_TOKEN != 'your_paperless_api_token_here' else 'Missing/Placeholder'}")
        
        config_ok = True
        
        if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
            print("❌ TELEGRAM_BOT_TOKEN is required. Get one from @BotFather on Telegram.")
            config_ok = False
        if not PAPERLESS_TOKEN or PAPERLESS_TOKEN == "your_paperless_api_token_here":
            print("❌ PAPERLESS_TOKEN is required for Paperless-NGX API access.")
            config_ok = False
            
        if config_ok:
            print("✅ Configuration looks good!")
        return config_ok
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

async def test_paperless_connection():
    """Test connection to Paperless-NGX API."""
    print("\n📡 Testing Paperless-NGX Connection...")
    
    try:
        from paperless_client import PaperlessClient
        client = PaperlessClient()
        
        # Try to make a simple API call
        import aiohttp
        async with aiohttp.ClientSession() as session:
            url = f"{PAPERLESS_URL}/api/documents/"
            headers = {'Authorization': f'Token {PAPERLESS_TOKEN}'}
            
            async with session.get(url, headers=headers, params={'page_size': 1}) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Successfully connected to Paperless-NGX!")
                    print(f"   Documents in system: {data.get('count', 0)}")
                    return True
                else:
                    print(f"❌ Paperless-NGX API returned status {response.status}")
                    error_text = await response.text()
                    print(f"   Error: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Failed to connect to Paperless-NGX: {e}")
        print("   This is expected if Paperless-NGX is not running locally.")
        print("   The bot will still work once Paperless-NGX is available.")
        return False

async def test_telegram_token():
    """Test Telegram bot token validity."""
    print("\n🤖 Testing Telegram Bot Token...")
    
    if TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("⚠️  Using placeholder token - please configure a real bot token")
        return False
    
    try:
        from telegram import Bot
        
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Test the token by getting bot info
        bot_info = await bot.get_me()
        print(f"✅ Bot token is valid!")
        print(f"   Bot name: {bot_info.first_name}")
        print(f"   Bot username: @{bot_info.username}")
        return True
            
    except Exception as e:
        print(f"❌ Invalid Telegram bot token: {e}")
        return False

async def test_imports():
    """Test that all required modules can be imported."""
    print("\n📦 Testing Module Imports...")
    
    modules_to_test = [
        'telegram',
        'telegram.ext',
        'aiohttp',
        'aiofiles',
        'dotenv'
    ]
    
    for module in modules_to_test:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            return False
    
    print("✅ All modules imported successfully!")
    return True

async def run_tests():
    """Run all tests."""
    print("🧪 Starting Paperless-NGX Telegram Concierge Test Suite\n")
    
    tests = [
        ("Import Test", test_imports()),
        ("Configuration Test", test_config()),
        ("Telegram Token Test", test_telegram_token()),
        ("Paperless Connection Test", test_paperless_connection()),
    ]
    
    results = []
    
    for test_name, test_coro in tests:
        if asyncio.iscoroutine(test_coro):
            result = await test_coro
        else:
            result = test_coro
        results.append((test_name, result))
    
    print(f"\n📊 Test Results:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! The bot should work correctly.")
        print("\nTo start the bot:")
        print("1. Make sure your .env file is configured")
        print("2. Run: python bot.py")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please fix the issues above.")
        
        if not TELEGRAM_BOT_TOKEN:
            print("\n📝 To get a Telegram bot token:")
            print("1. Message @BotFather on Telegram")
            print("2. Send /newbot")
            print("3. Follow the instructions")
            print("4. Add the token to your .env file")

if __name__ == "__main__":
    asyncio.run(run_tests())