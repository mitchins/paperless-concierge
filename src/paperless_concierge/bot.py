"""
Telegram bot for Paperless-NGX document management.

SECURITY NOTE: This module uses os.kill() with signal 0 for process existence checking
in the singleton enforcement functionality. This usage is secure because:
- Signal 0 is completely harmless (existence check only, never kills)
- PIDs are validated before use (bounds checking, type validation)
- Process ownership is verified (only checks processes owned by current user)
- System processes are explicitly excluded (PID 1, negative PIDs, etc.)
"""

import argparse
import logging
import os
import tempfile
import uuid
import inspect
import asyncio
import atexit
import fcntl
from typing import Optional

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import TELEGRAM_BOT_TOKEN
from .constants import DEFAULT_SEARCH_RESULTS
from .document_tracker import DocumentTracker
from .exceptions import (
    FileDownloadError,
    PaperlessAPIError,
    PaperlessTaskNotFoundError,
    PaperlessUploadError,
    TelegramBotError,
)
from .paperless_client import PaperlessClient
from .user_manager import get_user_manager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def require_authorization(func):
    """Decorator to check if user is authorized."""

    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        user_manager = get_user_manager()

        if not user_manager.is_authorized(user_id):
            logger.warning(
                f"Unauthorized access attempt from user {user_id} (@{username})"
            )
            await update.message.reply_text(
                "🚫 Access denied. You are not authorized to use this bot.\n"
                f"Your Telegram ID: {user_id}\n\n"
                f"Current mode: {user_manager.auth_mode}"
            )
            return

        logger.info(
            f"Authorized user {user_id} (@{username}) accessing {func.__name__}"
        )
        return await func(self, update, context)

    return wrapper


