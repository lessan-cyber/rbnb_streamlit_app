from typing import Dict, Any, List, Optional
from ..config.supabase import get_supabase_client
from ..schemas.chatschemas import Message, ExtractedInfo
import traceback
import uuid
from ..config.redis import load_conversation_state, save_conversation_state


async def get_or_create_user(
    session_id: str,
    email: str,
    full_name: str,  # <-- Make optional with default None
    phone_number: Optional[str] = None,  # Already optional, matches schema if added
) -> Dict[str, Any]:
    """
    Finds a user by email. If not found, creates a new user.
    Handles optional full_name and phone_number.
    Returns user details including their ID and status ('found' or 'created').
    Also updates the user_id in the conversation state in Redis.
    """

    if not email or "@" not in email or "." not in email:
        return {"status": "error", "error_message": "Invalid email address provided."}

    user_id = None
    status = "error"
    error_message = None
    final_user_data = {}

    try:
        supabase = get_supabase_client()
        # Instead of using eq filter which might cause the 406 error
        response = (
            supabase.table("users")
            .select("id, email, full_name")
            .filter("email", "eq", email)  # Use filter instead of eq
            .execute()
        )

        if not response or hasattr(response, "error") and response.error:
            return {
                "status": "error",
                "message": "Failed to fetch user data",
                "user_id": None,
            }
        existing_user = response.data

        if existing_user and len(existing_user) > 0:
            # Access the first element in the list
            user_data = existing_user[0]
            user_id = user_data.get("id")
            print(f"[Tool Info] User found: ID={user_id}")
            full_name = user_data.get("full_name")
            status = "found"
            final_user_data = user_data
        else:
            insert_data = {"email": email}
            insert_data["full_name"] = full_name
            if phone_number:
                insert_data["phone_number"] = phone_number

            insert_response = supabase.table("users").insert(insert_data).execute()
            if insert_response.data and len(insert_response.data) > 0:
                new_user = insert_response.data[0]
                user_id = new_user.get("id")
                print(f"[Tool Info] New user created: ID={user_id}")
                status = "created"
                final_user_data = new_user
            else:
                error_message = "Failed to create new user profile in database."

        if user_id:
            state = await load_conversation_state(session_id)
            await save_conversation_state(
                session_id=session_id,
                info=state.get("info"),
                history=state.get("history", []),
                user_id=user_id,  # Pass the user ID here
                listing=state.get("listing"),
            )

        else:
            print(
                "[Tool Warn] No user_id obtained, Redis state not updated with user_id."
            )

    except Exception as e:
        print(f"ERROR during get_or_create_user execution: {e}")
        traceback.print_exc()
        status = "error"
        error_message = "An internal error occurred while processing user details."

    print(f"[Tool End] 'get_or_create_user'. Status: {status}, UserID: {user_id}")
    # --- Return Result ---
    result = {
        "status": status,
        "user_id": str(user_id) if user_id else None,
        "email": email,
        "full_name": full_name,
    }
    if error_message:
        result["error_message"] = error_message
    print(f"[Tool Result] {result}")
    return result


# --- Tool Schema Definition (Dictionary Format) ---
get_or_create_user_tool_schema = {
    "name": "get_or_create_user",
    "description": "Looks up a user by their email address. If the user doesn't exist, creates a new user record with the provided email and optional full name or phone number. Returns the user's ID and status.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "email": {"type": "STRING", "description": "The user's email address."},
            "full_name": {
                "type": "STRING",
                "description": "Optional. The user's full name.",
            },
            "phone_number": {
                "type": "STRING",
                "description": "Optional. The user's phone number.",
            },
        },
        "required": ["email", "full_name"],
    },
}
