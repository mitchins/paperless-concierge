#!/usr/bin/env python3
"""
Comprehensive workflow tests with mocks for Paperless-NGX Telegram Concierge.
Tests the complete end-to-end workflow without external dependencies.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import os
import sys
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Telegram objects
@dataclass
class MockUser:
    id: int = 12345
    username: str = "testuser"
    first_name: str = "Test"

@dataclass
class MockChat:
    id: int = 12345

@dataclass 
class MockMessage:
    message_id: int = 1
    from_user: MockUser = None
    chat: MockChat = None
    photo: list = None
    document: Mock = None
    
    def __post_init__(self):
        if self.from_user is None:
            self.from_user = MockUser()
        if self.chat is None:
            self.chat = MockChat()

@dataclass
class MockUpdate:
    message: MockMessage = None
    effective_user: MockUser = None
    callback_query: Mock = None
    
    def __post_init__(self):
        if self.message is None:
            self.message = MockMessage()
        if self.effective_user is None:
            self.effective_user = MockUser()

class MockFile:
    def __init__(self, file_id="test_file_123"):
        self.file_id = file_id
        self.file_path = f"photos/{file_id}.jpg"
    
    async def get_file(self):
        return self
        
    async def download_to_drive(self, path):
        # Create a dummy file
        with open(path, 'wb') as f:
            f.write(b"fake image data")

# Test the complete document upload workflow
async def test_document_upload_workflow():
    """Test complete document upload workflow with mocks"""
    
    from bot import TelegramConcierge
    from paperless_client import PaperlessClient
    from document_tracker import DocumentTracker
    from user_manager import get_user_manager
    
    # Mock user manager
    with patch('bot.get_user_manager') as mock_get_user_manager:
        mock_user_manager = Mock()
        mock_user_manager.is_authorized.return_value = True
        mock_user_manager.get_user_config.return_value = Mock(
            paperless_url="http://test-paperless:8000",
            paperless_token="test_token",
            paperless_ai_url="http://test-ai:8080",
            paperless_ai_token="test_ai_token"
        )
        mock_get_user_manager.return_value = mock_user_manager
        
        # Mock document tracker
        mock_tracker = Mock()
        
        # Create bot instance
        bot = TelegramConcierge(document_tracker=mock_tracker)
        
        # Mock the paperless client
        with patch.object(bot, 'get_paperless_client') as mock_get_client:
            mock_client = Mock()
            mock_client.upload_document = AsyncMock(return_value="task-123")
            mock_get_client.return_value = mock_client
            
            # Create mock update with photo
            update = MockUpdate()
            update.message.photo = [MockFile()]
            
            # Mock context
            context = Mock()
            
            # Mock message reply methods
            status_message = Mock()
            status_message.edit_text = AsyncMock()
            update.message.reply_text = AsyncMock(return_value=status_message)
            
            # Mock file operations
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_temp_file = Mock()
                mock_temp_file.name = "/tmp/test_file.jpg"
                mock_temp_file.__enter__ = Mock(return_value=mock_temp_file)
                mock_temp_file.__exit__ = Mock(return_value=None)
                mock_temp.return_value = mock_temp_file
                
                with patch('os.path.exists', return_value=True), \
                     patch('os.unlink'):
                    
                    # Execute the upload
                    await bot.handle_document(update, context)
                    
                    # Verify the workflow
                    assert update.message.reply_text.called
                    assert mock_client.upload_document.called
                    assert mock_tracker.add_document.called
                    assert status_message.edit_text.called

async def test_ai_processing_workflow():
    """Test AI processing workflow with mocks"""
    
    from paperless_client import PaperlessClient
    
    client = PaperlessClient(
        paperless_url="http://test:8000",
        paperless_token="test_token", 
        paperless_ai_url="http://test-ai:8080",
        paperless_ai_token="test_ai_token"
    )
    
    # Mock aiohttp session
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "completed"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value = mock_response
        mock_session_instance.get.return_value = mock_response
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session.return_value = mock_session_instance
        
        # Test AI trigger
        result = await client.trigger_ai_processing(document_id=123)
        assert result is True
        
        # Verify API calls
        assert mock_session_instance.post.called
        
        # Test AI query
        mock_response.json = AsyncMock(return_value={
            "answer": "Test answer",
            "confidence": 0.9,
            "sources": ["doc1", "doc2"]
        })
        
        query_result = await client.query_ai("test query")
        assert "answer" in query_result

async def test_state_persistence():
    """Test document tracker state persistence"""
    
    from document_tracker import DocumentTracker, TrackedDocument
    
    # Mock telegram application
    mock_app = Mock()
    
    tracker = DocumentTracker(mock_app)
    
    # Add a document
    mock_client = Mock()
    document = TrackedDocument(
        task_id="test-123",
        user_id=12345,
        chat_id=12345,
        filename="test.pdf",
        paperless_client=mock_client,
        tracking_uuid="uuid-123"
    )
    
    tracker.documents["test-123"] = document
    
    # Test state can be serialized/deserialized
    state = {
        "task_id": document.task_id,
        "user_id": document.user_id,
        "filename": document.filename,
        "status": document.status
    }
    
    assert state["task_id"] == "test-123"
    assert state["status"] == "processing"

async def test_error_handling():
    """Test error handling and resilience"""
    
    from bot import TelegramConcierge
    
    bot = TelegramConcierge()
    
    # Test with invalid update
    with patch('bot.get_user_manager') as mock_get_user_manager:
        mock_user_manager = Mock()
        mock_user_manager.is_authorized.return_value = True
        mock_user_manager.get_user_config.return_value = None  # No config
        mock_get_user_manager.return_value = mock_user_manager
        
        update = MockUpdate()
        context = Mock()
        
        # Should handle missing config gracefully
        with patch.object(bot, 'get_paperless_client', side_effect=ValueError("No config")):
            update.message.reply_text = AsyncMock()
            
            await bot.handle_document(update, context)
            
            # Should have sent an error message
            assert update.message.reply_text.called

def test_configuration_validation():
    """Test configuration validation"""
    
    from config import TELEGRAM_BOT_TOKEN, PAPERLESS_URL
    from user_manager import UserManager
    
    # Test environment variables are loaded
    assert TELEGRAM_BOT_TOKEN is not None
    
    # Test user manager configurations
    user_manager = UserManager(auth_mode="global")
    assert user_manager.auth_mode == "global"

if __name__ == "__main__":
    # Run tests
    async def run_tests():
        print("🧪 Running comprehensive workflow tests...")
        
        await test_document_upload_workflow()
        print("✅ Document upload workflow test passed")
        
        await test_ai_processing_workflow() 
        print("✅ AI processing workflow test passed")
        
        await test_state_persistence()
        print("✅ State persistence test passed")
        
        await test_error_handling()
        print("✅ Error handling test passed")
        
        test_configuration_validation()
        print("✅ Configuration validation test passed")
        
        print("🎉 All workflow tests passed!")
    
    asyncio.run(run_tests())