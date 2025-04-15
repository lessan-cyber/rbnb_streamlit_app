# streamlit_app.py
import streamlit as st
import requests
import os
from dotenv import load_dotenv
import uuid
# Assuming ExtractedInfo is not directly needed in frontend state for now
# We primarily care about the search results list

load_dotenv() # Load environment variables from .env file

FASTAPI_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000") # Get from .env or default

st.title("Airbnb Reservation Chatbot")

# --- Session State Initialization ---
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    # 'messages' will store dicts like {"role": "user", "content": "hello"}
    # or {"role": "assistant", "content": "Hi!", "listings": [...]}
    st.session_state.messages = []
    # st.session_state.booking_info = None # Store booking info state if needed frontend-side

# Display session ID for debugging if desired
# st.info(f"Session ID: {st.session_state.session_id}")

# --- Display Chat History (Including Past Listings) ---
st.write("--- Chat History ---") # Add a separator for clarity
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # Display the text content of the message
        st.markdown(message["content"])

        # <-- MODIFIED: Check if this past assistant message had listings attached -->
        if message["role"] == "assistant" and "search_results" in message and message["search_results"]:
            st.write("_(Suggested listings from this message)_") # Indicate these are from history
            num_listings = len(message["search_results"])
            max_cols = 3 # Max columns for displaying listings side-by-side
            cols = st.columns(min(num_listings, max_cols))
            for i, listing in enumerate(message["search_results"]):
                col_index = i % max_cols
                with cols[col_index]:
                    with st.container(border=True):
                        if listing.get("image_url"):
                            st.image(listing["image_url"], caption=listing.get("title", ""), use_column_width=True)
                        else:
                            st.caption("[No Image]")
                        st.subheader(listing.get("title", "N/A"))
                        details = []
                        if listing.get("max_guests"): details.append(f"Sleeps {listing['max_guests']}")
                        if listing.get("bedrooms"): details.append(f"{listing['bedrooms']} BR")
                        st.caption(" | ".join(details))
                        if listing.get("price_per_night") is not None:
                            st.write(f"**${listing['price_per_night']:.2f}** / night")
            if num_listings > max_cols:
                st.caption(f"_(Displaying {max_cols} of {num_listings} listings from this message)_")
            # Add a small separator after historical listings
            st.markdown("---", unsafe_allow_html=True) # Use markdown for a subtle line


# --- Handle User Input ---
if prompt := st.chat_input("How can I help with your booking?"):
    # Add user message to state and display immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- Call Backend API ---
    payload = {
        "session_id": st.session_state.session_id,
        "message": prompt
    }
    ai_response_text = "Error: Could not get response from backend." # Default error message
    search_results_list = None # Variable to hold listings for THIS turn
    booking_info_updated = False # Track if booking parameters changed

    try:
        response = requests.post(f"{FASTAPI_URL}/chat", json=payload)
        response.raise_for_status() # Check for HTTP errors

        response_data = response.json()
        print(response_data) # Debugging: Print the entire response data
        ai_response_text = response_data.get("response", "Sorry, I received an empty response.")

        # <-- NEW: Extract search results if they exist -->
        search_results_list = response_data.get("search_results") # This will be None or a list of dicts
        print(search_results_list)
        # Process updated booking info (optional, as backend manages main state)
        updated_info_dict = response_data.get("updated_info")
        if updated_info_dict is not None:
             st.session_state.booking_info = updated_info_dict # Update local copy if needed
             booking_info_updated = True
             # print(f"Streamlit received updated booking info: {st.session_state.booking_info}")

    except requests.exceptions.ConnectionError:
        ai_response_text = f"Connection Error: Cannot connect to backend ({FASTAPI_URL}). Is it running?"
        st.error(ai_response_text) # Show error prominently
    except requests.exceptions.RequestException as e:
        ai_response_text = f"Request Error: {e}"
        st.error(ai_response_text)
    except Exception as e:
        ai_response_text = f"An unexpected error occurred: {e}"
        st.error(ai_response_text)

    # --- Prepare and Store Assistant Message (including listings) ---
    # Create the message dictionary first
    assistant_message_data = {
        "role": "assistant",
        "content": ai_response_text
    }
    # <-- NEW: Attach listings to the message data if they exist -->
    if search_results_list and isinstance(search_results_list, list):
        assistant_message_data["listings"] = search_results_list

    # Add the complete message data (text + maybe listings) to history
    st.session_state.messages.append(assistant_message_data)

    # --- Display Assistant Response and Listings for THIS Turn ---
    with st.chat_message("assistant"):
        # Display the AI's text response
        st.markdown(ai_response_text)

        # <-- NEW: Display listings if they were returned in THIS response -->
        if search_results_list and isinstance(search_results_list, list):
            st.write("--- Suggested Listings ---") # Add a header
            num_results = len(search_results_list)
            if num_results > 0:
                max_cols_display = 3 # Max columns for display
                cols = st.columns(min(num_results, max_cols_display)) # Create columns

                for i, listing in enumerate(search_results_list):
                    col_index = i % max_cols_display
                    with cols[col_index]: # Place each listing in a column
                        with st.container(border=True): # Use container with border for card effect
                            # Display Image if URL exists
                            if listing.get("image_url"):
                                st.image(listing["image_url"], caption=listing.get("title", ""), use_column_width=True)
                            else:
                                st.caption("[No Image Available]") # Placeholder

                            # Display Title
                            st.subheader(listing.get("title", "No Title Provided"))

                            # Display Key Details Concisely
                            details = []
                            if listing.get("max_guests"): details.append(f"Sleeps {listing['max_guests']}")
                            if listing.get("bedrooms"): details.append(f"{listing['bedrooms']} BR")
                            if listing.get("city"): details.append(f"{listing['city']}")
                            st.caption(" | ".join(details)) 

                            # Display Price
                            if listing.get("price_per_night") is not None:
                                st.write(f"**${listing['price_per_night']:.2f}** / night")
                            else:
                                st.write("Price N/A")

                            # Add Description (Optional - maybe in an expander)
                            desc = listing.get("description")
                            if desc:
                                with st.expander("Description"):
                                    st.write(desc)

                            # Add Select Button (for future interaction)
                            st.button("Select", key=f"select_{listing.get('id')}_{st.session_state.session_id}") # Use unique key

                if num_results > max_cols_display:
                     st.caption(f"Showing {max_cols_display} of {num_results} suggestions.")

            else:
                # If the list exists but is empty
                st.write("No specific listings matched your current criteria.")

            st.write("---") # Separator after listings display

        # Optionally display booking info for debugging
        # if booking_info_updated:
        #    st.caption(f"Debug - Updated Booking Info: {st.session_state.booking_info}")