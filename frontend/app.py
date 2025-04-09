# streamlit_app.py
import streamlit as st
import requests
import os
from dotenv import load_dotenv
import uuid
# Make sure ExtractedInfo is importable or defined here if needed for type hinting/parsing
# from somewhere import ExtractedInfo # Or define a minimal version here

load_dotenv() # Load environment variables from .env file

FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000") # Get from .env or default

st.title("Airbnb Reservation Chatbot")

# Initialize session state if it doesn't exist
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = [] # For displaying chat messages
    # st.session_state.booking_info = None # Explicitly track booking info state if needed

st.info(f"Session ID: {st.session_state.session_id}") # Display session ID for debugging

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("How can I help with your booking?"):
    # Add user message to display history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare request payload
    payload = {
        "session_id": st.session_state.session_id,
        "message": prompt
    }

    ai_response_text = "Error: Could not get response from backend." # Default error
    booking_info_updated = None # Track if booking info was updated

    # Call FastAPI backend
    try:
        response = requests.post(f"{FASTAPI_URL}/chat", json=payload)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()
        ai_response_text = response_data.get("response", "Sorry, I received an empty response.")

        # --- Process updated booking info ---
        updated_info_dict = response_data.get("updated_info")
        if updated_info_dict is not None:
             # Store the dictionary directly or parse into a Pydantic model if needed frontend-side
             st.session_state.booking_info = updated_info_dict
             booking_info_updated = True
             print(f"Streamlit received updated booking info: {st.session_state.booking_info}") # Debugging
        else:
             # If backend didn't return updated_info, keep existing st.session_state.booking_info
             pass


    except requests.exceptions.ConnectionError as e:
        ai_response_text = f"Connection Error: Could not connect to the backend at {FASTAPI_URL}. Please ensure it's running."
        st.error(ai_response_text)
    except requests.exceptions.Timeout as e:
        ai_response_text = "Error: The request to the backend timed out."
        st.error(ai_response_text)
    except requests.exceptions.RequestException as e:
        ai_response_text = f"Request Error: {e}"
        st.error(ai_response_text)
    except Exception as e:
        ai_response_text = f"An unexpected error occurred: {e}"
        st.error(ai_response_text) # Display error in Streamlit UI

    # Add assistant response to display history
    st.session_state.messages.append({"role": "assistant", "content": ai_response_text})

    # Display assistant response
    with st.chat_message("assistant"):
        st.markdown(ai_response_text)
        # Optionally display the updated info for debugging
        # if booking_info_updated:
        #    st.caption(f"Debug - Updated Info: {st.session_state.booking_info}")