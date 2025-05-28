# RBNB Streamlit Booking Assistant

A conversational AI-powered booking assistant for accommodation search and reservation, similar to Airbnb. Built with FastAPI (backend), Streamlit (frontend), Gemini LLM, Redis (for chat state), and Supabase (for listings, users, and bookings).

---

## Features
- **Conversational AI**: Natural chat interface for users to search, refine, and book accommodations.
- **Tool-Calling LLM**: Uses Gemini to call backend tools for search, booking, user management, and availability checks.
- **Supabase Integration**: Stores listings, users, and bookings in a Postgres database via Supabase.
- **Redis State**: Maintains chat and booking state for each session.
- **Streamlit Frontend**: Modern, interactive UI for users to chat and view results.

---

## Project Structure

```
rbnb_streamlit_app/
├── compose.yml           # Docker Compose for Redis
├── backend/
│   ├── main.py           # FastAPI app (API endpoints, chat logic)
│   ├── config/           # Configs for Gemini, Redis, Supabase
│   ├── schemas/          # Pydantic models for chat, listings, etc.
│   ├── tools/            # Tool functions (search, booking, user, availability)
│   ├── utils/            # Logging and helpers
│   └── ...
├── frontend/
│   └── app.py            # Streamlit UI
└── README.md             # This file
```

---

## Quickstart

### 1. Prerequisites
- Python 3.10+
- Redis (via Docker Compose)
- Supabase project (with tables: `users`, `listings`, `bookings`)
- Google Gemini API key

### 2. Setup

1. **Clone the repo**
2. **Configure environment variables** in `.env` (see backend/config/supabase.py for required keys)
3. **Start Redis**:
   ```bash
   docker compose up -d
   ```
4. **Install backend dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
5. **Run FastAPI backend**:
   ```bash
   fastapi dev main.py
   ```
6. **Install frontend dependencies**:
   ```bash
   cd ../frontend
   pip install -r requirements.txt
   ```
7. **Run Streamlit frontend**:
   ```bash
   streamlit run app.py
   ```

---

## How It Works

- **User chats** with the assistant in the Streamlit UI.
- **Gemini LLM** interprets the message and calls backend tools (search, update booking, check availability, get/create user, create booking) as needed.
- **Backend tools** interact with Supabase (for data) and Redis (for state).
- **State** (user, listing, booking info) is persisted in Redis for each session.
- **Frontend** displays search results, booking confirmations, and chat history.

---

## Tooling & API

- **update_booking_parameters**: Update or record booking details (destination, dates, guests).
- **search_listings**: Find listings matching user criteria.
- **check_availability**: Check if a listing is available for given dates.
- **get_or_create_user**: Find or create a user profile.
- **create_booking**: Finalize a booking with all required info.

---

## Customization
- Add more tools in `backend/tools/` as needed.
- Extend schemas in `backend/schemas/` for richer data.
- Update the system prompt in `backend/config/gemini.py` to change assistant behavior.

---

## License
MIT
