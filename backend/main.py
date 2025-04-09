# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai # Use the newer package namespace if possible
import traceback # Import traceback for better error logging
from .config.gemini import connection_to_gemini
from .schemas.chatschemas import ChatRequest, ChatResponse, ExtractedInfo, Message
from .config.redis import get_redis_connection, load_conversation_state, save_conversation_state, test_redis_connection, close_connection
from .tools.booking_tools import update_booking_parameters, update_booking_tool_schema , available_tools

# --- Environment & CORS Setup ---
load_dotenv()
origins = [
    os.getenv("FRONTEND_URL", "http://localhost:8501"), # Get from env or default
    "http://localhost",
]
app = FastAPI(title="Booking Assistant API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


gemini_model = None # Initialize as None

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    await test_redis_connection() # Test the Redis connection


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    await close_connection() 

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handles incoming chat messages, manages state, interacts with Gemini, and uses tools."""

    if not gemini_model:
        raise HTTPException(status_code=503, detail="Gemini model is not available.")

    session_id = request.session_id
    user_message_content = request.message
    print(f"\n--- New Request ---")
    print(f"Session ID: {session_id}")
    print(f"User Message: {user_message_content}")

    # 1. Load State
    print("Loading conversation state...")
    state = await load_conversation_state(session_id)
    current_info: Optional[ExtractedInfo] = state.get("info")
    chat_history: List[Message] = state.get("history")
    print(f"Loaded Info: {current_info}")

    # 2. Prepare History for Gemini API
    gemini_history_content: List[Dict[str, Any]] = []
    # *** REMOVE THE SYSTEM ROLE APPEND HERE ***
    # The system prompt is now handled by system_instruction during model init

    for msg in chat_history:
        # Map 'assistant' role to 'model' for the API
        role = "model" if msg.role == "assistant" else msg.role
        gemini_history_content.append({'role': role, 'parts': [{'text': msg.content}]})
        # Note: This history structure might need adjustment if you want the AI
        # to explicitly remember *past* function calls/responses within the history.
        # For now, it just includes user/model text turns.

    # Add the current user message
    gemini_history_content.append({'role': 'user', 'parts': [{'text': user_message_content}]})

    # --- Default Response Values ---
    ai_natural_response = "Sorry, something went wrong while processing your request."
    updated_info_for_response = current_info # Assume no change unless tool succeeds

    # --- Interaction Loop (Handles potential function calling) ---
    try:
        print("Sending request to Gemini (pass 1)...")
        # Pass the tool schema dictionary directly in the tools argument
        model  = await connection_to_gemini()
        response = await model.generate_content_async(
            contents=gemini_history_content, # Pass the history (NO system role)
            tools=[update_booking_tool_schema] # Pass the schema dictionary
        )

        # ... (Rest of the function call handling logic remains the same as previous correct version) ...
        # Extract the response part
        if not response.candidates:
            raise ValueError("Gemini response missing candidates.")
        response_part = response.candidates[0].content.parts[0]
        print(f"Gemini response (pass 1): {response_part}")

        # Check for function call request
        func_call = getattr(response_part, 'function_call', None)

        if func_call:
            function_name = func_call.name
            function_args = {key: value for key, value in func_call.args.items()}
            print(f"Function call requested: {function_name}({function_args})")

            # Execute the corresponding function
            if function_name in available_tools:
                tool_function = available_tools[function_name]
                function_args["session_id"] = session_id

                try:
                    print(f"Executing tool function: {function_name}...")
                    function_result_dict = await tool_function(**function_args) # Await async tool
                    print(f"Tool function executed. Result: {function_result_dict}")

                    # Prepare history for the second Gemini call
                    # Append model's request (containing the function call)
                    gemini_history_content.append({'role': 'model', 'parts': [response_part]})
                    # Append function execution result
                    gemini_history_content.append({
                        'role': 'function',
                        'parts': [{'function_response': {'name': function_name, 'content': function_result_dict}}]
                    })

                    print("Sending request to Gemini (pass 2 - after function execution)...")
                    second_response = await gemini_model.generate_content_async(
                        contents=gemini_history_content
                    )

                    if not second_response.candidates:
                         raise ValueError("Gemini response missing candidates on second call.")
                    ai_natural_response = second_response.candidates[0].content.parts[0].text
                    print(f"Gemini final response (post-tool): {ai_natural_response}")

                    # Update state from the function's result dict
                    updated_info_for_response = ExtractedInfo(**function_result_dict) if function_result_dict else current_info

                except Exception as tool_exec_error:
                    print(f"ERROR executing tool '{function_name}': {tool_exec_error}")
                    traceback.print_exc()
                    ai_natural_response = f"Sorry, I encountered an issue trying to update your booking details. Could you try again?"
                    updated_info_for_response = current_info

            else:
                print(f"ERROR: Gemini requested unknown function: {function_name}")
                ai_natural_response = "Sorry, I got a bit confused there. Could you rephrase?"
                updated_info_for_response = current_info

        else:
            # No function call -> Just Text Response
            ai_natural_response = response_part.text
            print(f"Gemini final response (no tool called): {ai_natural_response}")
            updated_info_for_response = current_info # State didn't change

    except Exception as gemini_error:
        print(f"ERROR during Gemini interaction or processing: {gemini_error}")
        traceback.print_exc()
        ai_natural_response = "I apologize, but I'm having trouble processing your request right now. Please try again in a moment."
        updated_info_for_response = current_info # Keep state before error

    # --- Save Final State ---
    final_history = chat_history + [
        Message(role="user", content=user_message_content),
        Message(role="assistant", content=ai_natural_response)
    ]
    print("Saving final conversation state...")
    # Ensure updated_info is a Pydantic model or None before saving
    await save_conversation_state(session_id, updated_info_for_response, final_history)
    print("--- Request End ---")

    # --- Return Response ---
    return ChatResponse(response=ai_natural_response, updated_info=updated_info_for_response)