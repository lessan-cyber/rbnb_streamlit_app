import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ListingResult(BaseModel):
    """Represents structured data for a single listing found by search."""

    id: Any
    title: Optional[str] = None
    city: Optional[str] = None
    price_per_night: Optional[float] = None
    max_guests: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    bedrooms: Optional[int] = None
    # amenities: Optional[List[str]] = None


class Message(BaseModel):
    """Represents a single message in the chat history."""

    role: str
    content: str


class ExtractedInfo(BaseModel):
    """Stores the extracted booking parameters."""

    destination: Optional[str] = None
    check_in: Optional[str] = (
        None  # Keep as string for now, validate format later if needed
    )
    check_out: Optional[str] = None
    guests: Optional[int] = None


class ChatRequest(BaseModel):
    """Defines the structure of incoming chat requests."""

    session_id: str
    message: str


class ChatResponse(BaseModel):
    """Defines the structure of outgoing chat responses."""

    response: str
    updated_info: Optional[ExtractedInfo] = None
    search_results: Optional[List[ListingResult]] = None
