from typing import Optional, List, Dict, Any
from ..config.supabase import get_supabase_client
import traceback
import re
import logging
from ..config.redis import load_conversation_state, save_conversation_state
from ..schemas.chatschemas import Message, ExtractedInfo


async def search_listings(
    session_id: str,
    query: Optional[str] = None,
    destination: Optional[str] = None,
    guests: Optional[int] = None,
    country: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_bedrooms: Optional[int] = None,
    amenities: Optional[str] = None,
    check_in: Optional[str] = None,  # Add this parameter
    check_out: Optional[str] = None,  # Add this parameter
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Enhanced search function with multiple criteria and better matching.

    Args:
        session_id: User's session ID (required but not used for search)
        query: Free-text search query (searches across multiple fields)
        destination: City or area to search in
        guests: Minimum number of guests accommodation must support
        country: Country to search in
        min_price: Minimum price per night
        max_price: Maximum price per night
        min_bedrooms: Minimum number of bedrooms
        amenities: Comma-separated list of amenities to filter by
        limit: Maximum number of results to return

    Returns:
        List of matching listing dictionaries
    """
    log_prefix = f"[SESSION {session_id[:6]}] SEARCH:"
    logging.info(
        f"{log_prefix} Starting search with params: query={query}, dest={destination}, "
        f"guests={guests}, country={country}, price={min_price}-{max_price}"
    )
    state = await load_conversation_state(session_id)
    current_info: Optional[ExtractedInfo] = state.get("info")
    results = []
    try:
        supabase = get_supabase_client()

        # Select all relevant fields
        base_query = supabase.table("listings").select(
            "id, title, city, country, price_per_night, max_guests, description, "
            "image_url, bedrooms, amenities"
        )

        # Build our query with filters
        if query:
            # If free text query is provided, search multiple columns
            # Note: This assumes Supabase has text search capabilities
            clean_query = query.lower().strip()
            base_query = base_query.or_(
                f"title.ilike.%{clean_query}%,description.ilike.%{clean_query}%,"
                f"city.ilike.%{clean_query}%,country.ilike.%{clean_query}%"
            )

        # Apply individual filters if provided
        if destination:
            # Make destination matching more flexible - allow partial matches
            clean_dest = destination.lower().strip()
            base_query = base_query.or_(
                f"city.ilike.%{clean_dest}%,country.ilike.%{clean_dest}%"
            )

        # Other specific filters
        if country:
            base_query = base_query.ilike("country", f"%{country.strip()}%")

        if guests and guests > 0:
            # Convert float to integer before sending to database
            base_query = base_query.gte("max_guests", int(guests))

        if min_price and min_price > 0:
            base_query = base_query.gte("price_per_night", min_price)

        if max_price and max_price > 0:
            base_query = base_query.lte("price_per_night", max_price)

        if min_bedrooms and min_bedrooms > 0:
            base_query = base_query.gte("bedrooms", min_bedrooms)

        if amenities:
            # This assumes amenities is stored as an array in Supabase
            # You might need to adjust based on your actual data model
            for amenity in amenities.split(","):
                clean_amenity = amenity.strip().lower()
                if clean_amenity:
                    # Assuming Postgres array contains amenity
                    base_query = base_query.contains("amenities", [clean_amenity])

        # Apply limit and order by relevance/price
        base_query = base_query.order("price_per_night").limit(limit)

        # Execute query
        response = base_query.execute()

        if not response.data:
            logging.info(f"{log_prefix} No results found, trying fallback search...")

            # If no results with specific filters, try a broader search
            fallback_query = supabase.table("listings").select(
                "id, title, city, country, price_per_night, max_guests, description, "
                "image_url, bedrooms"
            )

            # Just use destination or country as a simple filter if available
            if destination:
                fallback_query = fallback_query.ilike(
                    "city", f"%{destination.strip()}%"
                )
            elif country:
                fallback_query = fallback_query.ilike("country", f"%{country.strip()}%")

            # Or search a random set if no location specified
            fallback_query = fallback_query.limit(limit)
            fallback_response = fallback_query.execute()

            if fallback_response.data:
                results = fallback_response.data
                logging.info(f"{log_prefix} Fallback found {len(results)} results")
            else:
                logging.warning(f"{log_prefix} No results even with fallback")
        else:
            results = response.data
            logging.info(f"{log_prefix} Found {len(results)} primary results")

        for item in results:
            # Add a default image URL if none exists
            if not item.get("image_url"):
                item["image_url"] = "https://placehold.co/600x400?text=No+Image"

            # Ensure description is not too long for display
            if item.get("description") and len(item["description"]) > 200:
                item["description"] = item["description"][:197] + "..."
            history: List[Message] = state.get("history", [])
            await save_conversation_state(
                session_id, current_info, history, listing=item
            )

    except Exception as e:
        logging.error(f"{log_prefix} Error during search: {str(e)}")
        traceback.print_exc()
        # Return empty list on error

    return results


# Add this at the bottom of the file

# Define an improved tool schema that guides the model better
search_tool_schema = {
    "name": "search_listings",
    "description": """Searches for available accommodations based on the user's requirements. 
    USE THIS TOOL WHENEVER:
    1. A user mentions ANY location, city, or country
    2. A user asks to see available listings or examples
    3. A user asks about prices, options, or accommodations in an area
    DO NOT try to make up examples - ALWAYS use this tool to get real listings.""",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Free text search query extracted from user's message (e.g., 'beachfront condo in Miami')",
            },
            "destination": {
                "type": "STRING",
                "description": "The geographical city, area, or region for the search (e.g., 'London', 'Kyoto', 'Tuscany'). MUST NOT include property names or descriptions.",
            },
            "guests": {"type": "INTEGER", "description": "Number of guests"},
            "country": {"type": "STRING", "description": "Country name if specified"},
            "min_price": {
                "type": "NUMBER",
                "description": "Minimum price per night in USD",
            },
            "max_price": {
                "type": "NUMBER",
                "description": "Maximum price per night in USD",
            },
            "min_bedrooms": {
                "type": "INTEGER",
                "description": "Minimum number of bedrooms required",
            },
            "amenities": {
                "type": "STRING",
                "description": "Comma-separated amenities (e.g., 'wifi,pool,gym')",
            },
            "check_in": {
                "type": "STRING",
                "description": "Check-in date in YYYY-MM-DD format",
            },
            "check_out": {
                "type": "STRING",
                "description": "Check-out date in YYYY-MM-DD format",
            },
        },
        "required": [],
    },
}
