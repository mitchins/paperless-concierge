# Paperless-NGX Telegram Concierge Makefile

.PHONY: setup test test-unit test-integration clean run dev help lint ruff ruff-fix bandit vulture format

# Default target
help:
	@echo "📚 Paperless-NGX Telegram Concierge Development Commands"
	@echo "========================================================="
	@echo ""
	@echo "🚀 Setup & Installation:"
	@echo "  make setup         - Run complete setup (creates venv, installs deps, creates .env)"
	@echo "  make install       - Install dependencies only"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  make test          - Run all tests"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make test-integration - Run integration tests (requires real tokens)"
	@echo "  make test-workflow - Run comprehensive workflow tests"
	@echo ""
	@echo "📊 Code Quality:"
	@echo "  make lint          - Run all quality checks (ruff, bandit, vulture)"
	@echo "  make ruff          - Run ruff linting"
	@echo "  make ruff-fix      - Run ruff with auto-fix"
	@echo "  make bandit        - Run security analysis"
	@echo "  make vulture       - Run dead code detection"
	@echo "  make format        - Format code (black + ruff fixes)"
	@echo ""
	@echo "🤖 Running:"
	@echo "  make run           - Run the bot"
	@echo "  make dev           - Run bot with auto-restart on file changes"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  make clean         - Clean cache and temp files"
	@echo "  make clean-cache   - Clean persistent state cache"
	@echo ""

setup:
	@echo "🚀 Running complete setup..."
	python setup.py

install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

test:
	@echo "🧪 Running all tests..."
	pytest tests/ -v

test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/ -v -m "unit or not integration"

test-integration:
	@echo "🧪 Running integration tests (requires .env configuration)..."
	pytest tests/ -v -m integration

test-workflow:
	@echo "🧪 Running comprehensive workflow tests..."
	python tests/test_workflow.py

run:
	@echo "🤖 Starting Paperless-NGX Telegram Concierge..."
	python bot.py

dev:
	@echo "🔧 Starting bot in development mode..."
	@echo "📝 Press Ctrl+C to stop"
	@while true; do \
		python bot.py & \
		PID=$$!; \
		inotifywait -e modify -r . --include=".*\.py$$" 2>/dev/null || true; \
		kill $$PID 2>/dev/null || true; \
		echo "🔄 Restarting..."; \
		sleep 1; \
	done

clean:
	@echo "🧹 Cleaning cache and temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true

clean-cache:
	@echo "🧹 Cleaning persistent state cache..."
	rm -rf .paperless_concierge_cache/

# For systems without inotifywait, use basic dev mode
dev-basic:
	@echo "🔧 Basic development mode (manual restart required)"
	python bot.py

# Code Quality Commands
lint: ruff bandit vulture
	@echo "✅ All quality checks completed"

ruff:
	@echo "🔍 Running ruff linting..."
	ruff check .

ruff-fix:
	@echo "🔧 Running ruff with auto-fix..."
	ruff check --fix .

bandit:
	@echo "🔒 Running security analysis with bandit..."
	bandit -r . -c pyproject.toml

vulture:
	@echo "💀 Running dead code detection with vulture..."
	vulture . --min-confidence 80

format:
	@echo "🎨 Formatting code with black and ruff..."
	black .
	ruff check --fix .
