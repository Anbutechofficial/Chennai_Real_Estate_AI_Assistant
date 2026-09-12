"""
Unified Model Context Protocol (MCP) Server and Tool Registry.
Exposes standard MCP tool schemas and async execution dispatcher for Real Estate AI.
"""

from typing import Dict, Any, List
from app.ai.mcp.location_service import (
    geocode_location,
    get_nearby_places,
    calculate_route_and_distance,
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


MCP_TOOL_DEFINITIONS = [
    # ── Location & Navigation Tools ──
    {
        "name": "geocode_location",
        "description": "Converts any Chennai/TN address, landmark, or locality into exact latitude and longitude coordinates.",
        "parameters": {
            "type": "object",
            "properties": {
                "location_name": {
                    "type": "string",
                    "description": "Area, locality or landmark name (e.g. 'OMR', 'Velachery', 'Guindy', 'Adyar')"
                }
            },
            "required": ["location_name"]
        }
    },
    {
        "name": "find_nearby_amenities",
        "description": "Discovers nearby amenities (Metro stations, Hospitals, Schools, IT Parks, Supermarkets, Restaurants) around a property location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Property locality or area name (e.g., 'Sholinganallur', 'Perungudi', 'Velachery')"
                },
                "amenity_type": {
                    "type": "string",
                    "description": "Type of amenity to find: 'metro', 'hospital', 'school', 'it_park', 'supermarket', 'restaurant', 'bank'",
                    "default": "metro"
                },
                "radius_meters": {
                    "type": "integer",
                    "description": "Search radius in meters (default 4000m / 4km)",
                    "default": 4000
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "calculate_distance_and_route",
        "description": "Calculates real-world road distance, driving/riding travel duration, route summary, and navigation directions between origin and property destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Starting location or landmark (e.g., 'Chennai Central', 'Airport', 'Guindy')"
                },
                "destination": {
                    "type": "string",
                    "description": "Target property locality or project name (e.g., 'Prestige Courtyards, Sholinganallur', 'OMR')"
                },
                "travel_mode": {
                    "type": "string",
                    "description": "Mode of travel: 'drive', 'two_wheeler', 'transit', 'walk'",
                    "default": "drive"
                }
            },
            "required": ["origin", "destination"]
        }
    },

    # ── Financial Calculator Tools ──
    {
        "name": "calc_home_loan_emi",
        "description": "Calculates monthly Home Loan EMI, total interest payable, total cost, and principal vs interest amortization summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "loan_amount_lakhs": {
                    "type": "number",
                    "description": "Loan amount in Lakhs INR (e.g., 50.0 for 50 Lakhs, 85.5 for 85.5 Lakhs)"
                },
                "annual_interest_rate": {
                    "type": "number",
                    "description": "Annual interest rate percentage (e.g., 8.5 for 8.5% p.a.)",
                    "default": 8.5
                },
                "tenure_years": {
                    "type": "integer",
                    "description": "Loan tenure in years (e.g., 20 for 20 years)",
                    "default": 20
                }
            },
            "required": ["loan_amount_lakhs"]
        }
    },
    {
        "name": "calc_property_breakdown",
        "description": "Calculates all-inclusive on-road property price breakdown including rate per sq.ft, Tamil Nadu stamp duty (2%), registration fees (7%), and GST.",
        "parameters": {
            "type": "object",
            "properties": {
                "base_price_lakhs": {
                    "type": "number",
                    "description": "Base property price in Lakhs INR (e.g. 75.0)"
                },
                "sqft": {
                    "type": "number",
                    "description": "Property built-up area in square feet (e.g. 1250)",
                    "default": None
                },
                "registration_fee_percent": {
                    "type": "number",
                    "description": "Registration fee percentage (TN standard is 7%)",
                    "default": 7.0
                },
                "stamp_duty_percent": {
                    "type": "number",
                    "description": "Stamp duty percentage (TN standard is 2%)",
                    "default": 2.0
                }
            },
            "required": ["base_price_lakhs"]
        }
    },
    {
        "name": "calc_buyer_affordability",
        "description": "Computes home buyer maximum loan eligibility and affordable property budget based on monthly net income and existing EMIs (50% FOIR banking standard).",
        "parameters": {
            "type": "object",
            "properties": {
                "monthly_net_income_inr": {
                    "type": "number",
                    "description": "Customer monthly net take-home salary in INR (e.g. 120000)"
                },
                "existing_monthly_emis_inr": {
                    "type": "number",
                    "description": "Existing loan EMIs in INR per month (e.g. 15000)",
                    "default": 0.0
                },
                "loan_tenure_years": {
                    "type": "integer",
                    "description": "Desired loan tenure in years",
                    "default": 20
                }
            },
            "required": ["monthly_net_income_inr"]
        }
    },

    # ── Calendar & Visit Booking Tools ──
    {
        "name": "calendar_check_slots",
        "description": "Checks available and booked site visit time slots for a property on a specific date.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_name": {
                    "type": "string",
                    "description": "Name or locality of the property"
                },
                "preferred_date": {
                    "type": "string",
                    "description": "Date to check (e.g., '2026-08-25', 'This Saturday', 'Tomorrow')",
                    "default": "Upcoming Weekend"
                }
            },
            "required": ["property_name"]
        }
    },
    {
        "name": "calendar_book_visit",
        "description": "Schedules and confirms a property site visit for a customer, records it in MongoDB, and generates iCalendar event data.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_name": {
                    "type": "string",
                    "description": "Name of the property project (e.g., 'Prestige Courtyards', 'Casagrand Zenith')"
                },
                "customer_name": {
                    "type": "string",
                    "description": "Full name of the customer"
                },
                "customer_phone": {
                    "type": "string",
                    "description": "Customer contact mobile number",
                    "default": "Not Provided"
                },
                "customer_email": {
                    "type": "string",
                    "description": "Customer email address for calendar invites",
                    "default": "Not Provided"
                },
                "visit_date": {
                    "type": "string",
                    "description": "Date of site visit (e.g., 'This Saturday', '2026-08-23')",
                    "default": "Upcoming Saturday"
                },
                "visit_time": {
                    "type": "string",
                    "description": "Time slot (e.g., '11:00 AM', '03:00 PM', '04:30 PM')",
                    "default": "11:00 AM"
                },
                "notes": {
                    "type": "string",
                    "description": "Special requirements or BHK preference",
                    "default": ""
                }
            },
            "required": ["property_name", "customer_name"]
        }
    },
    {
        "name": "calendar_cancel_reschedule",
        "description": "Cancels or reschedules an existing property site visit booking using the booking reference ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "Booking reference ID (e.g., 'VISIT-A729B1')"
                },
                "action": {
                    "type": "string",
                    "description": "'cancel' or 'reschedule'",
                    "default": "cancel"
                },
                "new_date": {
                    "type": "string",
                    "description": "New visit date if rescheduling",
                    "default": None
                },
                "new_time": {
                    "type": "string",
                    "description": "New visit time slot if rescheduling",
                    "default": None
                }
            },
            "required": ["booking_id", "action"]
        }
    }
]


