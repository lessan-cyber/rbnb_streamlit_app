from .booking_tools import update_booking_parameters,update_booking_tool_schema
from .search_tools import search_listings, search_tool_schema

# Update the available tools dictionary
available_tools = {
    "update_booking_parameters": update_booking_parameters,
    "search_listings": search_listings  # Use your new enhanced search
}

