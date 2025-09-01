import asyncio
import logging
from typing import Any, Dict, Optional

import aiofiles
import aiohttp

from config import PAPERLESS_AI_TOKEN, PAPERLESS_AI_URL, PAPERLESS_TOKEN, PAPERLESS_URL
from constants import HTTPStatus

logger = logging.getLogger(__name__)


class PaperlessClient:
    def __init__(
        self,
        paperless_url: Optional[str] = None,
        paperless_token: Optional[str] = None,
        paperless_ai_url: Optional[str] = None,
        paperless_ai_token: Optional[str] = None,
    ):
        self.base_url = paperless_url or PAPERLESS_URL
        self.token = paperless_token or PAPERLESS_TOKEN
        self.ai_url = paperless_ai_url or PAPERLESS_AI_URL
        self.ai_token = paperless_ai_token or PAPERLESS_AI_TOKEN
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json",
        }

    async def upload_document(
        self,
        file_path: str,
        title: Optional[str] = None,
        correspondent: Optional[str] = None,
        document_type: Optional[str] = None,
        tags: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Upload a document to Paperless-NGX"""
        url = f"{self.base_url}/api/documents/post_document/"

        data = aiohttp.FormData()

        async with aiofiles.open(file_path, "rb") as f:
            file_content = await f.read()
            data.add_field("document", file_content, filename=file_path.split("/")[-1])

        if title:
            data.add_field("title", title)
        if correspondent:
            data.add_field("correspondent", correspondent)
        if document_type:
            data.add_field("document_type", document_type)
        if tags:
            for tag in tags:
                data.add_field("tags", tag)

        headers = {"Authorization": f"Token {self.token}"}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, data=data, headers=headers) as response:
                    if response.status == HTTPStatus.OK:
                        result = await response.json()
                        logger.info(f"🔍 UPLOAD RESPONSE: {result}")
                        logger.info(f"🔍 UPLOAD RESPONSE TYPE: {type(result)}")
                        if isinstance(result, dict):
                            logger.info(f"🔍 UPLOAD KEYS: {list(result.keys())}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Upload failed with status {response.status}: {error_text}"
                        )
                        raise Exception(f"Upload failed: {error_text}")
            except Exception as e:
                logger.error(f"Error uploading document: {e!s}")
                raise

    async def get_document_status(self, task_id: str) -> Dict[str, Any]:
        """Check the status of a document processing task"""
        url = f"{self.base_url}/api/tasks/{task_id}/"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if response.status == HTTPStatus.OK:
                    status_result = await response.json()
                    logger.info(f"🔍 TASK STATUS RESPONSE: {status_result}")
                    logger.info(
                        f"🔍 TASK STATUS KEYS: {list(status_result.keys()) if isinstance(status_result, dict) else 'Not a dict'}"
                    )
                    return status_result
                else:
                    raise Exception(
                        f"Failed to get task status: {await response.text()}"
                    )

    async def trigger_ai_processing(self, document_id: int) -> bool:
        """Trigger Paperless-AI to process documents (may process all unprocessed)"""
        if not self.ai_url or not self.ai_token:
            logger.info("Paperless-AI not configured, skipping AI processing")
            return False

        # Try to trigger processing - many paperless-ai setups process all unprocessed documents
        # rather than targeting specific ones
        processing_triggered = await self._trigger_ai_processing_all(document_id)
        if processing_triggered:
            return True

        # Fallback: try to process the specific document
        return await self._trigger_ai_document_processing(document_id)

    async def _trigger_ai_scan(self) -> bool:
        """Trigger Paperless-AI to scan/discover new documents"""
        scan_endpoints = [
            f"{self.ai_url}/api/scan",
            f"{self.ai_url}/scan",
            f"{self.ai_url}/api/sync",
            f"{self.ai_url}/sync",
            f"{self.ai_url}/api/discover",
            f"{self.ai_url}/discover",
        ]

        headers = {"x-api-key": self.ai_token, "Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            for endpoint in scan_endpoints:
                try:
                    # Try POST first
                    async with session.post(
                        endpoint, headers=headers, json={}
                    ) as response:
                        if response.status in [
                            HTTPStatus.OK,
                            HTTPStatus.CREATED,
                            HTTPStatus.ACCEPTED,
                        ]:
                            logger.info(f"AI scan triggered via POST {endpoint}")
                            return True

                    # Try GET
                    async with session.get(endpoint, headers=headers) as response:
                        if response.status in [
                            HTTPStatus.OK,
                            HTTPStatus.CREATED,
                            HTTPStatus.ACCEPTED,
                        ]:
                            logger.info(f"AI scan triggered via GET {endpoint}")
                            return True

                except (aiohttp.ClientError, ValueError, KeyError) as e:
                    logger.debug(f"Error trying scan endpoint {endpoint}: {e!s}")
                    continue

        logger.info("No scan endpoint found, proceeding without explicit scan")
        return False

    async def _trigger_ai_processing_all(
        self, document_id: Optional[int] = None
    ) -> bool:
        """Trigger Paperless-AI to scan and process documents using the actual API"""
        scan_endpoint = f"{self.ai_url}/api/scan/now"

        headers = {"x-api-key": self.ai_token, "Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            try:
                # Use the exact endpoint from your curl command
                async with session.post(scan_endpoint, headers=headers) as response:
                    if response.status in [
                        HTTPStatus.OK,
                        HTTPStatus.CREATED,
                        HTTPStatus.ACCEPTED,
                    ]:
                        logger.info(f"AI scan triggered via POST {scan_endpoint}")

                        # Now poll the processing status to wait for completion
                        return await self._wait_for_ai_processing_complete(
                            session, headers, document_id
                        )
                    else:
                        logger.warning(f"AI scan failed with status {response.status}")
                        return False

            except (aiohttp.ClientError, ValueError, KeyError) as e:
                logger.error(f"Error triggering AI scan: {e!s}")
                return False

    async def _wait_for_ai_processing_complete(
        self, session, headers, target_document_id: int
    ) -> bool:
        """Poll until our EXACT document ID appears in lastProcessed.documentId"""
        status_endpoint = f"{self.ai_url}/api/processing-status"
        max_wait_time = 120  # seconds
        check_interval = 0.25  # 250ms - fast polling

        logger.info(
            f"Waiting for document ID {target_document_id} to appear in AI processing-status"
        )

        for iteration in range(int(max_wait_time / check_interval)):
            try:
                async with session.get(status_endpoint, headers=headers) as response:
                    if response.status == HTTPStatus.OK:
                        status_data = await response.json()
                        logger.debug(f"AI status check #{iteration}: {status_data}")

                        last_processed = status_data.get("lastProcessed")
                        currently_processing = status_data.get("currentlyProcessing")

                        # DEFINITIVE CHECK: our exact document ID in lastProcessed
                        if last_processed and int(
                            last_processed.get("documentId", 0)
                        ) == int(target_document_id):
                            logger.info(
                                f"✅ CONFIRMED: Document {target_document_id} processed by AI"
                            )
                            logger.info(f"   Title: {last_processed.get('title')}")
                            logger.info(
                                f"   Processed at: {last_processed.get('processed_at')}"
                            )
                            return True

                        # Show what's currently being processed
                        if currently_processing:
                            current_id = currently_processing.get("documentId")
                            logger.info(
                                f"AI currently processing document {current_id}, waiting for {target_document_id}"
                            )

                        await asyncio.sleep(check_interval)

                    else:
                        logger.warning(
                            f"AI status check failed: HTTP {response.status}"
                        )
                        await asyncio.sleep(check_interval)

            except (aiohttp.ClientError, ValueError, KeyError) as e:
                logger.error(f"Error checking AI status: {e!s}")
                await asyncio.sleep(check_interval)

        logger.error(
            f"❌ TIMEOUT: Document {target_document_id} never appeared in AI processing-status after {max_wait_time}s"
        )
        return False

    async def _trigger_ai_document_processing(self, document_id: int) -> bool:
        """Trigger processing of a specific document after scan"""
        # Try multiple possible endpoints for triggering AI processing
        possible_endpoints = [
            f"{self.ai_url}/api/process/{document_id}",
            f"{self.ai_url}/api/analyze/{document_id}",
            f"{self.ai_url}/process/{document_id}",
            f"{self.ai_url}/manual",
            f"{self.ai_url}/api/trigger",
        ]

        headers = {"x-api-key": self.ai_token, "Content-Type": "application/json"}

        # Different payload formats to try
        payloads = [
            {"document_id": document_id},
            {"documents": [document_id]},
            {"doc_id": document_id},
            {"id": document_id},
        ]

        async with aiohttp.ClientSession() as session:
            for endpoint in possible_endpoints:
                for payload in payloads:
                    try:
                        # Try POST
                        async with session.post(
                            endpoint, headers=headers, json=payload
                        ) as response:
                            if response.status in [
                                HTTPStatus.OK,
                                HTTPStatus.CREATED,
                                HTTPStatus.ACCEPTED,
                            ]:
                                logger.info(
                                    f"AI processing triggered via POST {endpoint}"
                                )
                                return True
                            elif (
                                response.status == HTTPStatus.METHOD_NOT_ALLOWED
                            ):  # Method not allowed, try GET
                                pass
                            else:
                                logger.debug(
                                    f"POST {endpoint} returned {response.status}"
                                )

                        # Try GET (some endpoints might use GET with query params)
                        get_url = f"{endpoint}?document_id={document_id}"
                        async with session.get(get_url, headers=headers) as response:
                            if response.status in [
                                HTTPStatus.OK,
                                HTTPStatus.CREATED,
                                HTTPStatus.ACCEPTED,
                            ]:
                                logger.info(
                                    f"AI processing triggered via GET {get_url}"
                                )
                                return True

                    except (aiohttp.ClientError, ValueError, KeyError) as e:
                        logger.debug(f"Error trying {endpoint}: {e!s}")
                        continue

            # Fallback: Try to add AI processing tag to document in Paperless
            # This is the documented way for some Paperless-AI setups
            return await self._add_ai_processing_tag(document_id)

    async def _add_ai_processing_tag(self, document_id: int) -> bool:
        """Add AI processing tag to trigger Paperless-AI via tagging mechanism"""
        try:
            # Common tag names used by Paperless-AI setups
            ai_tag_names = ["paperless-ai", "paperless-gpt", "ai-process", "process-ai"]

            async with aiohttp.ClientSession() as session:
                # First, get or create the AI processing tag
                tags_url = f"{self.base_url}/api/tags/"
                async with session.get(tags_url, headers=self.headers) as response:
                    if response.status != HTTPStatus.OK:
                        return False

                    tags_data = await response.json()
                    existing_tags = {
                        tag["name"]: tag["id"] for tag in tags_data.get("results", [])
                    }

                    # Find or create AI processing tag
                    ai_tag_id = None
                    for tag_name in ai_tag_names:
                        if tag_name in existing_tags:
                            ai_tag_id = existing_tags[tag_name]
                            logger.info(f"Found existing AI tag: {tag_name}")
                            break

                    if not ai_tag_id:
                        # Create new AI processing tag
                        tag_data = {"name": "paperless-ai", "color": "#FF0000"}
                        async with session.post(
                            tags_url, headers=self.headers, json=tag_data
                        ) as create_response:
                            if create_response.status in [
                                HTTPStatus.OK,
                                HTTPStatus.CREATED,
                            ]:
                                result = await create_response.json()
                                ai_tag_id = result["id"]
                                logger.info("Created new AI processing tag")
                            else:
                                return False

                    # Add tag to document
                    doc_url = f"{self.base_url}/api/documents/{document_id}/"
                    async with session.get(
                        doc_url, headers=self.headers
                    ) as doc_response:
                        if doc_response.status != HTTPStatus.OK:
                            return False

                        doc_data = await doc_response.json()
                        current_tags = doc_data.get("tags", [])

                        if ai_tag_id not in current_tags:
                            current_tags.append(ai_tag_id)
                            update_data = {"tags": current_tags}

                            async with session.patch(
                                doc_url, headers=self.headers, json=update_data
                            ) as patch_response:
                                if patch_response.status == HTTPStatus.OK:
                                    logger.info(
                                        f"Added AI processing tag to document {document_id}"
                                    )
                                    return True
                        else:
                            logger.info(
                                f"Document {document_id} already has AI processing tag"
                            )
                            return True

        except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as e:
            logger.error(f"Error adding AI processing tag: {e!s}")

        return False

    async def search_documents(self, query: str) -> Dict[str, Any]:
        """Search documents in Paperless-NGX"""
        url = f"{self.base_url}/api/documents/"
        params = {"query": query}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=self.headers, params=params
            ) as response:
                if response.status == HTTPStatus.OK:
                    return await response.json()
                else:
                    raise Exception(f"Search failed: {await response.text()}")

    async def query_ai(self, query: str) -> Dict[str, Any]:
        """Query Paperless-AI for intelligent document search with structured response"""
        if not self.ai_url or not self.ai_token:
            return {
                "success": False,
                "error": "AI service not configured",
                "answer": "AI service not configured",
            }

        # Try multiple possible endpoints for Paperless-AI
        possible_endpoints = [
            f"{self.ai_url}/api/chat",
            f"{self.ai_url}/api/query",
            f"{self.ai_url}/chat",
            f"{self.ai_url}/query",
        ]

        headers = {"x-api-key": self.ai_token, "Content-Type": "application/json"}

        # Try different payload formats
        payloads = [
            {"query": query, "message": query},
            {"query": query},
            {"message": query},
            {"prompt": query},
        ]

        async with aiohttp.ClientSession() as session:
            for endpoint in possible_endpoints:
                for payload in payloads:
                    try:
                        async with session.post(
                            endpoint, headers=headers, json=payload
                        ) as response:
                            if response.status == HTTPStatus.OK:
                                result = await response.json()
                                logger.info(f"AI query successful via {endpoint}")

                                # Parse different response formats
                                parsed_response = self._parse_ai_response(result, query)
                                if parsed_response["success"]:
                                    return parsed_response

                            elif response.status == HTTPStatus.NOT_FOUND:
                                continue  # Try next endpoint
                            else:
                                logger.warning(
                                    f"AI query failed at {endpoint} with status {response.status}"
                                )
                                error_text = await response.text()
                                logger.debug(f"Error details: {error_text}")

                    except (aiohttp.ClientError, ValueError, KeyError) as e:
                        logger.debug(f"Error trying {endpoint} with {payload}: {e!s}")
                        continue

            # If all endpoints failed
            return {
                "success": False,
                "error": "AI service temporarily unavailable",
                "answer": "AI service temporarily unavailable",
                "tried_endpoints": possible_endpoints,
            }

    def _extract_answer_from_response(self, raw_response: Dict) -> Optional[str]:
        """Extract answer text from various AI response formats"""
        answer_keys = ["answer", "response", "message"]
        for key in answer_keys:
            if key in raw_response:
                return raw_response[key]

        # Handle OpenAI-style response
        choices = raw_response.get("choices")
        if choices:
            choice = choices[0]
            if "message" in choice:
                return choice["message"].get("content", "")
            elif "text" in choice:
                return choice["text"]

        return None

    def _extract_sources_from_response(self, raw_response: Dict) -> list:
        """Extract document sources from various AI response formats"""
        source_keys = ["sources", "references"]
        for key in source_keys:
            if key in raw_response:
                return raw_response[key]
        return []

    def _extract_documents_from_response(self, raw_response: Dict) -> list:
        """Extract document references from AI response"""
        return raw_response.get("documents", [])

    def _extract_tags_from_response(self, raw_response: Dict) -> list:
        """Extract tags from various AI response formats"""
        tag_keys = ["tags", "entities"]
        for key in tag_keys:
            if key in raw_response:
                return raw_response[key]
        return []

    def _extract_confidence_from_response(self, raw_response: Dict) -> Optional[float]:
        """Extract confidence score from AI response"""
        confidence_keys = ["confidence", "score"]
        for key in confidence_keys:
            if key in raw_response:
                return raw_response[key]
        return None

    def _parse_ai_response(self, raw_response: Dict, query: str) -> Dict[str, Any]:
        """Parse AI response into structured format"""
        try:
            # Handle different response formats from various AI services
            parsed = {
                "success": True,
                "query": query,
                "answer": None,
                "documents_found": [],
                "tags_found": [],
                "confidence": None,
                "sources": [],
                "raw_response": raw_response,
            }

            # Extract data using helper methods
            parsed["answer"] = self._extract_answer_from_response(raw_response)
            parsed["sources"] = self._extract_sources_from_response(raw_response)
            parsed["documents_found"] = self._extract_documents_from_response(
                raw_response
            )
            parsed["tags_found"] = self._extract_tags_from_response(raw_response)
            parsed["confidence"] = self._extract_confidence_from_response(raw_response)

            # Ensure we have an answer
            if not parsed["answer"]:
                parsed["success"] = False
                parsed["error"] = "No answer found in AI response"
                parsed["answer"] = "No answer found"

            return parsed

        except (ValueError, KeyError, TypeError, AttributeError) as e:
            logger.error(f"Error parsing AI response: {e!s}")
            return {
                "success": False,
                "error": f"Error parsing AI response: {e!s}",
                "answer": "Error parsing AI response",
                "raw_response": raw_response,
            }
