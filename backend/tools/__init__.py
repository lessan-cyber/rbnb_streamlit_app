from .booking_tools import create_booking, create_booking_tool_schema, update_booking_parameters, update_booking_tool_schema
from .search_tools import search_listings, search_tool_schema
from .aviailability_tools import check_availability, check_availability_tool_schema
from .user_tools import get_or_create_user, get_or_create_user_tool_schema

# Dictionary of available tool functions that can be called by name
available_tools = {
    "update_booking_parameters": update_booking_parameters,
    "search_listings": search_listings,
    "check_availability": check_availability,
    "get_or_create_user": get_or_create_user,
    "create_booking": create_booking
}

