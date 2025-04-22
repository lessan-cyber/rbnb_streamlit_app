from typing import Dict, Any, Optional, List
from ..config.supabase import get_supabase_client
from ..schemas.chatschemas import (
    ExtractedInfo,
    Message,
)  # For potentially getting dates from state
from ..config.redis import (
    load_conversation_state,
    save_conversation_state,
)  # To get current check-in/out dates
import datetime
import traceback


# --- Availability Check Function ---
async def check_availability(
    session_id: str,  # Add this parameter
    name: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,  #
) -> Dict[str, Any]:
    """
    Checks if a specific listing is available for booking between the given
    check-in and check-out dates by looking for overlapping bookings.
    Retrieves dates from conversation state if not explicitly provided.
    """
    supabase = get_supabase_client()
    # get the id of the listing from the name
    listing_id = supabase.table("listings").select("id").eq("title", name).execute()
    if listing_id.data:
        listing_id = listing_id.data[0]["id"]
    else:
        return {"error": "Listing not found."}
    print(
        f"[Tool Start] 'check_availability' for session {session_id} with args: listing_id={listing_id}, check_in={check_in}, check_out={check_out}"
    )
    # --- Validate Inputs ---
    if not listing_id:
        return {"error": "Missing listing ID for availability check."}
    if not check_in or not check_out:
        return {"error": "Missing check-in or check-out date for availability check."}

    try:
        # Basic date validation and check order
        date_in = datetime.date.fromisoformat(check_in)
        date_out = datetime.date.fromisoformat(check_out)
        if date_in >= date_out:
            return {
                "error": "Check-out date must be after check-in date.",
                "check_in": check_in,
                "check_out": check_out,
            }
    except ValueError:
        return {
            "error": "Invalid date format provided. Please use YYYY-MM-DD.",
            "check_in": check_in,
            "check_out": check_out,
        }

    is_available = False
    error_message = None
    overlapping_booking_count = 0
    try:
        response = (
            supabase.table("bookings")
            .select("id", count="exact")
            .eq("listing_id", str(listing_id))
            .lt("check_out", check_out)
            .gt("check_in", check_in)
            .execute()
        )

        print(f"[Tool Info] Supabase overlap check response: count={response.count}")
        overlapping_booking_count = response.count
        if overlapping_booking_count == 0:
            is_available = True

    except Exception as e:
        print(f"ERROR during Supabase availability check: {e}")
        traceback.print_exc()
        error_message = "Database error checking availability."

    print(
        f"[Tool End] 'check_availability'. Listing {listing_id} available ({check_in} to {check_out}): {is_available}"
    )

    result = {
        "listing_id": str(listing_id),
        "check_in": check_in,
        "check_out": check_out,
        "is_available": is_available,
        "conflicting_bookings_found": overlapping_booking_count,
    }
    if error_message:
        result["error"] = error_message

    # After checking availability, if available, calculate price
    if is_available:
        # Get listing details including price
        listing_response = (
            supabase.table("listings")
            .select("price_per_night, title")
            .eq("id", listing_id)
            .execute()
        )
        listing_details = listing_response.data[0] if listing_response.data else {}

        price_per_night = listing_details.get("price_per_night")

        if price_per_night:
            # Calculate nights
            check_in_date = datetime.date.fromisoformat(check_in)
            check_out_date = datetime.date.fromisoformat(check_out)
            nights = (check_out_date - check_in_date).days
            total_price = price_per_night * nights

            # Update state with selected listing
            state = await load_conversation_state(session_id)
            current_info = state.get("info", {})
            current_info["selected_listing_id"] = listing_id
            current_info["selected_listing_title"] = listing_details.get("title")
            current_info["total_price"] = total_price
            await save_conversation_state(
                session_id, current_info, state.get("history", [])
            )

            result["total_price"] = total_price
            result["listing_title"] = listing_details.get("title")

    if is_available:
        # Update state with selected listing
        state = await load_conversation_state(session_id)
        current_info = state.get("info", {})

        # Make sure these are being set
        current_info["selected_listing_id"] = listing_id
        current_info["selected_listing_title"] = listing_details.get("title")

        # Save state
        await save_conversation_state(
            session_id, current_info, state.get("history", [])
        )

    return result


# --- Tool Schema Definition (Dictionary Format) ---
check_availability_tool_schema = {
    "name": "check_availability",
    "description": "Checks if a specific listing ('listing_id') is available for booking between the check-in and check-out dates. Retrieves dates from conversation state if not provided.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "name": {
                "type": "STRING",
                "description": "the name of the listing choose by the user .",
            },
            "check_in": {
                "type": "STRING",
                "description": "Optional. The desired check-in date (YYYY-MM-DD). If omitted, uses date from conversation state.",
            },
            "check_out": {
                "type": "STRING",
                "description": "Optional. The desired check-out date (YYYY-MM-DD). If omitted, uses date from conversation state.",
            },
        },
        "required": ["name", "check_in", "check_out"],
    },
}
