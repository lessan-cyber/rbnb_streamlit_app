from typing import Optional, Dict, Any, List
from ..config.supabase import get_supabase_client
from ..schemas.chatschemas import ExtractedInfo, Message
from ..config.redis import load_conversation_state, save_conversation_state
import logging
import uuid
from datetime import datetime

# The actual Python function that implements the tool's logic
async def update_booking_parameters(session_id: str,
                                destination: Optional[str] = None,
                                check_in: Optional[str] = None,
                                check_out: Optional[str] = None,
                                guests: Optional[int] = None) -> Dict[str, Any]: # Return a dict for Gemini
    """
    ASYNC function. Updates booking parameters in Redis for the session ID.
    Loads current state, updates with non-null values, saves back,
    and returns the full updated state as a dictionary.
    """
    print(f"[Tool Start] 'update_booking_parameters' for session {session_id} with args: dest={destination}, in={check_in}, out={check_out}, guests={guests}")

    # --- Load current state ---
    # MUST await the async function
    current_state = await load_conversation_state(session_id)
    current_info: Optional[ExtractedInfo] = current_state.get("info")
    # History is loaded but not modified by this function, just passed to save_conversation_state
    history: List[Message] = current_state.get("history", [])

    if current_info is None:
        print(f"[Tool Info] No existing info found for session {session_id}, creating new.")
        current_info = ExtractedInfo() # Start with a fresh Pydantic model

    # --- Update parameters ---
    updated_values = current_info.model_dump() # Start with existing values
    if destination is not None:
        updated_values["destination"] = destination
    if check_in is not None:
        updated_values["check_in"] = check_in
    if check_out is not None:
        updated_values["check_out"] = check_out
    if guests is not None:
        updated_values["guests"] = guests

    # Create the updated Pydantic model
    updated_info_model = ExtractedInfo(**updated_values)
    print(f"[Tool Info] Updated info for session {session_id}: {updated_info_model}")

    # --- Save updated state ---
    # MUST await the async function
    await save_conversation_state(session_id, updated_info_model, history)

    print(f"[Tool End] 'update_booking_parameters' finished for session {session_id}")
    # Return the updated info as a dictionary, as expected by Gemini function response part
    return updated_info_model.model_dump(mode='json')


# --- Tool Schema Definition (Dictionary Format) ---
# This dictionary describes the tool to the Gemini model.
# It follows the OpenAPI Specification format.
update_booking_tool_schema = {
    "name": "update_booking_parameters", # MUST match the function name and the key in available_tools
    "description": "Updates or records booking parameters like destination, check-in date, check-out date, or number of guests based on user input. Use this whenever the user provides any of these specific details.",
    "parameters": {
        "type": "OBJECT", 
        "properties": {
            "destination": {
                "type": "STRING",
                "description": "The city, region, or specific area the user wants to book accommodation in (e.g., 'Paris', 'Soho, London')."
            },
            "check_in": {
                "type": "STRING",
                "description": "The user's desired check-in date, ideally formatted as YYYY-MM-DD (e.g., '2025-07-15')."
            },
            "check_out": {
                "type": "STRING",
                "description": "The user's desired check-out date, ideally formatted as YYYY-MM-DD (e.g., '2025-07-22')."
            },
            "guests": {
                "type": "INTEGER",
                "description": "The total number of guests requiring accommodation (e.g., 2)."
            }
        },
        "required": [] # List any parameters Gemini MUST provide if it calls the function. Often empty if all are optional updates.
    }
}



