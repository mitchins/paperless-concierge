"""
Document processing tracker for async notifications
"""

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp
import diskcache as dc

from constants import (
    AI_PROCESSING_TIMEOUT,
    AI_TRIGGER_MAX_RETRIES,
    CACHE_EXPIRE_TIME,
    CONSUMPTION_TIMEOUT,
    CONTENT_PREVIEW_LENGTH,
    CONTENT_PREVIEW_TRUNCATE_LENGTH,
    HTTP_NOT_FOUND,
    HTTP_OK,
    HTTPStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class TrackedDocument:
    """Represents a document being tracked for processing completion"""

    task_id: str
    user_id: int
    chat_id: int
    filename: str
    upload_time: datetime
    paperless_client: Any  # PaperlessClient instance
    status: str = "processing"
    document_id: Optional[int] = None
    ai_processed: bool = False
    retry_count: int = 0
    max_retries: int = 30  # 30 retries = ~5 minutes with 10 second intervals
    ai_analysis: Optional[Dict] = None
    tracking_uuid: Optional[str] = None  # Our definitive UUID for matching


class DocumentTracker:
    """Tracks uploaded documents and provides notifications when processing completes"""

    def __init__(self, bot_application):
        self.bot = bot_application
        self.tracked_documents: Dict[str, TrackedDocument] = {}
        self.check_interval = 1  # 1 second for aggressive consumption polling
        self.ai_check_delay = (
            5  # seconds to wait after Paperless processing before checking AI
        )
        self.background_task = None

        # Initialize persistent cache for state recovery
        self.cache = dc.Cache(".paperless_concierge_cache")
        self._restore_state()

    async def start_tracking(self):
        """Start the background tracking task"""
        # Clear any old tracking records to avoid confusion
        old_count = len(self.tracked_documents)
        if old_count > 0:
            logger.info(f"Clearing {old_count} old tracking records")
            self.tracked_documents.clear()

        if not self.background_task or self.background_task.done():
            self.background_task = asyncio.create_task(self._tracking_loop())
            logger.info("Document tracking started with clean state")

    async def stop_tracking(self):
        """Stop the background tracking task"""
        if self.background_task and not self.background_task.done():
            self.background_task.cancel()
            logger.info("Document tracking stopped")

    def _save_state(self):
        """Save current tracking state to persistent cache"""
        try:
            # Convert documents to serializable format
            state_data = {}
            for task_id, doc in self.tracked_documents.items():
                # Don't serialize the paperless_client object
                doc_dict = asdict(doc)
                doc_dict.pop("paperless_client", None)
                doc_dict["upload_time"] = doc.upload_time.isoformat()
                state_data[task_id] = doc_dict

            self.cache.set("tracked_documents", state_data, expire=CACHE_EXPIRE_TIME)
            logger.debug(f"Saved state for {len(state_data)} documents")
        except (OSError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to save state: {e}")

    def _restore_state(self):
        """Restore tracking state from persistent cache"""
        try:
            state_data = self.cache.get("tracked_documents", {})
            if state_data:
                logger.info(
                    f"Restoring state for {len(state_data)} documents from cache"
                )
                # Note: We can't fully restore without recreating paperless_client objects
                # This is mainly for recovery awareness and cleanup
                for task_id, doc_dict in state_data.items():
                    logger.info(
                        f"Found cached document: {task_id} - {doc_dict.get('filename', 'unknown')}"
                    )

                # Clean up old entries (older than 24 hours)
                current_time = datetime.now()
                old_entries = []
                for task_id, doc_dict in state_data.items():
                    try:
                        upload_time = datetime.fromisoformat(doc_dict["upload_time"])
                        if (
                            current_time - upload_time
                        ).total_seconds() > CACHE_EXPIRE_TIME:
                            old_entries.append(task_id)
                    except (ValueError, TypeError, AttributeError):
                        old_entries.append(task_id)  # Remove malformed entries

                for task_id in old_entries:
                    del state_data[task_id]

                if old_entries:
                    self.cache.set(
                        "tracked_documents", state_data, expire=CACHE_EXPIRE_TIME
                    )
                    logger.info(f"Cleaned up {len(old_entries)} old cache entries")

        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Failed to restore state: {e}")

    def add_document(
        self,
        task_id: str,
        user_id: int,
        chat_id: int,
        filename: str,
        paperless_client: Any,
        immediate_status: Optional[dict] = None,
        tracking_uuid: Optional[str] = None,
    ):
        """Add a document to tracking"""
        doc = TrackedDocument(
            task_id=task_id,
            user_id=user_id,
            chat_id=chat_id,
            filename=filename,
            upload_time=datetime.now(),
            paperless_client=paperless_client,
            tracking_uuid=tracking_uuid,
        )

        # If we got immediate status with document ID, use it
        if immediate_status and immediate_status.get("status") == "SUCCESS":
            doc_id = immediate_status.get("document_id") or immediate_status.get(
                "result", {}
            ).get("document_id")
            if doc_id:
                doc.document_id = doc_id
                doc.status = "paperless_indexing"
                logger.info(f"🔍 Got document ID immediately: {doc_id} for {filename}")

        self.tracked_documents[task_id] = doc
        self._save_state()  # Persist state after adding document
        logger.info(
            f"Tracking document: {filename} (task_id: {task_id}, doc_id: {doc.document_id})"
        )

    async def _handle_completed_state(self, task_id: str) -> bool:
        """Handle completed state - mark for cleanup"""
        return True  # Add to completed_tasks

    async def _handle_timeout_check(self, doc) -> bool:
        """Handle global timeout check"""
        if doc.retry_count >= doc.max_retries:
            await self._send_timeout_notification(doc)
            return True  # Add to completed_tasks
        return False

    async def _handle_processing_state(self, task_id: str, doc) -> bool:
        """Handle processing state - wait for task completion"""
        try:
            await doc.paperless_client.get_document_status(task_id)
            # Still processing - increment and continue
            doc.retry_count += 1
            return False
        except (aiohttp.ClientError, ValueError, KeyError) as e:
            if "Not found" in str(e):
                # Task completed, move to next state
                doc.status = "waiting_for_consumption"
                logger.info("✅ Task completed, polling for document consumption")
                doc.retry_count = 0  # Reset counter for new phase
            return False

    async def _handle_waiting_for_consumption_state(self, task_id: str, doc) -> bool:
        """Handle waiting for consumption state"""
        if doc.tracking_uuid:
            doc_id = await self._find_document_by_uuid(
                doc.paperless_client, doc.tracking_uuid
            )
        else:
            doc_id = await self._find_recent_document_by_filename(
                doc.paperless_client, doc.filename, doc.upload_time
            )

        if doc_id:
            doc.document_id = doc_id
            doc.status = "paperless_indexing"
            doc.retry_count = 0  # Reset for new phase
            logger.info(f"🔍 FOUND: Document {doc_id} consumed, checking indexing...")
            return False
        else:
            doc.retry_count += 1
            if doc.retry_count >= CONSUMPTION_TIMEOUT:
                logger.error("❌ TIMEOUT: Document never consumed after 60s")
                await self._send_basic_success_notification(doc)
                return True  # Add to completed_tasks
            return False

    async def _handle_paperless_indexing_state(self, doc) -> bool:
        """Handle paperless indexing state"""
        if await self._is_document_ready(doc):
            doc.status = "triggering_ai"
            doc.retry_count = 0  # Reset for AI phase
            logger.info(
                f"📋 INDEXED: Document {doc.document_id} ready, triggering AI..."
            )
        else:
            doc.retry_count += 1
        return False

    async def _handle_triggering_ai_state(self, doc) -> bool:
        """Handle triggering AI state"""
        if doc.paperless_client.ai_url:
            logger.info(f"🤖 TRIGGERING AI: Scanning document {doc.document_id}")
            triggered = await doc.paperless_client.trigger_ai_processing(
                doc.document_id
            )
            if triggered:
                doc.status = "waiting_for_ai"
                doc.retry_count = 0  # Reset for AI polling phase
                logger.info("🤖 AI TRIGGERED: Polling for completion...")
            else:
                logger.warning("AI trigger failed, retrying...")
                doc.retry_count += 1
                if doc.retry_count >= AI_TRIGGER_MAX_RETRIES:
                    # Give up on AI, send basic success
                    await self._send_basic_success_notification(doc)
                    return True  # Add to completed_tasks
        else:
            # No AI configured
            doc.status = "completed"
            await self._send_success_notification(doc)
            return True  # Add to completed_tasks
        return False

    async def _handle_waiting_for_ai_state(self, doc) -> bool:
        """Handle waiting for AI state"""
        ai_result = await self._check_ai_processing(doc)
        if ai_result:
            doc.ai_analysis = ai_result
            doc.ai_processed = True
            doc.status = "completed"
            logger.info(f"🎉 AI COMPLETE: Document {doc.document_id} processed!")
            await self._send_success_notification(doc)
            return True  # Add to completed_tasks
        else:
            doc.retry_count += 1
            if doc.retry_count >= AI_PROCESSING_TIMEOUT:
                logger.warning(f"⏰ AI TIMEOUT: Document {doc.document_id} after 120s")
                await self._send_basic_success_notification(doc)
                return True  # Add to completed_tasks
            return False

    async def _process_document_state(self, task_id: str, doc) -> bool:
        """Process a single document based on its state"""
        # STATE: completed - cleanup
        if doc.status == "completed":
            return await self._handle_completed_state(task_id)

        # TIMEOUT: Global timeout check
        if await self._handle_timeout_check(doc):
            return True

        # Map states to their handlers
        state_handlers = {
            "processing": lambda: self._handle_processing_state(task_id, doc),
            "waiting_for_consumption": lambda: self._handle_waiting_for_consumption_state(
                task_id, doc
            ),
            "paperless_indexing": lambda: self._handle_paperless_indexing_state(doc),
            "triggering_ai": lambda: self._handle_triggering_ai_state(doc),
            "waiting_for_ai": lambda: self._handle_waiting_for_ai_state(doc),
        }

        # Execute the appropriate handler or return False for unknown states
        handler = state_handlers.get(doc.status)
        if handler:
            return await handler()
        return False

    async def _tracking_loop(self):
        """Main tracking loop that checks document status"""
        while True:
            try:
                await asyncio.sleep(self.check_interval)

                # Check all tracked documents - SIMPLE STATE MACHINE
                completed_tasks = []
                for task_id, doc in list(self.tracked_documents.items()):
                    try:
                        should_complete = await self._process_document_state(
                            task_id, doc
                        )
                        if should_complete:
                            completed_tasks.append(task_id)

                    except (
                        aiohttp.ClientError,
                        ValueError,
                        KeyError,
                        AttributeError,
                    ) as e:
                        logger.error(
                            f"Error in state {doc.status} for {task_id}: {e!s}"
                        )
                        doc.retry_count += 1

                # Clean up completed documents
                for task_id in completed_tasks:
                    if task_id in self.tracked_documents:
                        del self.tracked_documents[task_id]
                        logger.info(
                            f"Removed completed document from tracking: {task_id}"
                        )

                # Save state after cleanup
                if completed_tasks:
                    self._save_state()

            except asyncio.CancelledError:
                logger.info("Document tracking loop cancelled")
                break
            except (
                aiohttp.ClientError,
                ValueError,
                KeyError,
                AttributeError,
                OSError,
            ) as e:
                logger.error(f"Error in tracking loop: {e!s}")
                await asyncio.sleep(self.check_interval)

    async def _check_ai_processing(self, doc: TrackedDocument) -> Optional[Dict]:
        """Check if AI has processed the document"""
        try:
            if not doc.document_id:
                return None

            # Try to get document details with AI analysis
            # First, try to get the document with its extracted data
            url = f"{doc.paperless_client.base_url}/api/documents/{doc.document_id}/"
            headers = {"Authorization": f"Token {doc.paperless_client.token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == HTTP_OK:
                        doc_data = await response.json()

                        # Check if AI has added tags, correspondent, or document type
                        ai_result = {
                            "document_id": doc.document_id,
                            "title": doc_data.get("title", doc.filename),
                            "tags": [],
                            "correspondent": None,
                            "document_type": None,
                            "content_preview": None,
                        }

                        # Extract tag names
                        if doc_data.get("tags"):
                            # Tags might be IDs, need to resolve them
                            tag_ids = doc_data["tags"]
                            if tag_ids:
                                tags_url = f"{doc.paperless_client.base_url}/api/tags/"
                                async with session.get(
                                    tags_url, headers=headers
                                ) as tags_response:
                                    if tags_response.status == HTTPStatus.OK:
                                        all_tags = await tags_response.json()
                                        tag_map = {
                                            tag["id"]: tag["name"]
                                            for tag in all_tags.get("results", [])
                                        }
                                        ai_result["tags"] = [
                                            tag_map.get(tid, f"Tag_{tid}")
                                            for tid in tag_ids
                                        ]

                        # Get correspondent name
                        if doc_data.get("correspondent"):
                            corr_id = doc_data["correspondent"]
                            corr_url = f"{doc.paperless_client.base_url}/api/correspondents/{corr_id}/"
                            async with session.get(
                                corr_url, headers=headers
                            ) as corr_response:
                                if corr_response.status == HTTPStatus.OK:
                                    corr_data = await corr_response.json()
                                    ai_result["correspondent"] = corr_data.get("name")

                        # Get document type
                        if doc_data.get("document_type"):
                            type_id = doc_data["document_type"]
                            type_url = f"{doc.paperless_client.base_url}/api/document_types/{type_id}/"
                            async with session.get(
                                type_url, headers=headers
                            ) as type_response:
                                if type_response.status == HTTPStatus.OK:
                                    type_data = await type_response.json()
                                    ai_result["document_type"] = type_data.get("name")

                        # Get content preview if available
                        if doc_data.get("content"):
                            ai_result["content_preview"] = (
                                doc_data["content"][:CONTENT_PREVIEW_LENGTH] + "..."
                                if len(doc_data.get("content", ""))
                                > CONTENT_PREVIEW_LENGTH
                                else doc_data.get("content")
                            )

                        # Consider it AI processed if we have tags or other AI-added metadata
                        if (
                            ai_result["tags"]
                            or ai_result["correspondent"]
                            or ai_result["document_type"]
                        ):
                            return ai_result

                        # If no AI metadata yet, return None to keep checking
                        return None

        except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error checking AI processing: {e!s}")
            return None

    async def _is_document_ready(self, doc: TrackedDocument) -> bool:
        """Check if document is actually consumed and fully indexed"""
        try:
            if not doc.document_id:
                return False

            # First: Verify document actually exists in database (not rejected as duplicate)
            url = f"{doc.paperless_client.base_url}/api/documents/{doc.document_id}/"
            headers = {"Authorization": f"Token {doc.paperless_client.token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == HTTP_NOT_FOUND:
                        # Document doesn't exist - likely rejected or failed
                        logger.warning(
                            f"Document {doc.document_id} not found - may have been rejected (duplicate?)"
                        )
                        return False
                    elif response.status != HTTP_OK:
                        logger.warning(
                            f"Could not check document: HTTP {response.status}"
                        )
                        return False

                    doc_data = await response.json()

                    # Second: Check document has been fully consumed and indexed
                    has_content = bool(doc_data.get("content", "").strip())
                    has_created_date = bool(doc_data.get("created"))

                    # Third: Verify it's not just a stub - should have actual data
                    checksum = doc_data.get("checksum", "")
                    file_type = doc_data.get("file_type", "")

                    # Document is ready if:
                    # 1. Has content (OCR completed) - this means it's been consumed AND indexed
                    # 2. Has creation date (stored in DB)
                    # If we can retrieve it with content via API, it must be consumed
                    is_indexed = has_content and has_created_date

                    logger.info(
                        f"Document {doc.document_id} status - indexed: {is_indexed}"
                    )
                    logger.info(
                        f"  - has_content: {has_content}, has_created_date: {has_created_date}"
                    )
                    logger.info(
                        f"  - checksum: {bool(checksum)}, file_type: {file_type}"
                    )

                    # If indexed with content, it's ready for AI processing
                    if is_indexed:
                        # Final check: verify document is searchable (fully committed to DB)
                        return await self._verify_document_searchable(doc)
                    else:
                        return False

        except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error checking if document is ready: {e!s}")
            return False

    async def _verify_document_searchable(self, doc: TrackedDocument) -> bool:
        """Final verification: check if document appears in recent documents list (like UI)"""
        try:
            # Use the same endpoint as the UI to check recent documents
            url = f"{doc.paperless_client.base_url}/api/documents/"
            params = {
                "page": 1,
                "page_size": 50,
                "ordering": "-created",
                "truncate_content": "true",
            }
            headers = {"Authorization": f"Token {doc.paperless_client.token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == HTTP_OK:
                        recent_docs = await response.json()

                        # Check if our document appears in the recent documents list
                        found_docs = recent_docs.get("results", [])
                        for found_doc in found_docs:
                            if found_doc.get("id") == doc.document_id:
                                logger.info(
                                    f"Document {doc.document_id} found in recent documents list - ready for AI"
                                )
                                return True

                        logger.info(
                            f"Document {doc.document_id} not in recent documents list yet - not ready"
                        )
                        return False
                    else:
                        logger.warning(
                            f"Recent documents query failed: HTTP {response.status}"
                        )
                        return False

        except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error verifying document in recent list: {e!s}")
            return False

    async def _find_document_by_uuid(
        self, paperless_client, tracking_uuid: str
    ) -> Optional[int]:
        """Find document by our tracking UUID in the original filename"""
        try:
            # Search for documents containing our UUID
            url = f"{paperless_client.base_url}/api/documents/"
            params = {
                "page": 1,
                "page_size": 50,
                "ordering": "-created",
                "truncate_content": "true",
            }
            headers = {"Authorization": f"Token {paperless_client.token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == HTTP_OK:
                        recent_docs = await response.json()

                        # Look for our UUID in original_file_name or title
                        for doc in recent_docs.get("results", []):
                            original_name = doc.get("original_file_name", "")
                            title = doc.get("title", "")

                            if tracking_uuid in original_name or tracking_uuid in title:
                                doc_id = doc.get("id")
                                logger.info(
                                    f"🔍 DEFINITIVE MATCH: Found document {doc_id} with UUID {tracking_uuid}"
                                )
                                logger.info(f"   Original name: {original_name}")
                                logger.info(f"   Title: {title}")
                                return doc_id

                        logger.warning(f"No document found with UUID {tracking_uuid}")
                        return None
                    else:
                        logger.error(
                            f"Failed to search for UUID: HTTP {response.status}"
                        )
                        return None

        except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error finding document by UUID: {e!s}")
            return None

    async def _get_recent_documents_api(self, paperless_client) -> Optional[dict]:
        """Get recent documents using direct API call"""
        url = f"{paperless_client.base_url}/api/documents/"
        params = {"ordering": "-created", "page_size": 20}
        headers = {"Authorization": f"Token {paperless_client.token}"}

        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == HTTP_OK:
                    return await response.json()
        return None

    def _is_document_recent(self, doc_created_str: str, time_threshold) -> bool:
        """Check if document creation time is after threshold"""
        try:
            from dateutil.parser import parse

            doc_time = parse(doc_created_str)
            return doc_time >= time_threshold
        except (ValueError, TypeError) as e:
            logger.debug(f"Error parsing date {doc_created_str}: {e}")
            return False

    async def _search_documents_by_term(
        self, paperless_client, term: str
    ) -> Optional[dict]:
        """Search documents by term or get recent ones if term is empty"""
        if term:
            return await paperless_client.search_documents(term)
        else:
            return await self._get_recent_documents_api(paperless_client)

    async def _find_recent_document_by_filename(
        self, paperless_client, filename: str, upload_time
    ) -> Optional[int]:
        """Find a recently uploaded document by filename"""
        try:
            from datetime import timedelta

            # Get recent documents (last 10 minutes)
            time_threshold = upload_time - timedelta(minutes=10)

            # Try multiple search approaches
            search_terms = [
                filename.split(".")[0],  # Without extension
                filename,  # With extension
                "",  # All recent documents
            ]

            for term in search_terms:
                try:
                    search_results = await self._search_documents_by_term(
                        paperless_client, term
                    )

                    if search_results and search_results.get("results"):
                        logger.info(
                            f"Found {len(search_results['results'])} documents for search '{term}'"
                        )

                        for doc in search_results["results"]:
                            doc_created = doc.get("created")
                            doc_id = doc.get("id")
                            doc_title = doc.get("title", "Untitled")

                            if (
                                doc_created
                                and doc_id
                                and self._is_document_recent(
                                    doc_created, time_threshold
                                )
                            ):
                                logger.info(
                                    f"Found recent document: ID={doc_id}, title='{doc_title}', created={doc_created}"
                                )
                                return doc_id

                except (aiohttp.ClientError, ValueError, KeyError) as e:
                    logger.debug(f"Error searching with term '{term}': {e}")
                    continue

            logger.warning(
                f"No recent documents found for {filename} after {upload_time}"
            )
            return None

        except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error finding document by filename: {e!s}")
            return None

    async def _send_basic_success_notification(self, doc: TrackedDocument):
        """Send basic success notification when we can't get full details"""
        try:
            message = "✅ **Document Upload Complete!**\n\n"
            message += f"📄 **File:** {doc.filename}\n"
            message += (
                "✅ *Document should be processed and available in Paperless-NGX*\n"
            )
            message += "🔍 *Try using /query to search for it*"

            await self.bot.bot.send_message(chat_id=doc.chat_id, text=message)

        except (AttributeError, ValueError, OSError) as e:
            logger.error(f"Error sending basic success notification: {e!s}")

    async def _send_success_notification(self, doc: TrackedDocument):
        """Send notification when document is fully processed"""
        try:
            message = "✅ **Document Processed Successfully!**\n\n"
            message += f"📄 **File:** {doc.filename}\n"

            if doc.ai_analysis:
                # AI-enhanced notification
                ai = doc.ai_analysis

                if ai.get("title") and ai["title"] != doc.filename:
                    message += f"📝 **Title:** {ai['title']}\n"

                if ai.get("tags"):
                    message += f"🏷️ **Tags:** {', '.join(ai['tags'])}\n"

                if ai.get("correspondent"):
                    message += f"👤 **Correspondent:** {ai['correspondent']}\n"

                if ai.get("document_type"):
                    message += f"📋 **Type:** {ai['document_type']}\n"

                if ai.get("content_preview"):
                    preview = (
                        ai["content_preview"][:CONTENT_PREVIEW_TRUNCATE_LENGTH] + "..."
                        if len(ai["content_preview"]) > CONTENT_PREVIEW_TRUNCATE_LENGTH
                        else ai["content_preview"]
                    )
                    message += f"\n💬 **Preview:** _{preview}_\n"

                message += "\n🤖 *AI analysis complete - document is searchable!*"
            elif not doc.paperless_client.ai_url:
                # No AI configured - basic notification
                if doc.document_id:
                    message += f"🆔 **Document ID:** {doc.document_id}\n"
                message += "\n✅ *Document uploaded and indexed in Paperless-NGX*\n"
                message += "📝 *Ready for searching and manual tagging*"
            else:
                # AI configured but no analysis available yet
                message += "\n✅ *Document is now searchable in Paperless-NGX*\n"
                message += "⏳ *AI analysis may still be processing*"

            # Send notification to user
            await self.bot.bot.send_message(
                chat_id=doc.chat_id, text=message, parse_mode="Markdown"
            )

        except (AttributeError, ValueError, OSError) as e:
            logger.error(f"Error sending success notification: {e!s}")

    async def _send_failure_notification(self, doc: TrackedDocument, error: str):
        """Send notification when document processing fails"""
        try:
            message = "❌ **Document Processing Failed**\n\n"
            message += f"📄 File: {doc.filename}\n"
            message += f"⚠️ Error: {error}\n\n"
            message += "Please try uploading again or check the document format."

            await self.bot.bot.send_message(chat_id=doc.chat_id, text=message)
        except (AttributeError, ValueError, OSError) as e:
            logger.error(f"Error sending failure notification: {e!s}")

    async def _send_timeout_notification(self, doc: TrackedDocument):
        """Send notification when tracking times out"""
        try:
            message = "⏱️ **Document Processing Timeout**\n\n"
            message += f"📄 File: {doc.filename}\n"

            if doc.document_id:
                message += f"✅ Document was uploaded (ID: {doc.document_id})\n"
                message += "⏳ But AI analysis is still pending.\n\n"
                message += "The document is searchable, but may lack AI-generated tags."
            else:
                message += "⚠️ Processing is taking longer than expected.\n"
                message += "Please check Paperless-NGX directly."

            await self.bot.bot.send_message(chat_id=doc.chat_id, text=message)
        except (AttributeError, ValueError, OSError) as e:
            logger.error(f"Error sending timeout notification: {e!s}")
