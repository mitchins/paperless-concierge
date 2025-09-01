#!/usr/bin/env python3
"""
Setup script for Paperless-NGX Telegram Concierge
"""

import os
import subprocess
import sys

# ruff: noqa: T201


def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version < (3, 8):
        print("❌ Python 3.8+ is required. Current version:", sys.version)
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True


def setup_virtual_environment():
    """Create and set up virtual environment."""
    print("\n🔧 Setting up virtual environment...")

    venv_path = "venv"

    if os.path.exists(venv_path):
        print("✅ Virtual environment already exists")
        return True

    try:
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False


def install_dependencies():
    """Install required dependencies."""
    print("\n📦 Installing dependencies...")

    if os.name == "nt":  # Windows
        pip_path = os.path.join("venv", "Scripts", "pip")
    else:  # Unix/Linux/macOS
        pip_path = os.path.join("venv", "bin", "pip")

    try:
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def setup_environment_file():
    """Set up the .env file."""
    print("\n⚙️  Setting up environment file...")

    if os.path.exists(".env"):
        print("✅ .env file already exists")
        return True

    try:
        with open(".env.example") as example:
            content = example.read()

        with open(".env", "w") as env_file:
            env_file.write(content)

        print("✅ .env file created from template")
        print("📝 Please edit .env file with your actual tokens and URLs")
        return True
    except (OSError, ValueError) as e:
        print(f"❌ Failed to create .env file: {e}")
        return False


def print_next_steps():
    """Print setup completion and next steps."""
    print("\n" + "=" * 60)
    print("🎉 SETUP COMPLETE!")
    print("=" * 60)

    print("\n📋 Next steps:")
    print("1. Edit the .env file with your actual values:")
    print("   - Get a Telegram bot token from @BotFather")
    print("   - Configure your Paperless-NGX URL and API token")
    print("   - Optionally configure Paperless-AI integration")
    print()
    print("2. Test the configuration:")
    if os.name == "nt":  # Windows
        print("   venv\\Scripts\\python test_bot.py")
    else:  # Unix/Linux/macOS
        print("   source venv/bin/activate && python test_bot.py")
    print()
    print("3. Run the bot:")
    if os.name == "nt":  # Windows
        print("   venv\\Scripts\\python bot.py")
    else:  # Unix/Linux/macOS
        print("   source venv/bin/activate && python bot.py")

    print("\n🤖 Telegram Bot Setup:")
    print("• Message @BotFather on Telegram")
    print("• Send /newbot")
    print("• Choose a name and username for your bot")
    print("• Copy the token to your .env file")


def main():
    """Run the setup process."""
    print("🚀 Paperless-NGX Telegram Concierge Setup")
    print("=" * 50)

    steps = [
        ("Python Version Check", check_python_version),
        ("Virtual Environment", setup_virtual_environment),
        ("Dependencies", install_dependencies),
        ("Environment File", setup_environment_file),
    ]

    for step_name, step_func in steps:
        print(f"\n🔄 {step_name}...")
        if not step_func():
            print(f"\n❌ Setup failed at: {step_name}")
            sys.exit(1)

    print_next_steps()


if __name__ == "__main__":
    main()
