# app/tools/booking_tools.py
from typing import Optional, Dict, Any, List
# Import needed schemas and redis functions
from ..schemas.chatschemas import ExtractedInfo, Message
from ..config.redis import load_conversation_state, save_conversation_state

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

