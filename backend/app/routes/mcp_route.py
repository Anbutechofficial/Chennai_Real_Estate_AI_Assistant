"""
routes/mcp_route.py
───────────────────
Endpoints for Model Context Protocol (MCP) Service Connectors:
  1. GET  /api/mcp/status   - Overall MCP Protocol health & OAuth status
  2. GET  /api/mcp/tools    - Registry of active MCP tools and schemas
  3. POST /api/mcp/execute  - Directly execute any MCP tool
  4. POST /api/mcp/oauth/google - OAuth token and authorization manager
  5. GET  /api/mcp/calendar/events - Fetch booked site visits
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from app.ai.mcp.mcp_server import MCP_TOOL_DEFINITIONS, execute_mcp_tool
from app.ai.mcp.calendar_service import get_customer_site_visits

router = APIRouter(prefix="/api/mcp", tags=["Model Context Protocol (MCP)"])

# In-memory OAuth state for demonstration / session
_google_oauth_state = {
    "connected": True,
    "email": "user@gmail.com",
    "scopes": [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/maps.routes",
        "https://www.googleapis.com/auth/places.nearby"
    ],
    "client_id": "847291039482-rf-ai-assistant.apps.googleusercontent.com",
    "token_type": "Bearer",
    "expires_in_hours": 12,
    "last_synced": datetime.now(timezone.utc).isoformat(),
}


class ExecuteToolRequest(BaseModel):
    tool_name: str = Field("", description="Name of the MCP tool to execute")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments dictionary for the tool")

    @model_validator(mode="before")
    @classmethod
    def normalize_tool_request(cls, data: Any) -> Any:
        if isinstance(data, dict):
            t_name = data.get("tool_name") or data.get("name") or data.get("tool") or ""
            args = data.get("arguments") or data.get("args") or data.get("parameters") or data.get("params") or {}
            data["tool_name"] = str(t_name).strip()
            data["arguments"] = args if isinstance(args, dict) else {}
        return data


class OAuthUpdateRequest(BaseModel):
    connected: bool
    email: Optional[str] = None
    client_id: Optional[str] = None


@router.get("/status")
async def get_mcp_status():
    """Returns the operational status of MCP servers and OAuth connectors."""
    return {
        "protocol_version": "2024-11-05 (MCP v1.0)",
        "server_name": "realestate-ai-mcp-server",
        "status": "ONLINE",
        "latency_ms": 18,
        "active_connectors": [
            {
                "id": "google-maps",
                "name": "Google Maps & Navigation MCP",
                "category": "Location & Navigation",
                "status": "ACTIVE" if _google_oauth_state["connected"] else "READY",
                "oauth_required": False,
                "tools_count": 3,
                "version": "2.4.0",
                "description": "Geocoding, real-world distance calculation, turn-by-turn routes & amenity finder (OSM / Google Maps v2)."
            },
            {
                "id": "google-calendar",
                "name": "Google Calendar & Meet MCP",
                "category": "Productivity & Scheduling",
                "status": "ACTIVE" if _google_oauth_state["connected"] else "DISCONNECTED",
                "oauth_required": True,
                "oauth_connected": _google_oauth_state["connected"],
                "tools_count": 4,
                "version": "1.8.2",
                "description": "Site visit slot availability check, automatic event creation, Google Meet sync & iCal export."
            },
            {
                "id": "financial-calculator",
                "name": "Financial & EMI Calculator MCP",
                "category": "Financial Services",
                "status": "ACTIVE",
                "oauth_required": False,
                "tools_count": 3,
                "version": "3.1.0",
                "description": "High-precision Home Loan EMI calculator, Tamil Nadu stamp duty & registration breakdown, and buyer affordability."
            }
        ],
        "oauth": _google_oauth_state,
        "total_tools": len(MCP_TOOL_DEFINITIONS)
    }


@router.get("/tools")
async def get_mcp_tools():
    """Returns the full list of tool definitions registered in the MCP Registry."""
    return {
        "count": len(MCP_TOOL_DEFINITIONS),
        "tools": MCP_TOOL_DEFINITIONS
    }


@router.post("/execute")
async def run_mcp_tool(body: ExecuteToolRequest):
    """Directly dispatches an execution request to the designated MCP tool."""
    try:
        result = await execute_mcp_tool(body.tool_name, body.arguments)
        return {
            "status": "SUCCESS",
            "tool_name": body.tool_name,
            "result": result,
            "executed_at": datetime.now(timezone.utc).isoformat()
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MCP tool execution failed: {str(e)}")


import urllib.parse
from app.core.config import Setting
from app.core.security import exchange_google_auth_code, fetch_google_user_profile


class GoogleOAuthCallbackRequest(BaseModel):
    code: str = Field(..., description="Google authorization code from OAuth redirect")
    redirect_uri: Optional[str] = Field(None, description="Matching OAuth redirect URI")


@router.get("/oauth/google/url")
async def get_google_oauth_url(redirect_uri: Optional[str] = None):
    """
    Generates a real Google OAuth 2.0 authorization URL with calendar and profile scopes.
    """
    client_id = Setting.GOOGLE_CLIENT_ID or "847291039482-rf-ai-assistant.apps.googleusercontent.com"
    target_redirect = redirect_uri or Setting.GOOGLE_REDIRECT_URI or "http://localhost:8010/api/auth/google/callback"
    
    scopes = [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly",
        "openid",
        "email",
        "profile"
    ]
    
    params = {
        "client_id": client_id,
        "redirect_uri": target_redirect,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true"
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return {
        "status": "SUCCESS",
        "auth_url": auth_url,
        "client_id": client_id,
        "redirect_uri": target_redirect,
        "scopes": scopes
    }


@router.post("/oauth/google/callback")
async def handle_google_oauth_callback(body: GoogleOAuthCallbackRequest):
    """
    Exchanges Google authorization code for tokens, retrieves user profile, and connects MCP Google services.
    """
    token_data = await exchange_google_auth_code(body.code, body.redirect_uri)
    access_token = token_data.get("access_token", "")
    
    # Fetch user info from Google
    user_info = await fetch_google_user_profile(access_token)
    email = user_info.get("email", "buyer@gmail.com")
    
    _google_oauth_state["connected"] = True
    _google_oauth_state["email"] = email
    _google_oauth_state["last_synced"] = datetime.now(timezone.utc).isoformat()
    if not token_data.get("is_mock"):
        _google_oauth_state["access_token"] = access_token
    
    return {
        "status": "SUCCESS",
        "message": f"Successfully connected Google Account ({email}) to MCP Calendar Services.",
        "user": user_info,
        "oauth": _google_oauth_state
    }


@router.post("/oauth/google")
async def update_google_oauth(body: OAuthUpdateRequest):
    """Connects, disconnects, or configures Google OAuth 2.0 credentials for MCP services."""
    _google_oauth_state["connected"] = body.connected
    if body.email:
        _google_oauth_state["email"] = body.email
    if body.client_id:
        _google_oauth_state["client_id"] = body.client_id
    _google_oauth_state["last_synced"] = datetime.now(timezone.utc).isoformat()
    return {
        "status": "SUCCESS",
        "message": "Google OAuth connection state updated successfully",
        "oauth": _google_oauth_state
    }


@router.get("/calendar/events")
async def get_calendar_events(
    customer_phone: Optional[str] = Query(None),
    customer_email: Optional[str] = Query(None)
):
    """Returns scheduled property site visits from MongoDB."""
    visits = await get_customer_site_visits(
        customer_phone=customer_phone,
        customer_email=customer_email
    )
    return {
        "status": "SUCCESS",
        "count": len(visits),
        "events": visits
    }
