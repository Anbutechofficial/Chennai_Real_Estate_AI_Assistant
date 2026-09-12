import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


ALL_DAILY_SLOTS = [
    "09:30 AM",
    "11:00 AM",
    "01:30 PM",
    "03:00 PM",
    "04:30 PM",
    "05:45 PM"
]


def _generate_ics_content(
    booking_id: str,
    property_name: str,
    customer_name: str,
    visit_date_str: str,
    visit_time_str: str
) -> str:
    """Generates RFC 5545 iCalendar content for Google/Apple Calendar integration."""
    now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    # Try parsing date and time or default to tomorrow 11 AM
    try:
        from dateutil import parser
        dt = parser.parse(f"{visit_date_str} {visit_time_str}")
        start_time_str = dt.strftime("%Y%m%dT%H%M%S")
        end_time_str = (dt + timedelta(minutes=45)).strftime("%Y%m%dT%H%M%S")
    except Exception:
        start_time_str = now_str
        end_time_str = now_str

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Real Estate AI Assistant//Site Visit Scheduler//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{booking_id}@realestateai.local",
        f"DTSTAMP:{now_str}",
        f"DTSTART:{start_time_str}",
        f"DTEND:{end_time_str}",
        f"SUMMARY:Property Site Visit - {property_name}",
        f"DESCRIPTION:Confirmed Property Visit for {customer_name} at {property_name}. Booking ID: {booking_id}",
        f"LOCATION:{property_name}, Chennai",
        "STATUS:CONFIRMED",
        "BEGIN:VALARM",
        "TRIGGER:-PT1H",
        "ACTION:DISPLAY",
        f"DESCRIPTION:Reminder: Site visit for {property_name} in 1 hour",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    return "\r\n".join(ics_lines)


async def check_site_visit_availability(
    property_name: str,
    preferred_date: str = "Upcoming Weekend"
) -> Dict[str, Any]:
    """
    Checks site visit availability for a given property and date.
    Returns list of open slots and already booked slots.
    """
    booked_slots: List[str] = []

    try:
        from app.db.mongodb import get_mongo_client
        client = get_mongo_client()
        db = client["vector_demo_db"]
        visits_col = db["site_visits"]
        
        cursor = visits_col.find({
            "property_name": {"$regex": property_name, "$options": "i"},
            "preferred_date": preferred_date,
            "status": "CONFIRMED"
        })
        async for doc in cursor:
            if doc.get("preferred_time"):
                booked_slots.append(doc["preferred_time"])
    except Exception as e:
        print(f"[Calendar Check] DB note: {e}")

    available_slots = [s for s in ALL_DAILY_SLOTS if s not in booked_slots]

    return {
        "status": "SUCCESS",
        "property_name": property_name,
        "date": preferred_date,
        "total_available_slots": len(available_slots),
        "available_slots": available_slots,
        "booked_slots": booked_slots,
        "recommended_slot": available_slots[0] if available_slots else "All slots booked for this date"
    }


import urllib.parse
import httpx


def _generate_google_calendar_link(
    property_name: str,
    customer_name: str,
    visit_date_str: str,
    visit_time_str: str,
    booking_id: str
) -> str:
    """Generates a one-click Google Calendar web URL to add the event immediately to the user's personal Google Calendar."""
    try:
        from dateutil import parser
        dt = parser.parse(f"{visit_date_str} {visit_time_str}")
        start_str = dt.strftime("%Y%m%dT%H%M%SZ")
        end_str = (dt + timedelta(minutes=45)).strftime("%Y%m%dT%H%M%SZ")
    except Exception:
        now_dt = datetime.utcnow() + timedelta(days=1)
        start_str = now_dt.strftime("%Y%m%dT110000Z")
        end_str = now_dt.strftime("%Y%m%dT114500Z")

    title = f"Property Site Visit: {property_name}"
    details = f"Site visit for {customer_name}. Booking Reference ID: {booking_id}. Organized by Real Estate AI Assistant."
    location = f"{property_name}, Chennai"

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": details,
        "location": location,
        "trp": "true"
    }
    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"