def get_mcp_tool_definitions() -> List[Dict[str, Any]]:
    """Returns the list of registered MCP tool definitions."""
    return MCP_TOOL_DEFINITIONS


async def execute_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Central dispatcher executing any MCP tool requested by the Model Context Protocol client or Agent.
    """
    # ── Location & Navigation Tools ──
    if tool_name in ["geocode_location", "geoapify_geocode"]:
        return await geocode_location(
            location_name=arguments.get("location_name", "")
        )
    elif tool_name in ["find_nearby_amenities", "geoapify_nearby_amenities"]:
        return await get_nearby_places(
            location=arguments.get("location", ""),
            amenity_type=arguments.get("amenity_type", "metro"),
            radius_meters=int(arguments.get("radius_meters", 4000))
        )
    elif tool_name in ["calculate_distance_and_route", "geoapify_route_distance"]:
        return await calculate_route_and_distance(
            origin=arguments.get("origin", ""),
            destination=arguments.get("destination", ""),
            travel_mode=arguments.get("travel_mode", "drive")
        )

    # ── Financial Calculator Tools ──
    elif tool_name in ["calc_home_loan_emi", "calculate_emi"]:
        return calculate_home_loan_emi(
            loan_amount_lakhs=float(arguments.get("loan_amount_lakhs", 50.0)),
            annual_interest_rate=float(arguments.get("annual_interest_rate", 8.5)),
            tenure_years=int(arguments.get("tenure_years", 20))
        )
    elif tool_name in ["calc_property_breakdown", "calc_property_price_breakdown"]:
        return calculate_property_price_breakdown(
            base_price_lakhs=float(arguments.get("base_price_lakhs", 50.0)),
            sqft=float(arguments.get("sqft")) if arguments.get("sqft") else None,
            registration_fee_percent=float(arguments.get("registration_fee_percent", 7.0)),
            stamp_duty_percent=float(arguments.get("stamp_duty_percent", 2.0))
        )
    elif tool_name in ["calc_buyer_affordability", "calculate_buyer_affordability"]:
        return calculate_buyer_loan_eligibility(
            monthly_net_income_inr=float(arguments.get("monthly_net_income_inr", 100000.0)),
            existing_monthly_emis_inr=float(arguments.get("existing_monthly_emis_inr", 0.0)),
            loan_tenure_years=int(arguments.get("loan_tenure_years", 20))
        )

    # ── Calendar & Visit Booking Tools ──
    elif tool_name in ["calendar_check_slots", "check_site_visit_availability"]:
        return await check_site_visit_availability(
            property_name=arguments.get("property_name", ""),
            preferred_date=arguments.get("preferred_date", "Upcoming Weekend")
        )
    elif tool_name in ["calendar_book_visit", "schedule_site_visit", "book_property_site_visit"]:
        return await book_property_site_visit(
            property_name=arguments.get("property_name", ""),
            customer_name=arguments.get("customer_name", "Customer"),
            customer_phone=arguments.get("customer_phone", "Not Provided"),
            customer_email=arguments.get("customer_email", "Not Provided"),
            visit_date=arguments.get("visit_date") or arguments.get("preferred_date", "Upcoming Saturday"),
            visit_time=arguments.get("visit_time") or arguments.get("preferred_time", "11:00 AM"),
            notes=arguments.get("notes", "")
        )
    elif tool_name in ["calendar_cancel_reschedule", "cancel_or_reschedule_site_visit"]:
        return await cancel_or_reschedule_site_visit(
            booking_id=arguments.get("booking_id", ""),
            action=arguments.get("action", "cancel"),
            new_date=arguments.get("new_date"),
            new_time=arguments.get("new_time")
        )
    else:
        return {"error": f"Unknown MCP tool '{tool_name}'"}


# Optional FastMCP server instance if mcp library is available
try:
    from mcp.server.fastmcp import FastMCP
    mcp_app = FastMCP("RealEstateAI-MCPServer")
except Exception:
    mcp_app = None
