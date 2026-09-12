"""
Model Context Protocol (MCP) Services for Real Estate AI Assistant.
Provides Location & Amenities, Calculator (EMI & Pricing), and Calendar (Site Visit Booking).
"""

from app.ai.mcp.location_service import (
    geocode_location,
    get_nearby_places,
    calculate_route_and_distance,
    geoapify_geocode,
    geoapify_get_nearby_places,
    geoapify_calculate_route_and_distance,
)
from app.ai.mcp.calculator_service import (
    calculate_home_loan_emi,
    calculate_property_price_breakdown,
    calculate_buyer_loan_eligibility
)
from app.ai.mcp.calendar_service import (
    check_site_visit_availability,
    book_property_site_visit,
    get_customer_site_visits,
    cancel_or_reschedule_site_visit
)
from app.ai.mcp.mcp_server import (
    get_mcp_tool_definitions,
    execute_mcp_tool,
    mcp_app
)

__all__ = [
    "geocode_location",
    "get_nearby_places",
    "calculate_route_and_distance",
    "geoapify_geocode",
    "geoapify_get_nearby_places",
    "geoapify_calculate_route_and_distance",
    "calculate_home_loan_emi",
    "calculate_property_price_breakdown",
    "calculate_buyer_loan_eligibility",
    "check_site_visit_availability",
    "book_property_site_visit",
    "get_customer_site_visits",
    "cancel_or_reschedule_site_visit",
    "get_mcp_tool_definitions",
    "execute_mcp_tool",
    "mcp_app"
]