async def create_google_calendar_event(
    google_access_token: str,
    property_name: str,
    customer_name: str,
    visit_date_str: str,
    visit_time_str: str,
    booking_id: str
) -> Dict[str, Any]:
    """Inserts a real event into Google Calendar via Google Calendar REST API."""
    if not google_access_token or google_access_token.startswith("mock_"):
        return {
            "synced": True,
            "is_mock": True,
            "html_link": _generate_google_calendar_link(property_name, customer_name, visit_date_str, visit_time_str, booking_id),
            "meet_link": f"https://meet.google.com/rea-{uuid.uuid4().hex[:3]}-{uuid.uuid4().hex[:4]}"
        }

    try:
        from dateutil import parser
        dt = parser.parse(f"{visit_date_str} {visit_time_str}")
        start_iso = dt.isoformat()
        end_iso = (dt + timedelta(minutes=45)).isoformat()
    except Exception:
        now_dt = datetime.utcnow() + timedelta(days=1)
        start_iso = now_dt.isoformat()
        end_iso = (now_dt + timedelta(minutes=45)).isoformat()

    event_payload = {
        "summary": f"Property Site Visit: {property_name}",
        "location": f"{property_name}, Chennai",
        "description": f"Site visit for {customer_name}. Booking ID: {booking_id}.",
        "start": {"dateTime": start_iso, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Kolkata"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60},
                {"method": "email", "minutes": 1440}
            ]
        }
    }

    headers = {"Authorization": f"Bearer {google_access_token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post("https://www.googleapis.com/calendar/v3/calendars/primary/events", headers=headers, json=event_payload)
        if res.status_code in [200, 201]:
            data = res.json()
            return {
                "synced": True,
                "is_mock": False,
                "event_id": data.get("id"),
                "html_link": data.get("htmlLink", ""),
                "meet_link": data.get("hangoutLink", "")
            }
    return {
        "synced": False,
        "html_link": _generate_google_calendar_link(property_name, customer_name, visit_date_str, visit_time_str, booking_id)
    }


async def book_property_site_visit(
    property_name: str,
    customer_name: str,
    customer_phone: Optional[str] = "Not Provided",
    customer_email: Optional[str] = "Not Provided",
    visit_date: Optional[str] = "Upcoming Saturday",
    visit_time: Optional[str] = "11:00 AM",
    notes: Optional[str] = "",
    google_access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Schedules and confirms a property site visit, records it in MongoDB, generates Google Calendar link & iCalendar event data.
    """
    booking_id = f"VISIT-{uuid.uuid4().hex[:6].upper()}"
    now_iso = datetime.utcnow().isoformat()

    booking_record = {
        "booking_id": booking_id,
        "property_name": property_name,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_email": customer_email,
        "preferred_date": visit_date,
        "preferred_time": visit_time,
        "notes": notes,
        "status": "CONFIRMED",
        "created_at": now_iso
    }

    db_saved = False
    try:
        from app.db.mongodb import get_mongo_client
        client = get_mongo_client()
        db = client["vector_demo_db"]
        visits_col = db["site_visits"]
        await visits_col.insert_one(booking_record.copy())
        db_saved = True
    except Exception as e:
        print(f"[Calendar Booking] MongoDB write note: {e}")

    ics_content = _generate_ics_content(
        booking_id=booking_id,
        property_name=property_name,
        customer_name=customer_name,
        visit_date_str=visit_date or "Tomorrow",
        visit_time_str=visit_time or "11:00 AM"
    )

    gcal_info = await create_google_calendar_event(
        google_access_token=google_access_token,
        property_name=property_name,
        customer_name=customer_name,
        visit_date_str=visit_date or "Tomorrow",
        visit_time_str=visit_time or "11:00 AM",
        booking_id=booking_id
    )

    return {
        "status": "CONFIRMED",
        "booking_id": booking_id,
        "property_name": property_name,
        "customer_name": customer_name,
        "contact_phone": customer_phone,
        "scheduled_date": visit_date,
        "scheduled_time": visit_time,
        "db_synced": db_saved,
        "google_calendar_synced": gcal_info.get("synced", True),
        "google_calendar_url": gcal_info.get("html_link"),
        "google_meet_url": gcal_info.get("meet_link"),
        "message": (
            f"Site visit successfully confirmed for {property_name} on {visit_date} at {visit_time}. "
            f"Your Booking Reference ID is {booking_id}."
        ),
        "calendar_event": {
            "type": "iCalendar",
            "summary": f"Visit to {property_name}",
            "ics_data": ics_content,
            "google_calendar_url": gcal_info.get("html_link")
        }
    }


async def get_customer_site_visits(
    customer_phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    property_name: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves scheduled site visits from MongoDB for a customer or property."""
    query: Dict[str, Any] = {}
    if customer_phone and customer_phone != "Not Provided":
        query["customer_phone"] = customer_phone
    elif customer_name:
        query["customer_name"] = {"$regex": customer_name, "$options": "i"}
    elif property_name:
        query["property_name"] = {"$regex": property_name, "$options": "i"}

    visits: List[Dict[str, Any]] = []
    try:
        from app.db.mongodb import get_mongo_client
        client = get_mongo_client()
        db = client["vector_demo_db"]
        visits_col = db["site_visits"]
        cursor = visits_col.find(query).sort("created_at", -1).limit(10)
        async for doc in cursor:
            doc.pop("_id", None)
            visits.append(doc)
    except Exception as e:
        print(f"[Get Visits] MongoDB note: {e}")

    return {
        "status": "SUCCESS",
        "total_visits": len(visits),
        "site_visits": visits
    }


async def cancel_or_reschedule_site_visit(
    booking_id: str,
    action: str = "cancel",
    new_date: Optional[str] = None,
    new_time: Optional[str] = None
) -> Dict[str, Any]:
    """Cancels or reschedules an existing site visit using its booking ID."""
    clean_action = action.lower().strip()
    
    try:
        from app.db.mongodb import get_mongo_client
        client = get_mongo_client()
        db = client["vector_demo_db"]
        visits_col = db["site_visits"]
        
        if clean_action in ["cancel", "cancelled"]:
            res = await visits_col.update_one(
                {"booking_id": booking_id},
                {"$set": {"status": "CANCELLED", "updated_at": datetime.utcnow().isoformat()}}
            )
            return {
                "status": "SUCCESS",
                "booking_id": booking_id,
                "action": "CANCELLED",
                "message": f"Site visit booking {booking_id} has been cancelled successfully."
            }
        elif clean_action in ["reschedule", "rescheduled"]:
            update_data: Dict[str, Any] = {
                "status": "RESCHEDULED",
                "updated_at": datetime.utcnow().isoformat()
            }
            if new_date:
                update_data["preferred_date"] = new_date
            if new_time:
                update_data["preferred_time"] = new_time
                
            res = await visits_col.update_one(
                {"booking_id": booking_id},
                {"$set": update_data}
            )
            return {
                "status": "SUCCESS",
                "booking_id": booking_id,
                "action": "RESCHEDULED",
                "new_date": new_date,
                "new_time": new_time,
                "message": f"Site visit booking {booking_id} has been rescheduled to {new_date} at {new_time}."
            }
    except Exception as e:
        print(f"[Cancel/Reschedule] Error: {e}")

    return {
        "status": "ERROR",
        "booking_id": booking_id,
        "message": f"Could not {action} booking {booking_id}."
    }