class TelegramConcierge:
    def __init__(self, document_tracker=None):
        self.upload_tasks = {}
        self.document_tracker = document_tracker
        # Cache per-user PaperlessClient instances (avoid per-request sessions)
        self._clients = {}
        self._client_keys = {}

    def get_paperless_client(self, user_id: int) -> PaperlessClient:
        """Return a cached PaperlessClient for a user, creating/replacing as needed."""
        user_config = get_user_manager().get_user_config(user_id)
        if not user_config:
            raise ValueError(f"No configuration found for user {user_id}")

        key = (
            user_config.paperless_url,
            user_config.paperless_token,
            user_config.paperless_ai_url,
            user_config.paperless_ai_token,
        )

        cached = self._clients.get(user_id)
        if cached and self._client_keys.get(user_id) == key:
            return cached

        self._close_previous_client(user_id, key)

        client = PaperlessClient(
            paperless_url=user_config.paperless_url,
            paperless_token=user_config.paperless_token,
            paperless_ai_url=user_config.paperless_ai_url,
            paperless_ai_token=user_config.paperless_ai_token,
        )
        self._clients[user_id] = client
        self._client_keys[user_id] = key
        return client

    def _close_previous_client(self, user_id: int, new_key: tuple) -> None:
        old = self._clients.get(user_id)
        if not old or self._client_keys.get(user_id) == new_key:
            return
        for closer in ("aclose", "close"):
            fn = getattr(old, closer, None)
            if not callable(fn):
                continue
            try:
                res = fn()
                if inspect.isawaitable(res):
                    try:
                        asyncio.get_running_loop().create_task(res)
                    except RuntimeError:
                        # No running loop; ignore — aclose() will handle later
                        pass
            except (httpx.HTTPError, RuntimeError, OSError) as e:
                logger.warning(
                    "Failed to close previous PaperlessClient for user %s: %s",
                    user_id,
                    e,
                    exc_info=True,
                )
            break

    async def aclose(self):
        """Close all cached PaperlessClient instances."""
        for client in self._clients.values():
            for closer in ("aclose", "close"):
                fn = getattr(client, closer, None)
                if callable(fn):
                    try:
                        res = fn()
                        if inspect.isawaitable(res):
                            await res
                    except (httpx.HTTPError, RuntimeError, OSError) as e:
                        logger.debug(
                            "Error while closing PaperlessClient during aclose: %s",
                            e,
                            exc_info=True,
                        )
        self._clients.clear()
        self._client_keys.clear()

    @require_authorization
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        user_id = update.effective_user.id
        user_manager = get_user_manager()
        user_config = user_manager.get_user_config(user_id)

        welcome_text = (
            "🤖 Welcome to Paperless-NGX Telegram Concierge!\n\n"
            "I can help you:\n"
            "📄 Upload documents to Paperless-NGX\n"
            "🔍 Search and query your documents\n"
            "📱 Work directly from your phone's share sheet\n\n"
            f"✅ You are authorized (ID: {user_id})\n"
            f"🔧 Mode: {user_manager.auth_mode}\n"
        )

        if user_config and user_manager.auth_mode == "user_scoped":
            welcome_text += f"👤 Config: {user_config.name}\n"
            welcome_text += f"🏠 Paperless: {user_config.paperless_url}\n"

        welcome_text += "\nJust send me a document or photo to get started!"

        await update.message.reply_text(welcome_text)

    @require_authorization
    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Send a message when the command /help is issued."""
        help_text = (
            "🤖 Paperless-NGX Telegram Concierge Help\n\n"
            "📤 *Uploading Documents:*\n"
            "• Send any photo or document file\n"
            "• I'll upload it to Paperless-NGX automatically\n"
            "• You'll get confirmation when it's processed\n\n"
            "🔍 *Searching Documents:*\n"
            "• Use /query <your question>\n"
            "• Example: /query When did I buy that laptop?\n"
            "• Example: /query Show me my tax receipts\n\n"
            "📱 *Pro tip:* Use your phone's share sheet to send documents directly from other apps!"
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    def _get_file_info(self, message, tracking_uuid: str) -> tuple:
        """Extract file object and filename from message."""
        if message.photo:
            file_obj = message.photo[-1]  # Get the highest resolution photo
            original_filename = f"{tracking_uuid}_photo_{message.message_id}.jpg"
            return file_obj, original_filename
        elif message.document:
            file_obj = message.document
            base_name = file_obj.file_name or f"document_{message.message_id}"
            # Extract extension if present
            if "." in base_name:
                name_part, ext_part = base_name.rsplit(".", 1)
                original_filename = f"{tracking_uuid}_{name_part}.{ext_part}"
            else:
                original_filename = f"{tracking_uuid}_{base_name}"
            return file_obj, original_filename
        else:
            return None, None

    def _extract_task_id(self, result) -> Optional[str]:
        """Extract task ID from upload result."""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict) and "task_id" in result:
            return result["task_id"]
        return None

    async def _setup_tracking_and_notification(
        self,
        task_id: str,
        user_id: int,
        original_filename: str,
        status_message,
        paperless_client,
        message,
        tracking_uuid: str,
        immediate_status,
    ):
        """Set up document tracking and notification UI."""
        self.upload_tasks[user_id] = {
            "task_id": task_id,
            "filename": original_filename,
            "message_id": status_message.message_id,
            "immediate_status": immediate_status,
        }

        # Add to document tracker for async notifications
        if self.document_tracker:
            self.document_tracker.add_document(
                task_id=task_id,
                user_id=user_id,
                chat_id=message.chat_id,
                filename=original_filename,
                paperless_client=paperless_client,
                immediate_status=immediate_status,
                tracking_uuid=tracking_uuid,
            )

        # Create inline keyboard for manual status checking
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Check Status", callback_data=f"status_{task_id}"
                ),
                InlineKeyboardButton(
                    "🔔 Notify When Done", callback_data=f"notify_{task_id}"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await status_message.edit_text(
            f"✅ Upload initiated!\n"
            f"📄 File: {original_filename}\n"
            f"⏳ Processing...\n\n"
            f"🤖 I'll notify you when AI analysis is complete!",
            reply_markup=reply_markup,
        )

    async def _download_to_temp(self, file_obj, original_filename: str) -> str:
        try:
            file = await file_obj.get_file()
        except Exception as e:
            raise FileDownloadError(
                f"Failed to download file from Telegram: {e}"
            ) from e
        temp_fd, temp_file_path = tempfile.mkstemp(suffix=f"_{original_filename}")
        os.close(temp_fd)
        await file.download_to_drive(temp_file_path)
        return temp_file_path

    async def _upload_and_track(
        self,
        user_id: int,
        temp_file_path: str,
        original_filename: str,
        status_message,
        message,
        tracking_uuid: str,
    ) -> None:
        paperless_client = self.get_paperless_client(user_id)
        result = await paperless_client.upload_document(
            temp_file_path, title=original_filename
        )
        task_id = self._extract_task_id(result)

        if not task_id:
            await status_message.edit_text(
                f"✅ {original_filename} uploaded successfully!"
            )
            return

        try:
            logger.info(f"🔍 Immediately checking task status for {task_id}")
            immediate_status = await paperless_client.get_document_status(task_id)
            logger.info(f"🔍 Immediate task status: {immediate_status}")
        except (PaperlessTaskNotFoundError, PaperlessAPIError, httpx.HTTPError) as e:
            logger.warning(f"Could not get immediate task status: {e}")
            immediate_status = None

        await self._setup_tracking_and_notification(
            task_id,
            user_id,
            original_filename,
            status_message,
            paperless_client,
            message,
            tracking_uuid,
            immediate_status,
        )

    @require_authorization
    async def handle_document(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle uploaded documents and photos."""
        message = update.message
        user_id = message.from_user.id
        tracking_uuid = str(uuid.uuid4())

        file_obj, original_filename = self._get_file_info(message, tracking_uuid)
        if not file_obj:
            await message.reply_text(
                "❌ Unsupported file type. Please send a photo or document."
            )
            return

        status_message = await message.reply_text("📤 Uploading to Paperless-NGX...")
        temp_file_path = None
        try:
            temp_file_path = await self._download_to_temp(file_obj, original_filename)
            await self._upload_and_track(
                user_id,
                temp_file_path,
                original_filename,
                status_message,
                message,
                tracking_uuid,
            )
        except TelegramBotError as e:
            logger.error(f"Document handling error: {e!s}")
            await message.reply_text(f"❌ Error processing file: {e!s}")
        except (TelegramError, httpx.HTTPError, OSError) as e:
            logger.error(f"Unexpected I/O error in document handling: {e!s}")
            await message.reply_text(
                "❌ A network or file error occurred. Please try again."
            )
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    @require_authorization
    async def check_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle status check button presses."""
        query = update.callback_query
        await query.answer()

        if query.data.startswith("status_"):
            task_id = query.data.split("_", 1)[1]
            user_id = query.from_user.id

            try:
                paperless_client = self.get_paperless_client(user_id)

                try:
                    status = await paperless_client.get_document_status(task_id)
                except PaperlessTaskNotFoundError:
                    # Task not found means it was completed and cleaned up
                    await query.edit_message_text(
                        "✅ Task completed! Document should be processed.\n"
                        "🔍 Try searching for your document in Paperless-NGX or use /query to find it."
                    )
                    return
                except (PaperlessAPIError, httpx.HTTPError) as task_error:
                    # Other API errors should be reported
                    await query.edit_message_text(
                        f"❌ Error checking status: {task_error}"
                    )
                    return

                if status.get("status") == "SUCCESS":
                    await query.edit_message_text(
                        "✅ Document processed successfully!\n"
                        "📄 Ready in your Paperless-NGX instance."
                    )
                elif status.get("status") == "FAILURE":
                    error_msg = status.get("result", "Unknown error")
                    await query.edit_message_text(f"❌ Processing failed: {error_msg}")
                else:
                    # Still processing
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "🔄 Check Again", callback_data=f"status_{task_id}"
                            )
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(
                        f"⏳ Still processing...\n"
                        f"Status: {status.get('status', 'Unknown')}",
                        reply_markup=reply_markup,
                    )

            except (httpx.HTTPError, ValueError, KeyError, AttributeError) as e:
                logger.error(f"Status check error: {e!s}")
                await query.edit_message_text(f"❌ Error checking status: {e!s}")

    def _build_document_url(
        self, paperless_client: PaperlessClient, document_id: int
    ) -> str:
        """Build a document URL for the Paperless-NGX web interface."""
        return f"{paperless_client.base_url.rstrip('/')}/documents/{document_id}/"

    def _format_ai_response(
        self, ai_response: dict, paperless_client: PaperlessClient = None
    ) -> str:
        """Format AI response into readable text."""
        response_text = f"🤖 **AI Assistant:**\n{ai_response['answer']}\n"

        # Add structured information if available
        if ai_response.get("documents_found"):
            response_text += (
                f"\n📄 **Referenced Documents:** {len(ai_response['documents_found'])}\n"
            )
            for doc in ai_response["documents_found"][:3]:  # Show top 3
                doc_title = doc.get("title", doc.get("name", "Unknown"))
                doc_id = doc.get("id")
                if doc_id and paperless_client:
                    doc_url = self._build_document_url(paperless_client, doc_id)
                    response_text += f"• [{doc_title}]({doc_url})\n"
                else:
                    response_text += f"• {doc_title}\n"

        if ai_response.get("tags_found"):
            tags = ai_response["tags_found"][:5]  # Show top 5 tags
            # Convert all tags to strings (they might be integers, dicts, or strings)
            tag_strs = []
            for tag in tags:
                if isinstance(tag, dict):
                    tag_strs.append(str(tag.get("name") or tag.get("label") or tag))
                else:
                    tag_strs.append(str(tag))
            response_text += f"\n🏷️ **Related Tags:** {', '.join(tag_strs)}\n"

        if ai_response.get("confidence"):
            confidence = (
                round(float(ai_response["confidence"]) * 100)
                if isinstance(ai_response["confidence"], (int, float))
                else ai_response["confidence"]
            )
            response_text += f"\n📊 **Confidence:** {confidence}%\n"

        if ai_response.get("sources"):
            response_text += (
                f"\n📚 **Sources:** {len(ai_response['sources'])} documents\n"
            )

        response_text += "\n💡 *Based on your Paperless-NGX documents*"
        return response_text

    def _format_search_results(
        self, search_results: dict, paperless_client: PaperlessClient = None
    ) -> str:
        """Format regular search results into readable text."""
        documents = search_results["results"][:DEFAULT_SEARCH_RESULTS]
        response = f"📋 **Found {search_results['count']} documents:**\n\n"

        for doc in documents:
            title = doc.get("title", "Untitled")
            created = doc.get("created", "Unknown date")[:10]  # Just the date part
            doc_id = doc.get("id")
            tags = doc.get("tags", [])

            # Format title with link if possible
            if doc_id and paperless_client:
                doc_url = self._build_document_url(paperless_client, doc_id)
                title_with_link = f"[{title}]({doc_url})"
            else:
                title_with_link = title

            # Coerce tags to strings safely (tags may be ints or dicts)
            tag_labels = []
            for t in tags[:3]:
                if isinstance(t, dict):
                    tag_labels.append(str(t.get("name") or t.get("label") or t))
                else:
                    tag_labels.append(str(t))
            tag_text = f" [Tags: {', '.join(tag_labels)}]" if tag_labels else ""
            response += f"• {title_with_link}{tag_text}\n  📅 {created}\n\n"

        if search_results["count"] > DEFAULT_SEARCH_RESULTS:
            response += f"... and {search_results['count'] - DEFAULT_SEARCH_RESULTS} more documents.\n"

        response += "\n💡 *Try specific keywords for better results*"
        return response

    async def _handle_successful_ai_response(
        self, ai_response: dict, status_message, paperless_client: PaperlessClient
    ):
        """Handle successful AI response."""
        response_text = self._format_ai_response(ai_response, paperless_client)
        await status_message.edit_text(response_text)

    async def _handle_ai_fallback_search(
        self, paperless_client, query_text: str, status_message
    ):
        """Handle fallback to regular search when AI is unavailable."""
        await status_message.edit_text("🔍 AI unavailable, searching documents...")
        search_results = await paperless_client.search_documents(query_text)

        if search_results.get("count", 0) > 0:
            response = self._format_search_results(search_results, paperless_client)
            await status_message.edit_text(response)
        else:
            await status_message.edit_text(
                f"❌ **No documents found for:** {query_text}\n\n"
                f"💡 Try different keywords or check if documents are uploaded"
            )

    async def _handle_ai_error_with_fallback(
        self, ai_response: dict, paperless_client, query_text: str, status_message
    ):
        """Handle AI error with fallback search."""
        await status_message.edit_text(
            f"❌ **AI Query Failed:** {ai_response.get('error', 'Unknown error')}\n\n"
            f"Falling back to document search..."
        )

        # Still try regular search as fallback
        search_results = await paperless_client.search_documents(query_text)
        if search_results.get("count", 0) > 0:
            documents = search_results["results"][:3]
            response = (
                f"📋 Found {search_results['count']} documents (fallback search):\n\n"
            )
            for doc in documents:
                title = doc.get("title", "Untitled")
                doc_id = doc.get("id")
                if doc_id:
                    doc_url = self._build_document_url(paperless_client, doc_id)
                    response += f"• [{title}]({doc_url})\n"
                else:
                    response += f"• {title}\n"
            await status_message.reply_text(response)

    @require_authorization
    async def query_documents(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle document queries using AI."""
        if not context.args:
            await update.message.reply_text(
                "🔍 Please provide a search query.\n"
                "Example: /query When did I buy that laptop?"
            )
            return

        query_text = " ".join(context.args)
        user_id = update.message.from_user.id
        status_message = await update.message.reply_text(
            f"🔍 Searching for: {query_text}..."
        )

        try:
            paperless_client = self.get_paperless_client(user_id)
            ai_response = await paperless_client.query_ai(query_text)

            if ai_response.get("success", False):
                await self._handle_successful_ai_response(
                    ai_response, status_message, paperless_client
                )
            elif ai_response.get("error") in [
                "AI service not configured",
                "AI service temporarily unavailable",
            ]:
                await self._handle_ai_fallback_search(
                    paperless_client, query_text, status_message
                )
            else:
                await self._handle_ai_error_with_fallback(
                    ai_response, paperless_client, query_text, status_message
                )

        except (httpx.HTTPError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Query error: {e!s}")
            await status_message.edit_text(f"❌ Search failed: {e!s}")
        except Exception as e:  # Last-resort guard for unexpected client errors
            logger.error("Unexpected error during query: %s", e, exc_info=True)
            await status_message.edit_text(f"❌ Search failed: {e!s}")


def _is_valid_pid(pid: int) -> bool:
    """Validate PID for security - ensure it's reasonable and safe to check."""
    # PID must be positive and within reasonable bounds
    if not isinstance(pid, int) or pid <= 0:
        return False

    # PIDs shouldn't exceed system limits (typically much lower than this)
    # This prevents potential issues with extremely large values
    if pid > 2**20:  # 1 million - well above typical system limits
        return False

    # Never try to check system critical processes (PID 1 is init/systemd)
    if pid == 1:
        return False

    return True


def _is_owned_by_current_user(pid: int) -> bool:
    """Check if the process belongs to the current user for additional safety."""
    try:
        # Get process info via /proc (Linux/Unix) or fall back to basic check
        proc_path = f"/proc/{pid}"
        if os.path.exists(proc_path):
            # Check if process directory is owned by current user
            current_uid = os.getuid()
            proc_stat = os.stat(proc_path)
            return proc_stat.st_uid == current_uid
        else:
            # Fallback: assume it's safe if we can't check
            # (macOS doesn't have /proc, Windows doesn't have this path)
            return True
    except (OSError, AttributeError):
        # If we can't check ownership, err on the side of caution
        return True


def ensure_singleton():
    """Ensure only one instance of the bot is running.

    Security considerations:
    - Only checks PIDs that pass validation (positive, within reasonable bounds)
    - Only checks processes owned by the current user
    - Uses signal 0 (harmless process existence check, doesn't terminate)
    - Never attempts to signal system processes (PID 1, etc.)
    """
    lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")

    try:
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, str(os.getpid()).encode())

        def cleanup():
            try:
                os.close(lock_fd)
                os.unlink(lock_file)
            except OSError:
                pass

        atexit.register(cleanup)
        return lock_fd

    except FileExistsError:
        # Check if the existing process is still running
        try:
            with open(lock_file, "r") as f:
                pid_content = f.read().strip()

            # Parse and validate PID
            existing_pid = int(pid_content)

            # Security validation: ensure PID is safe to check
            if not _is_valid_pid(existing_pid):
                logger.warning(f"Invalid PID in lock file: {existing_pid}")
                # Remove suspicious lock file and try again
                os.unlink(lock_file)
                return ensure_singleton()

            # Additional safety: only check processes owned by current user
            if not _is_owned_by_current_user(existing_pid):
                logger.warning(
                    f"PID {existing_pid} not owned by current user, removing stale lock"
                )
                os.unlink(lock_file)
                return ensure_singleton()

            # SECURITY NOTE: This is a safe usage of os.kill() because:
            # 1. Signal 0 is completely harmless - it only checks process existence
            # 2. PID has been validated by _is_valid_pid() above (bounds checking)
            # 3. Process ownership verified by _is_owned_by_current_user() above
            # 4. Never targets system processes (PID 1, negative PIDs, etc.)
            os.kill(existing_pid, 0)  # noqa: S603,S4828  # NOSONAR
            print(f"❌ Another instance is already running (PID: {existing_pid})")
            print("   Stop it first or wait for it to exit.")
            exit(1)

        except (ValueError, ProcessLookupError, OSError):
            # Stale lock file - remove it and try again
            try:
                os.unlink(lock_file)
                return ensure_singleton()
            except OSError:
                print("❌ Cannot acquire lock - permission denied")
                exit(1)


