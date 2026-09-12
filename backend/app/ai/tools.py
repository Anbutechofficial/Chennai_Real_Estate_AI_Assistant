import os
import json
import math
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from app.ai.mcp.location_service import (
    calculate_route_and_distance,
    get_nearby_places,
    geocode_location
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
from app.rag.retrieval import load_mongo_properties, retrieve


# ── 1. Pydantic Input Schemas ──

class DistanceRouteInput(BaseModel):
    origin: str = Field(
        ...,
        description="User starting location or landmark (e.g., 'Guindy', 'Chennai Central', 'Airport', 'Adyar')"
    )
    destination: str = Field(
        ...,
        description="Target property name or locality (e.g., 'Prestige Courtyards, Sholinganallur', 'T Nagar', 'OMR')"
    )
    travel_mode: str = Field(
        default="drive",
        description="Mode of transportation: 'drive', 'two_wheeler', 'transit', 'walk'"
    )


class NearbyAmenitiesInput(BaseModel):
    location: str = Field(
        ...,
        description="The locality or property area (e.g., 'Velachery', 'OMR', 'Sholinganallur', 'Adyar')"
    )
    amenity_type: str = Field(
        default="metro",
        description="Type of amenity to find: 'metro', 'hospital', 'school', 'it_park', 'supermarket', 'restaurant', 'bank'"
    )
    radius_meters: Optional[int] = Field(
        default=4000,
        description="Search radius in meters (e.g., 3000, 5000)"
    )


class SearchPropertiesInput(BaseModel):
    location: Optional[str] = Field(
        default=None,
        description="Locality or area name (e.g., 'T Nagar', 'OMR', 'Velachery', 'Adyar')"
    )
    bhk: Optional[int] = Field(
        default=None,
        description="Number of bedrooms / BHK (e.g., 1, 2, 3, 4)"
    )
    min_price: Optional[float] = Field(
        default=None,
        description="Minimum budget in Lakhs INR (e.g., 40.0)"
    )
    max_price: Optional[float] = Field(
        default=None,
        description="Maximum budget in Lakhs INR (e.g., 120.0)"
    )
    min_sqft: Optional[float] = Field(
        default=None,
        description="Minimum area in square feet"
    )
    max_sqft: Optional[float] = Field(
        default=None,
        description="Maximum area in square feet"
    )
    sort_by: Optional[str] = Field(
        default="relevance",
        description="Sorting criteria: 'relevance', 'price_asc', 'price_desc', 'sqft_desc', 'value_per_sqft'"
    )


class CalculateEmiInput(BaseModel):
    loan_amount_lakhs: float = Field(
        ...,
        description="Loan amount in Lakhs INR (e.g., 60.0 for 60 Lakhs, 85.5 for 85.5 Lakhs)"
    )
    annual_interest_rate: float = Field(
        default=8.5,
        description="Annual interest rate percentage (e.g., 8.5 for 8.5%, default: 8.5)"
    )
    tenure_years: int = Field(
        default=20,
        description="Loan tenure in years (e.g., 20, default: 20)"
    )


class PriceBreakdownInput(BaseModel):
    base_price_lakhs: float = Field(
        ...,
        description="Base property price in Lakhs INR (e.g., 75.0)"
    )
    sqft: Optional[float] = Field(
        default=None,
        description="Property built-up area in square feet (e.g., 1250)"
    )
    registration_fee_percent: float = Field(
        default=7.0,
        description="State registration percentage (TN standard: 7%)"
    )
    stamp_duty_percent: float = Field(
        default=2.0,
        description="State stamp duty percentage (TN standard: 2%)"
    )


class LoanEligibilityInput(BaseModel):
    monthly_net_income_inr: float = Field(
        ...,
        description="Customer monthly net take-home salary in INR (e.g., 120000)"
    )
    existing_monthly_emis_inr: float = Field(
        default=0.0,
        description="Existing loan monthly EMIs in INR (e.g., 15000)"
    )
    loan_tenure_years: int = Field(
        default=20,
        description="Desired loan tenure in years"
    )


class CheckVisitSlotsInput(BaseModel):
    property_name: str = Field(
        ...,
        description="Name or locality of the property"
    )
    preferred_date: Optional[str] = Field(
        default="Upcoming Weekend",
        description="Preferred visit date (e.g., 'This Saturday', '2026-08-25')"
    )


class ScheduleSiteVisitInput(BaseModel):
    property_name: str = Field(
        ...,
        description="Name or location of the property to visit (e.g., 'Prestige Courtyards', 'Casagrand Zenith')"
    )
    customer_name: str = Field(
        ...,
        description="Customer full name"
    )
    customer_phone: Optional[str] = Field(
        default="Not Provided",
        description="Customer contact phone number"
    )
    customer_email: Optional[str] = Field(
        default="Not Provided",
        description="Customer contact email address"
    )
    preferred_date: Optional[str] = Field(
        default="Upcoming Weekend",
        description="Preferred visit date (e.g., 'This Saturday', '2026-08-25')"
    )
    preferred_time: Optional[str] = Field(
        default="11:00 AM",
        description="Preferred time slot (e.g., '11:00 AM', '03:00 PM', '04:30 PM')"
    )
    notes: Optional[str] = Field(
        default="",
        description="Any specific requirements or BHK preference"
    )


# ── 2. LangChain Tools Definition (Powered by MCP Services) ──

@tool("calculate_distance_and_route", args_schema=DistanceRouteInput)
async def langchain_tool_distance(origin: str, destination: str, travel_mode: str = "drive") -> Dict[str, Any]:
    """Calculates real-time road distance (km), driving/riding travel time, key step-by-step corridor directions, and Google Maps navigation link between user location and property."""
    return await calculate_route_and_distance(origin=origin, destination=destination, travel_mode=travel_mode)



@tool("find_nearby_amenities", args_schema=NearbyAmenitiesInput)
async def langchain_tool_amenities(location: str, amenity_type: str = "metro", radius_meters: int = 4000) -> Dict[str, Any]:
    """Finds key nearby amenities (Metro stations, Hospitals, Schools, IT Parks, Supermarkets, Restaurants) around a property location."""
    return await get_nearby_places(location=location, amenity_type=amenity_type, radius_meters=radius_meters)


@tool("search_properties", args_schema=SearchPropertiesInput)
async def langchain_tool_search_properties(
    location: Optional[str] = None,
    bhk: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_sqft: Optional[float] = None,
    max_sqft: Optional[float] = None,
    sort_by: Optional[str] = "relevance"
) -> Dict[str, Any]:
    """Searches real estate listings in the database by location, price budget, BHK count, and square feet."""
    query_parts = []
    if bhk:
        query_parts.append(f"{bhk} BHK")
    if location:
        query_parts.append(f"in {location}")
    if max_price:
        query_parts.append(f"under {max_price} Lakhs")
    if min_price and not max_price:
        query_parts.append(f"above {min_price} Lakhs")
    if sort_by == "price_asc":
        query_parts.append("cheapest")
    elif sort_by == "sqft_desc":
        query_parts.append("largest sqft")

    query_str = " ".join(query_parts) if query_parts else "property listings"
    docs = await retrieve(query_str, top_k=5)
    return {
        "search_parameters": {
            "location": location,
            "bhk": bhk,
            "min_price": min_price,
            "max_price": max_price,
            "min_sqft": min_sqft,
            "max_sqft": max_sqft,
            "sort_by": sort_by
        },
        "matched_properties": docs
    }


@tool("calculate_emi", args_schema=CalculateEmiInput)
def langchain_tool_calculate_emi(loan_amount_lakhs: float, annual_interest_rate: float = 8.5, tenure_years: int = 20) -> Dict[str, Any]:
    """Calculates monthly home loan EMI, total interest payable, total payment, and principal vs interest amortization summary."""
    return calculate_home_loan_emi(loan_amount_lakhs=loan_amount_lakhs, annual_interest_rate=annual_interest_rate, tenure_years=tenure_years)


@tool("calculate_property_price_breakdown", args_schema=PriceBreakdownInput)
def langchain_tool_price_breakdown(
    base_price_lakhs: float,
    sqft: Optional[float] = None,
    registration_fee_percent: float = 7.0,
    stamp_duty_percent: float = 2.0
) -> Dict[str, Any]:
    """Calculates all-inclusive on-road property price breakdown including rate per sq.ft, Tamil Nadu stamp duty, registration fees, and total cost."""
    return calculate_property_price_breakdown(
        base_price_lakhs=base_price_lakhs,
        sqft=sqft,
        registration_fee_percent=registration_fee_percent,
        stamp_duty_percent=stamp_duty_percent
    )


@tool("calculate_buyer_loan_eligibility", args_schema=LoanEligibilityInput)
def langchain_tool_loan_eligibility(
    monthly_net_income_inr: float,
    existing_monthly_emis_inr: float = 0.0,
    loan_tenure_years: int = 20
) -> Dict[str, Any]:
    """Computes home buyer maximum loan eligibility and affordable property budget based on monthly salary and FOIR banking standards."""
    return calculate_buyer_loan_eligibility(
        monthly_net_income_inr=monthly_net_income_inr,
        existing_monthly_emis_inr=existing_monthly_emis_inr,
        loan_tenure_years=loan_tenure_years
    )


@tool("check_site_visit_availability", args_schema=CheckVisitSlotsInput)
async def langchain_tool_check_slots(property_name: str, preferred_date: str = "Upcoming Weekend") -> Dict[str, Any]:
    """Checks available and booked site visit time slots for a property on a specific date."""
    return await check_site_visit_availability(property_name=property_name, preferred_date=preferred_date)


@tool("schedule_site_visit", args_schema=ScheduleSiteVisitInput)
async def langchain_tool_schedule_site_visit(
    property_name: str,
    customer_name: str,
    customer_phone: Optional[str] = "Not Provided",
    customer_email: Optional[str] = "Not Provided",
    preferred_date: Optional[str] = "Upcoming Weekend",
    preferred_time: Optional[str] = "11:00 AM",
    notes: Optional[str] = ""
) -> Dict[str, Any]:
    """Schedules a property site visit, records the booking in MongoDB, and generates iCalendar event data."""
    return await book_property_site_visit(
        property_name=property_name,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        visit_date=preferred_date,
        visit_time=preferred_time,
        notes=notes
    )


def get_langchain_tools() -> List[Any]:
    """Returns the list of LangChain tools ready for model binding or AgentExecutor."""
    return [
        langchain_tool_distance,
        langchain_tool_amenities,
        langchain_tool_search_properties,
        langchain_tool_calculate_emi,
        langchain_tool_price_breakdown,
        langchain_tool_loan_eligibility,
        langchain_tool_check_slots,
        langchain_tool_schedule_site_visit
    ]


# ── Backward-Compatibility & Direct Dispatch Helpers ──

async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Central dispatcher for all AI tools."""
    from app.ai.mcp.mcp_server import execute_mcp_tool
    return await execute_mcp_tool(tool_name, arguments)
