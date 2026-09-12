import asyncio
import json
from app.ai.mcp.location_service import (
    geocode_location,
    get_nearby_places,
    calculate_route_and_distance
)
from app.ai.mcp.calculator_service import (
    calculate_home_loan_emi,
    calculate_property_price_breakdown,
    calculate_buyer_loan_eligibility
)
from app.ai.mcp.calendar_service import (
    check_site_visit_availability,
    book_property_site_visit
)
from app.ai.mcp.mcp_server import execute_mcp_tool
from app.ai.tools import get_langchain_tools

async def main():
    print("=" * 60)
    print("1. Testing Location & Navigation MCP Service (Free OSM/OSRM)")
    print("=" * 60)
    coords = await geocode_location("Velachery, Chennai")
    print(f"Geocode (Velachery): {coords}")

    places = await get_nearby_places("OMR, Sholinganallur", amenity_type="hospital", radius_meters=3000)
    print(f"Nearby Hospitals (OMR): Total Found = {places.get('total_found')}")
    if places.get("places"):
        print(f"First Hospital: {places['places'][0]}")

    route = await calculate_route_and_distance("Chennai Central", "Prestige Courtyards, Sholinganallur")
    print(f"Route Distance: {route.get('road_distance_km')} km | Drive Time: {route.get('driving_time_mins')} mins")
    print(f"Google Maps Link: {route.get('google_maps_url')}")

    print("\n" + "=" * 60)
    print("2. Testing Financial Calculator MCP Service")
    print("=" * 60)
    emi_res = calculate_home_loan_emi(loan_amount_lakhs=75.0, annual_interest_rate=8.5, tenure_years=20)
    print(f"EMI for 75L @ 8.5% (20 yrs): {emi_res.get('monthly_emi')} / month")
    print(f"Total Interest: {emi_res.get('total_interest_payable')}")

    cost_res = calculate_property_price_breakdown(base_price_lakhs=80.0, sqft=1250)
    print(f"Price Breakdown (80L, 1250 sqft): Rate = {cost_res.get('price_per_sqft')}")
    print(f"Stamp Duty: {cost_res.get('stamp_duty_cost')} | Total On-Road: {cost_res.get('total_estimated_cost')}")

    elig_res = calculate_buyer_loan_eligibility(monthly_net_income_inr=150000, existing_monthly_emis_inr=20000)
    print(f"Eligibility for 1.5L income: Max Loan = {elig_res.get('max_eligible_loan_amount')} | Recommended Budget = {elig_res.get('recommended_property_budget')}")

    print("\n" + "=" * 60)
    print("3. Testing Calendar MCP Service")
    print("=" * 60)
    slots = await check_site_visit_availability("Casagrand Zenith", "This Saturday")
    print(f"Casagrand Zenith Slots: Available = {slots.get('total_available_slots')}, Recommended = {slots.get('recommended_slot')}")

    booking = await book_property_site_visit(
        property_name="Casagrand Zenith",
        customer_name="Anbarasu",
        customer_phone="9876543210",
        visit_date="This Saturday",
        visit_time="11:00 AM"
    )
    print(f"Booking Status: {booking.get('status')} | ID: {booking.get('booking_id')}")
    print(f"Confirmation Message: {booking.get('message')}")

    print("\n" + "=" * 60)
    print("4. Testing MCP Dispatcher & LangChain Tools")
    print("=" * 60)
    tools = get_langchain_tools()
    print(f"Total LangChain Tools registered: {len(tools)}")
    for t in tools:
        print(f" - {t.name}: {t.description[:65]}...")

    mcp_res = await execute_mcp_tool("calc_home_loan_emi", {"loan_amount_lakhs": 50.0})
    print(f"MCP Dispatcher direct call: {mcp_res.get('monthly_emi')}")

    print("\n[SUCCESS] All MCP Services and Tools Tested Successfully!")

if __name__ == "__main__":
    asyncio.run(main())
