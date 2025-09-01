import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Set

import yaml

from config import PAPERLESS_AI_TOKEN, PAPERLESS_AI_URL, PAPERLESS_TOKEN, PAPERLESS_URL

logger = logging.getLogger(__name__)


@dataclass
class UserConfig:
    """Configuration for a specific user."""

    user_id: int
    name: str
    username: Optional[str]
    paperless_url: str
    paperless_token: str
    paperless_ai_url: Optional[str] = None
    paperless_ai_token: Optional[str] = None


class UserManager:
    """Manages user authorization and per-user configurations."""

    def __init__(
        self, auth_mode: Optional[str] = None, users_file: Optional[str] = None
    ):
        from config import AUTH_MODE, USER_CONFIG_FILE

        self.auth_mode = auth_mode or AUTH_MODE
        self.users_file = users_file or USER_CONFIG_FILE or "users.yml"
        self.users: Dict[int, UserConfig] = {}
        self.authorized_users: Set[int] = set()

        if self.auth_mode == "user_scoped":
            self._load_users_from_file()
        else:
            self._load_global_users()

    def _load_global_users(self):
        """Load users from environment variable (global mode)."""
        from config import AUTHORIZED_USERS

        self.authorized_users = AUTHORIZED_USERS
        logger.info(f"Global mode: {len(self.authorized_users)} authorized users")

    def _load_users_from_file(self):
        """Load users from YAML file (user_scoped mode)."""
        if not os.path.exists(self.users_file):
            logger.warning(
                f"Users file {self.users_file} not found. No users authorized."
            )
            return

        try:
            with open(self.users_file) as f:
                config = yaml.safe_load(f)

            if not config or "users" not in config:
                logger.warning("No users section found in users.yml")
                return

            for user_id_str, user_data in config["users"].items():
                user_id = int(user_id_str)

                # Validate required fields
                if "paperless" not in user_data:
                    logger.error(f"User {user_id} missing paperless configuration")
                    continue

                paperless = user_data["paperless"]
                if "url" not in paperless or "token" not in paperless:
                    logger.error(f"User {user_id} missing paperless url/token")
                    continue

                # Extract paperless-ai config if present
                paperless_ai = user_data.get("paperless_ai", {})

                user_config = UserConfig(
                    user_id=user_id,
                    name=user_data.get("name", "Unknown"),
                    username=user_data.get("username"),
                    paperless_url=paperless["url"],
                    paperless_token=paperless["token"],
                    paperless_ai_url=paperless_ai.get("url"),
                    paperless_ai_token=paperless_ai.get("token"),
                )

                self.users[user_id] = user_config
                self.authorized_users.add(user_id)

            logger.info(
                f"User-scoped mode: {len(self.users)} users loaded from {self.users_file}"
            )

        except Exception as e:
            logger.error(f"Error loading users file: {e}")
            raise

    def is_authorized(self, user_id: int) -> bool:
        """Check if a user is authorized."""
        return user_id in self.authorized_users

    def get_user_config(self, user_id: int) -> Optional[UserConfig]:
        """Get configuration for a specific user."""
        if self.auth_mode == "user_scoped":
            return self.users.get(user_id)
        else:
            # Global mode: return global config for all authorized users
            if user_id in self.authorized_users:
                return UserConfig(
                    user_id=user_id,
                    name="Global User",
                    username=None,
                    paperless_url=PAPERLESS_URL,
                    paperless_token=PAPERLESS_TOKEN,
                    paperless_ai_url=PAPERLESS_AI_URL,
                    paperless_ai_token=PAPERLESS_AI_TOKEN,
                )
            return None

    def get_authorized_users(self) -> Set[int]:
        """Get set of authorized user IDs."""
        return self.authorized_users.copy()

    def reload(self):
        """Reload user configurations."""
        self.users.clear()
        self.authorized_users.clear()

        if self.auth_mode == "user_scoped":
            self._load_users_from_file()
        else:
            self._load_global_users()

        logger.info(f"User configurations reloaded. Mode: {self.auth_mode}")


def get_user_manager() -> UserManager:
    """Get the global user manager instance."""
    if not hasattr(get_user_manager, "_instance"):
        auth_mode = os.getenv("AUTH_MODE", "global")
        get_user_manager._instance = UserManager(auth_mode=auth_mode)
    return get_user_manager._instance
