# app/config/supabase.py
import os
from supabase import create_client
from supabase.client import Client
from dotenv import load_dotenv
from typing import Optional
load_dotenv()

supabase_url: str = os.environ.get("SUPABASE_URL")
supabase_key: str = os.environ.get("SUPABASE_ANON_KEY")

supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """Initializes and returns the Supabase client."""
    global supabase_client
    if supabase_client is None:
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase URL or Key not found in environment variables.")
        try:
            print("Initializing Supabase client...")
            supabase_client = create_client(supabase_url, supabase_key)
            print("Supabase client initialized.")
            # You could potentially test the connection here if needed
        except Exception as e:
            print(f"FATAL: Error initializing Supabase client: {e}")
            raise ConnectionError("Failed to initialize Supabase client") from e
    return supabase_client

# You can call get_supabase_client() once at startup or lazily when needed.
# For simplicity now, we'll call it within the search function.

# supabase_connection_testing
def test_supabase_connection() -> bool:
    """Tests the connection to Supabase."""
    try:
        client = get_supabase_client()
        # Perform a simple query to test the connection
        response = client.from_("listings").select("*").limit(1).execute()
        if getattr(response, 'error', None):
            print("Supabase connection error:", response.error)
            return False
        else:
            print("Supabase connected successfully. Data retrieved:", response.data)
            return True
    except Exception as e:
        print(f"Error testing Supabase connection: {e}")
        return False