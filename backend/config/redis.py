import redis.asyncio as redis
from ..schemas.chatschemas import ExtractedInfo, Message
import json
from typing import Any, Dict, List, Optional

STATE_EXPIRY_SECONDS = 7200

async def get_redis_connection():
    # Create a Redis connection. The service name "redis" is used as the host.
    pool = redis.ConnectionPool(host='localhost', port=6379)
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
        client = await get_redis_connection() # Assume this returns the client
        if client:
            await client.close() # Close the connection/pool
            print("Redis connection closed.")
    except Exception as e:
        print(f"Error closing Redis connection: {e}")

async def save_conversation_state(session_id: str, info: Optional[ExtractedInfo], history: List[Message]):
    """Saves the conversation state (info and history) to Redis."""
    if not session_id:
        print("Error: Attempted to save state with empty session_id.")
        return

    # Prepare state dictionary using Pydantic's model_dump for proper serialization
    state = {
        "info": info.model_dump(mode='json') if info else None, # mode='json' ensures types like datetime are handled if added
        "history": [msg.model_dump(mode='json') for msg in history]
    }
    state_json = json.dumps(state)

    try:
        client = await get_redis_connection()
        # Use setex to automatically set expiration
        await client.setex(f"session:{session_id}", STATE_EXPIRY_SECONDS, state_json)
        print(f"Saved state for session: {session_id}")
    except Exception as e:
        print(f"Error saving state to Redis for session {session_id}: {e}")
        # Optionally re-raise or handle more specifically

async def load_conversation_state(session_id: str) -> Dict[str, Any]:
    """Loads conversation state from Redis, returning Pydantic models."""
    if not session_id:
        print("Error: Attempted to load state with empty session_id.")
        return {"info": None, "history": []}

    default_state = {"info": None, "history": []}
    try:
        client = await get_redis_connection()
        state_json_bytes = await client.get(f"session:{session_id}")

        if state_json_bytes:
            print(f"Loaded state for session: {session_id}")
            state_data = json.loads(state_json_bytes.decode('utf-8')) # Decode bytes to string

            # Re-parse into Pydantic models for type safety and validation
            info_data = state_data.get("info")
            history_data = state_data.get("history", [])

            loaded_info = ExtractedInfo(**info_data) if info_data else None
            # Ensure history items are valid before creating Message objects
            loaded_history = []
            for msg_data in history_data:
                if isinstance(msg_data, dict) and 'role' in msg_data and 'content' in msg_data:
                     loaded_history.append(Message(**msg_data))
                else:
                    print(f"Warning: Skipping invalid message data in history for session {session_id}: {msg_data}")


            return {"info": loaded_info, "history": loaded_history}
        else:
            print(f"No state found for session: {session_id}")
            return default_state
    except Exception as e:
        print(f"Error loading state from Redis for session {session_id}: {e}")
        return default_state # Return default on error
