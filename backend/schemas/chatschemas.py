# app/schemas/chatschemas.py
from pydantic import BaseModel, Field
from typing import Optional, List
import datetime

class Message(BaseModel):
    """Represents a single message in the chat history."""
    role: str  # 'user' or 'assistant' (or 'system' if you use it)
    content: str
    # You could add other metadata if needed, like a timestamp
    # timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)

class ExtractedInfo(BaseModel):
    """Stores the extracted booking parameters."""
    destination: Optional[str] = None
    check_in: Optional[str] = None  # Keep as string for now, validate format later if needed
    check_out: Optional[str] = None
    guests: Optional[int] = None

class ChatRequest(BaseModel):
    """Defines the structure of incoming chat requests."""
    session_id: str
    message: str
    # We load history/info from Redis based on session_id,
    # so they don't strictly need to be in the request model itself.
    # However, you *could* include them if your frontend manages state fully.

class ChatResponse(BaseModel):
    """Defines the structure of outgoing chat responses."""
    response: str  # The natural language message for the user
    updated_info: Optional[ExtractedInfo] = None # The latest booking info state