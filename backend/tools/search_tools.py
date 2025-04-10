from typing import Optional, List, Dict, Any
from ..config.supabase import get_supabase_client
import traceback


async def search_listings(
    destination: Optional[str] = None,
    guests: Optional[int] = None,

    limit: int = 3 
) -> List[Dict[str, Any]]:
    """
    Searches the Supabase 'listings' table based on destination and guest count.
    Returns a list of matching listings (up to a limit).
    """
    print(f"[Tool Start] 'search_listings' called with: dest={destination}, guests={guests}, limit={limit}")
    results = []
    try:
        supabase = get_supabase_client() # Get initialized client
        query = supabase.table("listings").select(
            "id, title, city, price_per_night, max_guests, description, image_url" # Select specific columns
        )

        # Apply filters based on provided arguments
        if destination:
            # Use ilike for case-insensitive partial matching on city
            query = query.ilike("city", f"%{destination.strip()}%")
        if guests:
            query = query.gte("max_guests", guests) # max_guests >= required guests

        # Apply limit
        query = query.limit(limit)

        # Execute query
        response = await query.execute() 

        print(f"[Tool Info] Supabase Response: {response}")
        if response.data:
            results = response.data
            print(f"[Tool Info] Found {len(results)} listings.")
        else:
             print("[Tool Info] No listings found matching criteria.")
             # Consider if response has error messages

    except Exception as e:
        print(f"ERROR during Supabase query execution: {e}")
        traceback.print_exc()
        # Return empty list on error or re-raise

    print("[Tool End] 'search_listings' finished.")
    return results # Return list of listing dictionaries

# --- Tool Schema Definition (Dictionary Format) ---
search_listings_tool_schema = {
    "name": "search_listings",
    "description": "Searches for available accommodation listings based on criteria like destination city and number of guests. Returns a list of matching properties.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "destination": {
                "type": "STRING",
                "description": "The city or area the user wants to search listings in (e.g., 'London', 'Kyoto')."
            },
            "guests": {
                "type": "INTEGER",
                "description": "The minimum number of guests the accommodation should support."
            },
            # Add other parameter descriptions here later (dates, price)
             "limit": {
                "type": "INTEGER",
                "description": "Optional. Maximum number of listings to return (default is 3)."
            }
        },
        "required": [] # Make destination/guests optional for now to allow broad searches? Or require destination? Let's make destination optional initially.
    }
}


