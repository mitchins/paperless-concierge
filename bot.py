#!/usr/bin/env python3
"""Entry point for running the bot directly."""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from paperless_concierge.bot import main

if __name__ == "__main__":
    main()