def main() -> None:
    """Start the bot."""
    # Ensure only one instance runs
    ensure_singleton()

    parser = argparse.ArgumentParser(
        prog="paperless-concierge",
        description="Telegram bot for uploading documents and querying your Paperless-NGX instance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  paperless-concierge                    Start the bot with default settings

For configuration, set environment variables:
  TELEGRAM_BOT_TOKEN      Your bot token from @BotFather
  PAPERLESS_URL          URL of your Paperless-NGX instance
  PAPERLESS_TOKEN        API token for Paperless-NGX
  AUTH_MODE              Authentication mode (global/user-based)
  AUTHORIZED_USERS       Comma-separated list of authorized user IDs
        """.strip(),
    )

    parser.add_argument(
        "--version",
        action="version",
        version="paperless-concierge (see https://github.com/mitchins/paperless-ngx-telegram-concierge)",
    )

    # Parse arguments - this will handle --help and exit on unknown args
    parser.parse_args()

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Create document tracker
    document_tracker = DocumentTracker(application)

    # Create concierge with tracker
    concierge = TelegramConcierge(document_tracker=document_tracker)

    # Add handlers
    application.add_handler(CommandHandler("start", concierge.start))
    application.add_handler(CommandHandler("help", concierge.help_command))
    application.add_handler(CommandHandler("query", concierge.query_documents))
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, concierge.handle_document)
    )
    application.add_handler(CallbackQueryHandler(concierge.check_status))

    # Add startup and shutdown handlers for the tracker
    async def post_init(application):
        """Start document tracker after bot initialization"""
        await document_tracker.start_tracking()
        logger.info("Document tracker started")

    async def post_shutdown(application):
        """Stop document tracker on shutdown"""
        await document_tracker.stop_tracking()
        try:
            await concierge.aclose()
        finally:
            logger.info("Document tracker stopped and clients closed")

    application.post_init = post_init
    application.post_shutdown = post_shutdown

    # Run the bot
    logger.info("Starting Paperless-NGX Telegram Concierge with async notifications...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
