# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import json
from typing import Dict, Any, List, Optional
import traceback
from .config.gemini import connection_to_gemini
from .schemas.chatschemas import (
    ChatRequest,
    ChatResponse,
    ExtractedInfo,
    Message,
    ListingResult,
)
from .config.redis import (
    get_redis_connection,
    load_conversation_state,
    save_conversation_state,
    test_redis_connection,
    close_connection,
)
from .tools import (
    available_tools,
    update_booking_tool_schema,
    update_booking_parameters,
    search_listings,
    search_tool_schema,
    check_availability,
    check_availability_tool_schema,
    get_or_create_user,
    get_or_create_user_tool_schema,
    create_booking,
    create_booking_tool_schema,
)
from .config.supabase import test_supabase_connection
from .utils import logger
from datetime import datetime
import time

# --- Environment & CORS Setup ---
load_dotenv()
origins = [
    os.getenv("FRONTEND_URL", "http://localhost:8501"),  # Get from env or default
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


gemini_model = None  # Initialize as None


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    await test_redis_connection()  # Test the Redis connection
    test_supabase_connection()  # Test the Supabase connection


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handles incoming chat messages, manages state, interacts with Gemini, and uses tools."""
    request_tracker = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": request.session_id,
        "functions_called": [],
        "start_time": time.time(),
    }
    logger.info(
        f"📩 NEW REQUEST | Session: {request.session_id} | Message: '{request.message}'"
    )
    model = (
        await connection_to_gemini()
    )  # Assuming this function returns the initialized model
    if not model:
        raise HTTPException(status_code=503, detail="Gemini model is not available.")

    session_id = request.session_id
    user_message_content = request.message

    state = await load_conversation_state(session_id)
    current_info: Optional[ExtractedInfo] = state.get("info")
    chat_history: List[Message] = state.get("history")

    # 2. Prepare History for Gemini API
    gemini_history_content: List[Dict[str, Any]] = []
    # Assuming system prompt is handled during model initialization via connection_to_gemini()
    for msg in chat_history:
        role = "model" if msg.role == "assistant" else msg.role
        gemini_history_content.append({"role": role, "parts": [{"text": msg.content}]})
    gemini_history_content.append(
        {"role": "user", "parts": [{"text": user_message_content}]}
    )

    # --- Default/Initialization for Response Variables ---
    ai_natural_response = "Sorry, something went wrong while processing your request."
    # Start assuming current info state unless update tool runs successfully
    updated_info_for_response: Optional[ExtractedInfo] = current_info
    # << Initialize variable to hold structured search results >>
    search_results_for_response: Optional[List[ListingResult]] = None
    # Initialize response dictionary to store booking information
    final_response = {}

    # --- Interaction Loop (Handles potential function calling) ---
    try:
        response = await model.generate_content_async(
            contents=gemini_history_content,
            tools=[
                update_booking_tool_schema,
                search_tool_schema,
                check_availability_tool_schema,
                get_or_create_user_tool_schema,
                create_booking_tool_schema,
            ],
        )
        logger.info(f"Gemini response received: {response}")
        if not response.candidates:
            raise ValueError("Gemini response missing candidates.")
        # Ensure parts exist before accessing
        if not response.candidates[0].content.parts:
            raise ValueError("Gemini response candidate missing parts.")
        response_part = response.candidates[0].content.parts[0]
        # print(f"Gemini response (pass 1): {response_part}")

        # Check for function call request
        func_call = getattr(response_part, "function_call", None)

        if func_call:
            function_name = func_call.name
            # Ensure args is a dict-like structure before converting
            function_args = {}
            if hasattr(func_call, "args"):
                function_args = {key: value for key, value in func_call.args.items()}
            logger.info(f"🔧 FUNCTION CALL | {function_name} | Args: {function_args}")
            request_tracker["functions_called"].append(
                {"name": function_name, "args": function_args, "status": "requested"}
            )

            if function_name in available_tools:
                tool_function = available_tools[function_name]
                function_args["session_id"] = session_id

                try:
                    logger.info(f"▶️ EXECUTING | {function_name}")
                    function_result_payload = await tool_function(**function_args)
                    tool_result_content_for_gemini = {}

                    if function_name == "update_booking_parameters":
                        logger.info(
                            f"✅ FUNCTION SUCCESS | {function_name} | Updated: {function_result_payload}"
                        )
                        print(
                            f"Processing result for {function_name}: {function_result_payload}"
                        )
                        if isinstance(function_result_payload, dict):
                            # Update the state variable for the final response
                            updated_info_for_response = ExtractedInfo(
                                **function_result_payload
                            )
                            # Content for Gemini is the dict itself
                            tool_result_content_for_gemini = function_result_payload
                        else:
                            print(
                                f"Warning: {function_name} did not return a dictionary."
                            )
                            # Keep original info state, send empty dict back to Gemini? Or error?
                            tool_result_content_for_gemini = {
                                "error": "Invalid tool result format"
                            }
                    elif function_name == "search_listings":
                        if isinstance(function_result_payload, list):
                            # 1. Prepare structured results for the frontend
                            validated_results = []
                            for item in function_result_payload:
                                if isinstance(item, dict):
                                    try:
                                        validated_results.append(ListingResult(**item))
                                    except Exception as parse_error:
                                        logger.warning(
                                            f"Skipping search result due to parsing error: {parse_error}"
                                        )
                                else:
                                    logger.warning(
                                        f"Item in search result is not a dictionary: {type(item)}"
                                    )

                            search_results_for_response = validated_results

                            # Log the success with more detail
                            if validated_results:
                                logger.info(
                                    f"✅ SEARCH SUCCESS | Found: {len(validated_results)} listings | "
                                    + f"Sample: {validated_results[0].city}, {validated_results[0].title}"
                                )
                            else:
                                logger.warning(
                                    f"⚠️ SEARCH RETURNED EMPTY | Args: {function_args}"
                                )

                            # 2. Prepare summary for Gemini with richer information
                            tool_result_content_for_gemini = {
                                "status": "success",
                                "listings_found_count": len(validated_results),
                                "listings_summary": [],
                            }

                            # Add more detailed listing information for the model to reference
                            for item in validated_results[
                                :3
                            ]:  # Limit to first 3 listings
                                listing_summary = {
                                    "title": item.title,
                                    "city": item.city,
                                    "price_per_night": f"${item.price_per_night:.2f}"
                                    if item.price_per_night
                                    else "Price not available",
                                    "max_guests": f"Up to {item.max_guests} guests"
                                    if item.max_guests
                                    else "Guest count not specified",
                                    "bedrooms": f"{item.bedrooms} bedrooms"
                                    if item.bedrooms
                                    else "Bedroom count not available",
                                    "description": item.description[:100] + "..."
                                    if item.description and len(item.description) > 100
                                    else item.description,
                                }
                                tool_result_content_for_gemini[
                                    "listings_summary"
                                ].append(listing_summary)

                        else:
                            print(f"Warning: {function_name} did not return a list.")
                            search_results_for_response = []  # Send empty list to frontend
                            tool_result_content_for_gemini = {
                                "status": "success",
                                "listings_found_count": 0,
                                "listings_summary": [],
                            }
                    elif function_name == "check_availability":
                        logger.info(
                            f"✅ FUNCTION SUCCESS | {function_name} | Result: {function_result_payload}"
                        )
                        if isinstance(function_result_payload, dict):
                            updated_info_for_response = ExtractedInfo(
                                **function_result_payload
                            )
                            tool_result_content_for_gemini = function_result_payload
                        else:
                            print(
                                f"Warning: {function_name} did not return a dictionary."
                            )
                            tool_result_content_for_gemini = {
                                "error": "Invalid tool result format"
                            }
                    elif function_name == "get_or_create_user":
                        logger.info(
                            f"✅ FUNCTION SUCCESS | {function_name} | Result: {function_result_payload}"
                        )
                        tool_result_content_for_gemini = (
                            function_result_payload  # Send result to Gemini
                        )
                        # Extract user_id from result to save in state later
                        if function_result_payload.get("status") in [
                            "found",
                            "created",
                        ]:
                            user_id_for_saving_state = function_result_payload.get(
                                "user_id"
                            )
                            print(
                                f"User ID {user_id_for_saving_state} obtained for session {session_id}"
                            )
                        else:
                            print(
                                f"Warning: {function_name} did not return a dictionary."
                            )
                            tool_result_content_for_gemini = {
                                "error": "Invalid tool result format"
                            }
                    elif function_name == "create_booking":
                        logger.info(
                            f"✅ FUNCTION SUCCESS | {function_name} | Result: {function_result_payload}"
                        )

                        # Format response for Gemini
                        if isinstance(function_result_payload, dict):
                            tool_result_content_for_gemini = function_result_payload

                            # Add booking info to response
                            if function_result_payload.get("status") == "success":
                                # Add booking confirmation to the response
                                booking_info = {
                                    "booking_id": function_result_payload.get(
                                        "booking_id"
                                    ),
                                    "listing_title": function_result_payload.get(
                                        "listing_title"
                                    ),
                                    "check_in": function_result_payload.get("check_in"),
                                    "check_out": function_result_payload.get(
                                        "check_out"
                                    ),
                                    "total_price": function_result_payload.get(
                                        "total_price"
                                    ),
                                }

                                # You might want to update the state or add this to the response
                                if "booking_info" not in final_response:
                                    final_response["booking_info"] = booking_info
                    else:
                        tool_result_content_for_gemini = (
                            function_result_payload if function_result_payload else {}
                        )

                    gemini_history_content.append(
                        {"role": "model", "parts": [response_part]}
                    )  # Append model's request part
                    # Append function execution result using the CORRECT 'response' key
                    gemini_history_content.append(
                        {
                            "role": "function",
                            "parts": [
                                {
                                    "function_response": {
                                        "name": function_name,
                                        "response": tool_result_content_for_gemini,  # Use the prepared content for Gemini
                                    }
                                }
                            ],
                        }
                    )

                    print(
                        "Sending request to Gemini (pass 2 - after function execution)..."
                    )
                    second_response = await model.generate_content_async(
                        contents=gemini_history_content
                    )

                    if not second_response.candidates:
                        raise ValueError(
                            "Gemini response missing candidates on second call."
                        )
                    if not second_response.candidates[0].content.parts:
                        raise ValueError(
                            "Gemini response candidate (pass 2) missing parts."
                        )
                    ai_natural_response = (
                        second_response.candidates[0].content.parts[0].text
                    )
                    print(f"Gemini final response (post-tool): {ai_natural_response}")
                    # Note: updated_info_for_response was already potentially updated if update_booking_parameters ran

                except Exception as tool_exec_error:
                    logger.error(
                        f"❌ FUNCTION FAILED | {function_name} | Error: {tool_exec_error}"
                    )
                    traceback.print_exc()
                    ai_natural_response = f"Sorry, I encountered an issue while trying to {function_name.replace('_', ' ')}. Could you try again?"
                    # Keep state as it was before the failed tool execution attempt
                    updated_info_for_response = current_info  # Reset to pre-tool state
                    search_results_for_response = (
                        None  # Ensure no partial results are sent
                    )

            else:
                # Handle case where Gemini requested a function not in available_tools
                print(f"ERROR: Gemini requested unknown function: {function_name}")
                ai_natural_response = "Sorry, I got a bit confused with an internal task. Could you please rephrase your request?"
                updated_info_for_response = current_info
                search_results_for_response = None

        else:
            # No function call needed, Gemini provided a direct text response
            ai_natural_response = response_part.text
            print(f"Gemini final response (no tool called): {ai_natural_response}")
            updated_info_for_response = current_info  # State didn't change
            search_results_for_response = None

    except Exception as gemini_error:
        print(f"ERROR during Gemini interaction or processing: {gemini_error}")
        traceback.print_exc()
        ai_natural_response = "I apologize, but I'm having trouble connecting with my systems right now. Please try again in a moment."
        updated_info_for_response = current_info  # Keep state before error
        search_results_for_response = None

    # --- Save Final State ---
    final_history = chat_history + [
        Message(role="user", content=user_message_content),
        Message(
            role="assistant", content=ai_natural_response
        ),  # Save final AI text response
    ]
    await save_conversation_state(session_id, updated_info_for_response, final_history)
    print("--- Request End ---")

    # --- Return Response ---
    # Include the structured search results for the frontend
    return ChatResponse(
        response=ai_natural_response,
        updated_info=updated_info_for_response,
        search_results=search_results_for_response,
    )
