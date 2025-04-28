import redis.asyncio as redis
from ..schemas.chatschemas import ExtractedInfo, Message
import json
from typing import Any, Dict, List, Optional

STATE_EXPIRY_SECONDS = 7200


async def get_redis_connection():
    # Create a Redis connection. The service name "redis" is used as the host.
    pool = redis.ConnectionPool(host="localhost", port=6379)
    client = redis.Redis(connection_pool=pool)
    return client


async def test_redis_connection():
    """Test the Redis connection."""
    client = await get_redis_connection()
    try:
        await client.ping()
        print("Redis connection is alive.")
    except redis.ConnectionError:
        print("Redis connection is not alive.")
    finally:
        await client.close()


async def close_connection():
    try:
        client = await get_redis_connection()
        if client:
            await client.close()
            print("Redis connection closed.")
    except Exception as e:
        print(f"Error closing Redis connection: {e}")


async def save_conversation_state(
    session_id: str,
    info: Optional[Any],
    history: List[Message],
    user_id: Optional[str] = None,
    listing: Optional[Dict[str, Any]] = None,
):
    if not session_id:
        print("Error: Attempted to save state with empty session_id.")
        return

    if info is None:
        info_dict = None
    elif hasattr(info, "model_dump"):
        info_dict = info.model_dump(mode="json")
    elif hasattr(info, "dict"):
        info_dict = info.dict()
    else:
        info_dict = info

    # Handle history items similarly
    history_list = []
    for msg in history:
        if hasattr(msg, "model_dump"):
            history_list.append(msg.model_dump(mode="json"))
        elif hasattr(msg, "dict"):
            history_list.append(msg.dict())
        else:
            history_list.append(msg)
    state = {
        "info": info_dict,
        "history": history_list,
        "user_id": user_id,
        "listing": listing,
    }
    print(f"Saving state for session: {session_id} (UserID: {user_id})")
    state_json = json.dumps(state)

    try:
        client = await get_redis_connection()
        await client.setex(f"session:{session_id}", STATE_EXPIRY_SECONDS, state_json)
        print(f"Saved state for session: {session_id} (UserID: {user_id})")
    except Exception as e:
        print(f"Error saving state to Redis for session {session_id}: {e}")


async def load_conversation_state(session_id: str) -> Dict[str, Any]:
    """Loads conversation state from Redis, including user_id."""
    default_state = {
        "info": None,
        "history": [],
        "user_id": None,
        "listing": None,
    }
    try:
        client = await get_redis_connection()
        state_json_bytes = await client.get(f"session:{session_id}")

        if state_json_bytes:
            print(f"Loaded state for session: {session_id}")
            state_data = json.loads(state_json_bytes.decode("utf-8"))

            info_data = state_data.get("info")
            history_data = state_data.get("history", [])
            loaded_user_id = state_data.get("user_id")
            loaded_info = ExtractedInfo(**info_data) if info_data else None
            loaded_history = [
                Message(**msg) for msg in history_data if isinstance(msg, dict)
            ]

            print(f"Loaded UserID: {loaded_user_id}")

            return {
                "info": loaded_info,
                "history": loaded_history,
                "user_id": loaded_user_id,
                "listing": state_data.get("listing"),
            }
        else:
            return default_state
    except Exception as e:
        print(f"Error loading state from Redis for session {session_id}: {e}")
        return default_state
