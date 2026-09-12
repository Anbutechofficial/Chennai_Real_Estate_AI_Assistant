import asyncio
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')


from app.ai.router import classify_query_intent, QueryIntent
from app.core.security import exchange_google_auth_code, fetch_google_user_profile
from app.ai.mcp.calendar_service import book_property_site_visit, check_site_visit_availability


async def run_all_tests():
    print("========================================")
    print("🚀 TESTING INTELLIGENT ROUTER & MCP OAUTH")
    print("========================================")

    test_queries = [
        ("Hi, good morning! Who are you?", QueryIntent.GENERAL_CONVERSATION, False),
        ("What is the EMI for 75 Lakhs loan at 8.5% interest?", QueryIntent.FINANCIAL_CALCULATOR, False),
        ("Calculate stamp duty and registration charges for 90 lakhs property", QueryIntent.FINANCIAL_CALCULATOR, False),
        ("How far is Chennai Airport from Prestige Courtyards Sholinganallur?", QueryIntent.MAPS_AND_LOCATION, False),
        ("Find nearby metro stations and hospitals in Velachery", QueryIntent.MAPS_AND_LOCATION, False),
        ("Schedule a site visit for Casagrand Zenith this Saturday 11 AM", QueryIntent.SCHEDULE_SITE_VISIT, False),
        ("Show me 3 BHK flats in OMR under 1.2 Crore", QueryIntent.REAL_ESTATE_SEARCH, True),
        ("Luxury apartments in Anna Nagar with 2000 sqft", QueryIntent.REAL_ESTATE_SEARCH, True),
    ]

    print("\n--- 1. Testing Intent & Query Router ---")
    all_passed = True
    for query, expected_intent, expected_rag in test_queries:
        res = classify_query_intent(query)
        intent = res["intent"]
        requires_rag = res["requires_rag"]
        match = (intent == expected_intent) and (requires_rag == expected_rag)
        status_icon = "✅" if match else "❌"
        print(f"{status_icon} Query: '{query}' -> Intent: {intent} (Requires RAG: {requires_rag})")
        if not match:
            all_passed = False

    print(f"\nRouter Test Result: {'ALL PASSED ✅' if all_passed else 'SOME FAILED ❌'}")

    print("\n--- 2. Testing Google OAuth 2.0 Helpers ---")
    token_res = await exchange_google_auth_code("sample_auth_code_12345")
    print(f"✅ Exchange code response: token_type={token_res.get('token_type')}, is_mock={token_res.get('is_mock')}")

    user_info = await fetch_google_user_profile(token_res["access_token"])
    print(f"✅ User profile fetched: email={user_info.get('email')}, name={user_info.get('name')}")

    print("\n--- 3. Testing Calendar Site Visit Booking & Sync ---")
    booking = await book_property_site_visit(
        property_name="Prestige Courtyards, Sholinganallur",
        customer_name="Anbarasu",
        customer_phone="+91 98401 99999",
        customer_email="anbarasu@gmail.com",
        visit_date="2026-08-23",
        visit_time="11:00 AM",
        google_access_token=token_res["access_token"]
    )
    print(f"✅ Booking Status: {booking.get('status')}")
    print(f"✅ Booking ID: {booking.get('booking_id')}")
    print(f"✅ Google Calendar URL: {booking.get('google_calendar_url')[:60]}...")
    print(f"✅ Google Meet URL: {booking.get('google_meet_url')}")

    print("\n========================================")
    print("🎉 ALL CORE UNIT TESTS COMPLETED SUCCESSFULLY!")
    print("========================================")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
