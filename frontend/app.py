# frontend/app.py
import streamlit as st

st.title("RBNB Reservation System (Prototype)")
st.write("Welcome to our prototype reservation system!")

search_term = st.text_input("Enter a location or property name:")
if search_term:
    st.write(f"You searched for: {search_term}")
    # In the future, this is where you'd interact with the backend