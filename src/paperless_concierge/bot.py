import argparse
import logging
import os
import tempfile
import uuid
from typing import Optional

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
    FileProcessingError,
    PaperlessAPIError,
    PaperlessTaskNotFoundError,
    PaperlessUploadError,
    TelegramBotError,
    TempFileError,
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

    def get_paperless_client(self, user_id: int) -> PaperlessClient:
        """Get a PaperlessClient configured for the specific user."""
        user_manager = get_user_manager()
        user_config = user_manager.get_user_config(user_id)

        if not user_config:
            raise ValueError(f"No configuration found for user {user_id}")

        return PaperlessClient(
            paperless_url=user_config.paperless_url,
            paperless_token=user_config.paperless_token,
            paperless_ai_url=user_config.paperless_ai_url,
            paperless_ai_token=user_config.paperless_ai_token,
        )

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

    @require_authorization
    async def handle_document(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle uploaded documents and photos."""
        message = update.message
        user_id = message.from_user.id
        tracking_uuid = str(uuid.uuid4())

        # Determine if it's a photo or document
        file_obj, original_filename = self._get_file_info(message, tracking_uuid)
        if not file_obj:
            await message.reply_text(
                "❌ Unsupported file type. Please send a photo or document."
            )
            return

        try:
            # Send initial confirmation
            status_message = await message.reply_text("📤 Uploading to Paperless-NGX...")

            # Download the file
            try:
                file = await file_obj.get_file()
            except Exception as e:
                raise FileDownloadError(f"Failed to download file from Telegram: {e}")

            # Create temporary file
            temp_fd, temp_file_path = tempfile.mkstemp(suffix=f"_{original_filename}")
            os.close(temp_fd)  # Close the file descriptor, we only need the path
            await file.download_to_drive(temp_file_path)

            # Upload to Paperless-NGX using user-specific client
            try:
                paperless_client = self.get_paperless_client(user_id)
                result = await paperless_client.upload_document(
                    temp_file_path, title=original_filename
                )

                # Extract task ID from upload result
                task_id = self._extract_task_id(result)

                if task_id:
                    # Immediately check task status to get document ID before it's cleaned up
                    try:
                        logger.info(f"🔍 Immediately checking task status for {task_id}")
                        immediate_status = await paperless_client.get_document_status(
                            task_id
                        )
                        logger.info(f"🔍 Immediate task status: {immediate_status}")
                    except (
                        PaperlessTaskNotFoundError,
                        PaperlessAPIError,
                        aiohttp.ClientError,
                    ) as e:
                        # Log warning but don't fail - task might not be ready yet
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
                else:
                    await status_message.edit_text(
                        f"✅ {original_filename} uploaded successfully!"
                    )

            except (
                PaperlessUploadError,
                PaperlessAPIError,
                aiohttp.ClientError,
                OSError,
            ) as e:
                logger.error(f"Upload error: {e!s}")
                await status_message.edit_text(f"❌ Upload failed: {e!s}")

            # Clean up temporary file
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except (
            FileDownloadError,
            FileProcessingError,
            TempFileError,
            TelegramBotError,
        ) as e:
            logger.error(f"Document handling error: {e!s}")
            await message.reply_text(f"❌ Error processing file: {e!s}")
        except Exception as e:
            # Catch any unexpected errors
            logger.error(f"Unexpected error in document handling: {e!s}")
            await message.reply_text(
                "❌ An unexpected error occurred. Please try again."
            )

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
                except (PaperlessAPIError, aiohttp.ClientError) as task_error:
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

            except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as e:
                logger.error(f"Status check error: {e!s}")
                await query.edit_message_text(f"❌ Error checking status: {e!s}")

    def _format_ai_response(self, ai_response: dict) -> str:
        """Format AI response into readable text."""
        response_text = f"🤖 **AI Assistant:**\n{ai_response['answer']}\n"

        # Add structured information if available
        if ai_response.get("documents_found"):
            response_text += (
                f"\n📄 **Referenced Documents:** {len(ai_response['documents_found'])}\n"
            )
            for doc in ai_response["documents_found"][:3]:  # Show top 3
                doc_title = doc.get("title", doc.get("name", "Unknown"))
                response_text += f"• {doc_title}\n"

        if ai_response.get("tags_found"):
            tags = ai_response["tags_found"][:5]  # Show top 5 tags
            response_text += f"\n🏷️ **Related Tags:** {', '.join(tags)}\n"

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

    def _format_search_results(self, search_results: dict) -> str:
        """Format regular search results into readable text."""
        documents = search_results["results"][:DEFAULT_SEARCH_RESULTS]
        response = f"📋 **Found {search_results['count']} documents:**\n\n"

        for doc in documents:
            title = doc.get("title", "Untitled")
            created = doc.get("created", "Unknown date")[:10]  # Just the date part
            tags = doc.get("tags", [])
            tag_text = f" [Tags: {', '.join(tags[:3])}]" if tags else ""
            response += f"• {title}{tag_text}\n  📅 {created}\n\n"

        if search_results["count"] > DEFAULT_SEARCH_RESULTS:
            response += f"... and {search_results['count'] - DEFAULT_SEARCH_RESULTS} more documents.\n"

        response += "\n💡 *Try specific keywords for better results*"
        return response

    async def _handle_successful_ai_response(self, ai_response: dict, status_message):
        """Handle successful AI response."""
        response_text = self._format_ai_response(ai_response)
        await status_message.edit_text(response_text)

    async def _handle_ai_fallback_search(
        self, paperless_client, query_text: str, status_message
    ):
        """Handle fallback to regular search when AI is unavailable."""
        await status_message.edit_text("🔍 AI unavailable, searching documents...")
        search_results = await paperless_client.search_documents(query_text)

        if search_results.get("count", 0) > 0:
            response = self._format_search_results(search_results)
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
                response += f"• {doc.get('title', 'Untitled')}\n"
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
                await self._handle_successful_ai_response(ai_response, status_message)
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

        except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Query error: {e!s}")
            await status_message.edit_text(f"❌ Search failed: {e!s}")


def main() -> None:
    """Start the bot."""
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
        version="paperless-concierge (see https://github.com/clusterzx/paperless-ngx-telegram-concierge)",
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
        logger.info("Document tracker stopped")

    application.post_init = post_init
    application.post_shutdown = post_shutdown

    # Run the bot
    logger.info("Starting Paperless-NGX Telegram Concierge with async notifications...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