async def create_booking(
    session_id: str,
    user_id: str,
    listing_id: str,
    check_in: str,
    check_out: str,
    num_guests: int,
    total_price: float
) -> Dict[str, Any]:
    """
    Creates a booking reservation in the database.
    
    Args:
        session_id: Current conversation session ID
        user_id: ID of user making the booking (from get_or_create_user tool)
        listing_id: ID of the listing being booked
        check_in: Check-in date (YYYY-MM-DD format)
        check_out: Check-out date (YYYY-MM-DD format)
        num_guests: Number of guests for the booking
        total_price: Total price of the booking
        
    Returns:
        Dictionary with booking details including confirmation status
    """
    booking_id = None
    status = "error"
    error_message = None
    
    logging.info(f"Creating booking for User:{user_id}, Listing:{listing_id}, "
                f"Dates:{check_in} to {check_out}, Guests:{num_guests}")
    
    try:
        # Basic validation
        if not user_id:
            return {
                "status": "error",
                "message": "User ID is required. Please collect user information first.",
                "booking_id": None
            }
        
        if not listing_id:
            return {
                "status": "error",
                "message": "Listing ID is required.",
                "booking_id": None
            }
            
        # Format dates for database
        try:
            # Validate date format
            check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
            check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
            
            if check_in_date >= check_out_date:
                return {
                    "status": "error",
                    "message": "Check-out date must be after check-in date.",
                    "booking_id": None
                }
                
        except ValueError:
            return {
                "status": "error",
                "message": "Invalid date format. Use YYYY-MM-DD.",
                "booking_id": None
            }
            
        # Create a unique booking ID
        booking_id = str(uuid.uuid4())
        
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Double-check availability before booking
        availability_check = (
            supabase.table("bookings")
            .select("id")
            .eq("listing_id", listing_id)
            .gte("check_out", check_in)
            .lte("check_in", check_out)
            .execute()
        )
        
        if availability_check.data and len(availability_check.data) > 0:
            return {
                "status": "unavailable",
                "message": "This listing is no longer available for the selected dates.",
                "booking_id": None
            }
            
        # Create booking record
        booking_data = {
            "id": booking_id,
            "user_id": user_id,
            "listing_id": listing_id,
            "check_in": check_in,
            "check_out": check_out,
            "num_guests": num_guests,
            "total_price": total_price,
            "booking_date": datetime.now().isoformat(),
            "status": "confirmed"  # Or "pending" if you have a multi-step process
        }
        
        booking_response = supabase.table("bookings").insert(booking_data).execute()
        
        if booking_response.data:
            status = "success"
            
            # Get listing details for the response
            listing_response = (
                supabase.table("listings")
                .select("title, city, image_url")
                .eq("id", listing_id)
                .execute()
            )
            
            listing_details = listing_response.data[0] if listing_response.data else {}
            
            # Return success response with details
            return {
                "status": "success",
                "booking_id": booking_id,
                "user_id": user_id,
                "listing_id": listing_id,
                "listing_title": listing_details.get("title", "Unknown listing"),
                "listing_city": listing_details.get("city", ""),
                "check_in": check_in,
                "check_out": check_out,
                "num_guests": num_guests,
                "total_price": total_price,
                "message": "Booking confirmed successfully!"
            }
        else:
            error_message = "Failed to create booking record"
            
    except Exception as e:
        error_message = str(e)
        logging.error(f"Error creating booking: {e}")
        
    # Return error response if we got here
    return {
        "status": "error",
        "message": error_message or "An error occurred during booking",
        "booking_id": booking_id
    }

# Define the tool schema for the AI
create_booking_tool_schema = {
    "name": "create_booking",
    "description": "Creates a booking reservation after user confirms they want to book a specific listing. Should ONLY be used after get_or_create_user has been successfully called and the user has explicitly confirmed they want to book.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "user_id": {
                "type": "STRING",
                "description": "The user ID obtained from the get_or_create_user tool call."
            },
            "listing_id": {
                "type": "STRING",
                "description": "ID of the listing the user wants to book."
            },
            "check_in": {
                "type": "STRING",
                "description": "Check-in date in YYYY-MM-DD format."
            },
            "check_out": {
                "type": "STRING",
                "description": "Check-out date in YYYY-MM-DD format."
            },
            "num_guests": {
                "type": "INTEGER",
                "description": "Number of guests for the booking."
            },
            "total_price": {
                "type": "NUMBER",
                "description": "Total price for the entire stay."
            }
        },
        "required": ["user_id", "listing_id", "check_in", "check_out", "num_guests", "total_price"]
    }
}


