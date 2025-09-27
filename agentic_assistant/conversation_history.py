# agentic_assistant/conversation_history.py
import pickle
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

class ConversationHistory:
    def __init__(self, max_conversations: int = 3):
        self.max_conversations = max_conversations
        self.history_file = os.path.join(os.path.dirname(__file__), "conversation_history.pkl")
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Ensure the directory for the history file exists."""
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
    
    def load_history(self) -> List[Dict[str, Any]]:
        """Load conversation history from pickle file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'rb') as f:
                    return pickle.load(f)
            return []
        except (FileNotFoundError, EOFError, pickle.UnpicklingError):
            return []
    
    def save_history(self, conversations: List[Dict[str, Any]]) -> None:
        """Save conversation history to pickle file."""
        try:
            with open(self.history_file, 'wb') as f:
                pickle.dump(conversations, f)
        except Exception as e:
            print(f"Error saving conversation history: {e}")
    
    def add_conversation(self, session_id: str, messages: List[Dict[str, str]], title: Optional[str] = None) -> None:
        """Add a new conversation to history, keeping only the last max_conversations."""
        if not messages:
            return
        
        conversations = self.load_history()
        
        # Create conversation entry
        conversation = {
            "session_id": session_id,
            "title": title or self._generate_title(messages),
            "timestamp": datetime.now().isoformat(),
            "messages": messages
        }
        
        # Add to beginning of list
        conversations.insert(0, conversation)
        
        # Keep only the last max_conversations
        conversations = conversations[:self.max_conversations]
        
        self.save_history(conversations)
    
    def _generate_title(self, messages: List[Dict[str, str]]) -> str:
        """Generate a title from the first user message."""
        for message in messages:
            if message.get("role") == "user":
                text = message.get("content", "")
                # Take first 50 characters and add ellipsis if longer
                if len(text) > 50:
                    return text[:50] + "..."
                return text
        return f"Conversation {datetime.now().strftime('%m/%d %H:%M')}"
    
    def get_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations in history."""
        return self.load_history()
    
    def clear_history(self) -> None:
        """Clear all conversation history."""
        try:
            if os.path.exists(self.history_file):
                os.remove(self.history_file)
        except Exception as e:
            print(f"Error clearing conversation history: {e}")
    
    def get_conversation_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific conversation by session ID."""
        conversations = self.load_history()
        for conv in conversations:
            if conv.get("session_id") == session_id:
                return conv
        return None