"""
routes/auth.py
──────────────
Authentication & User Profile endpoints for Clerk → Custom JWT flow with MongoDB.

Features:
  1. Clerk token verification & account syncing to MongoDB `users` & `profiles` collections.
  2. Cryptographic hashing of refresh tokens stored in `users.hashed_refresh_token`.
  3. Automatic `is_verified` tracking and `is_banned` enforcement (403 Forbidden for banned accounts).
  4. Token rotation on refresh (invalidates old refresh token).
  5. Profile retrieval & updating.
"""

from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Response, Depends, status
from pydantic import BaseModel

from app.core.security import (
    verify_clerk_token,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    set_refresh_cookie,
    clear_refresh_cookie,
    get_current_user,
    hash_token,
    verify_token_hash,
)
from app.db.mongodb import get_users_collection, get_profiles_collection


# ── Router Setup ──
router = APIRouter(prefix="/api/auth", tags=["Authentication & Profile"])


# ── Request / Response Schemas ──

class ClerkVerifyRequest(BaseModel):
    """Request body for Clerk token verification."""
    token: str


class AuthResponse(BaseModel):
    """Response after successful authentication."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: Optional[str] = None
    is_verified: bool = True
    is_banned: bool = False
    role: str = "user"


class RefreshResponse(BaseModel):
    """Response after successful token refresh."""
    access_token: str
    token_type: str = "bearer"


class ProfileUpdateRequest(BaseModel):
    """Schema for updating user preferences."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_locations: Optional[List[str]] = None
    budget_min_lakhs: Optional[float] = None
    budget_max_lakhs: Optional[float] = None
    preferred_bhk: Optional[int] = None
    saved_properties: Optional[List[str]] = None


# ╭──────────────────────────────────────────────╮
# │   POST /api/auth/clerk-verify                │
# ╰──────────────────────────────────────────────╯

@router.post("/clerk-verify", response_model=AuthResponse)
async def clerk_verify(body: ClerkVerifyRequest, response: Response):
    """
    Verify a Clerk session token, sync user and profile in MongoDB,
    store the hashed refresh token in `users`, and issue JWT tokens.
    """
    # Step 1 — Verify with Clerk
    clerk_payload = await verify_clerk_token(body.token)

    # Step 2 — Extract user info from Clerk payload
    user_id = clerk_payload.get("sub", "")
    email = clerk_payload.get("email", clerk_payload.get("email_address", ""))
    first_name = clerk_payload.get("first_name", "")
    last_name = clerk_payload.get("last_name", "")
    avatar_url = clerk_payload.get("image_url", clerk_payload.get("picture", ""))

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clerk token missing user ID (sub)",
        )

    users_col = get_users_collection()
    profiles_col = get_profiles_collection()

    # Step 3 — Check if account is banned
    existing_user = await users_col.find_one({"user_id": user_id})
    if existing_user and existing_user.get("is_banned", False) is True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been banned. Please contact support.",
        )

    # Step 4 — Generate access and refresh tokens
    token_data = {"sub": user_id, "email": email}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    # Step 5 — Hash refresh token for secure database storage
    hashed_refresh = hash_token(refresh_token)
    now = datetime.now(timezone.utc)

    # Step 6 — Upsert into `users` collection
    is_verified = bool(email)
    user_doc = {
        "$set": {
            "email": email,
            "hashed_refresh_token": hashed_refresh,
            "is_verified": is_verified,
            "updated_at": now,
            "last_login_at": now,
        },
        "$setOnInsert": {
            "user_id": user_id,
            "is_banned": False,
            "role": "user",
            "created_at": now,
        }
    }
    await users_col.update_one({"user_id": user_id}, user_doc, upsert=True)

    # Step 7 — Upsert into `profiles` collection
    profile_doc = {
        "$set": {
            "first_name": first_name or (existing_user and existing_user.get("first_name")) or "",
            "last_name": last_name or (existing_user and existing_user.get("last_name")) or "",
            "avatar_url": avatar_url or "",
            "updated_at": now,
        },
        "$setOnInsert": {
            "user_id": user_id,
            "phone": "",
            "preferred_locations": [],
            "budget_min_lakhs": None,
            "budget_max_lakhs": None,
            "saved_properties": [],
            "created_at": now,
        }
    }
    await profiles_col.update_one({"user_id": user_id}, profile_doc, upsert=True)

    # Step 8 — Set HTTP-only cookie & return response
    set_refresh_cookie(response, refresh_token)

    return AuthResponse(
        access_token=access_token,
        user_id=user_id,
        email=email,
        is_verified=is_verified,
        is_banned=False,
        role=existing_user.get("role", "user") if existing_user else "user"
    )


# ╭──────────────────────────────────────────────╮
# │   POST /api/auth/refresh                     │
# ╰──────────────────────────────────────────────╯

@router.post("/refresh", response_model=RefreshResponse)
async def refresh_access_token(request: Request, response: Response):
    """
    Issue a new access token and rotate the refresh token by validating the
    hashed refresh token in the `users` collection.
    """
    # 1. Read refresh token from HTTP-only cookie
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token found — please sign in",
        )

    # 2. Verify JWT signature & expiry
    payload = verify_refresh_token(refresh_token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
        )

    # 3. Check MongoDB `users` collection
    users_col = get_users_collection()
    user = await users_col.find_one({"user_id": user_id})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # 4. Check if account is banned
    if user.get("is_banned", False) is True:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been banned. Please contact support.",
        )

    # 5. Verify hashed refresh token against database (Prevents replay / revoked tokens)
    stored_hash = user.get("hashed_refresh_token", "")
    if not stored_hash or not verify_token_hash(refresh_token, stored_hash):
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or has been revoked",
        )

    # 6. Token Rotation: Issue brand new access token + new refresh token
    token_data = {"sub": user_id, "email": user.get("email", "")}
    new_access_token = create_access_token(data=token_data)
    new_refresh_token = create_refresh_token(data=token_data)

    # 7. Update hashed refresh token in database
    new_hashed_refresh = hash_token(new_refresh_token)
    await users_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "hashed_refresh_token": new_hashed_refresh,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )

    # 8. Set new cookie
    set_refresh_cookie(response, new_refresh_token)

    return RefreshResponse(access_token=new_access_token)


# ╭──────────────────────────────────────────────╮
# │   POST /api/auth/logout                      │
# ╰──────────────────────────────────────────────╯

@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Invalidate the stored hashed refresh token in MongoDB and clear the cookie.
    """
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = verify_refresh_token(refresh_token)
            user_id = payload.get("sub")
            if user_id:
                users_col = get_users_collection()
                await users_col.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "hashed_refresh_token": None,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    }
                )
        except Exception:
            pass

    clear_refresh_cookie(response)
    return {"message": "Successfully logged out"}


# ╭──────────────────────────────────────────────╮
# │   GET /api/auth/me                           │
# ╰──────────────────────────────────────────────╯

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    Protected route — returns authenticated user data and status.
    """
    user_id = user.get("sub")
    users_col = get_users_collection()
    profiles_col = get_profiles_collection()

    user_doc = await users_col.find_one({"user_id": user_id}, {"_id": 0, "hashed_refresh_token": 0})
    profile_doc = await profiles_col.find_one({"user_id": user_id}, {"_id": 0})

    return {
        "user_id": user_id,
        "email": user.get("email") or (user_doc and user_doc.get("email")),
        "is_verified": user_doc.get("is_verified", True) if user_doc else True,
        "is_banned": user_doc.get("is_banned", False) if user_doc else False,
        "role": user_doc.get("role", "user") if user_doc else "user",
        "profile": profile_doc or {}
    }


# ╭──────────────────────────────────────────────╮
# │   GET /api/auth/profile                      │
# ╰──────────────────────────────────────────────╯

@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    """
    Get user profile preferences and saved properties.
    """
    user_id = user.get("sub")
    profiles_col = get_profiles_collection()
    profile = await profiles_col.find_one({"user_id": user_id}, {"_id": 0})
    if not profile:
        profile = {"user_id": user_id}
    return profile


# ╭──────────────────────────────────────────────╮
# │   PUT /api/auth/profile                      │
# ╰──────────────────────────────────────────────╯

@router.put("/profile")
async def update_profile(body: ProfileUpdateRequest, user: dict = Depends(get_current_user)):
    """
    Update user profile preferences (phone, budget, locations, saved properties).
    """
    user_id = user.get("sub")
    profiles_col = get_profiles_collection()

    update_fields = {k: v for k, v in body.dict().items() if v is not None}
    update_fields["updated_at"] = datetime.now(timezone.utc)

    await profiles_col.update_one(
        {"user_id": user_id},
        {"$set": update_fields},
        upsert=True
    )

    updated_profile = await profiles_col.find_one({"user_id": user_id}, {"_id": 0})
    return {"message": "Profile updated successfully", "profile": updated_profile}


# ╭──────────────────────────────────────────────╮
# │   POST /api/auth/google-verify               │
# ╰──────────────────────────────────────────────╯

class GoogleVerifyRequest(BaseModel):
    access_token: Optional[str] = None
    code: Optional[str] = None
    redirect_uri: Optional[str] = None


@router.post("/google-verify", response_model=AuthResponse)
async def google_verify(body: GoogleVerifyRequest, response: Response):
    """
    Authenticate a user via Google OAuth access token or authorization code,
    sync to MongoDB `users` and `profiles`, and issue App JWT tokens.
    """
    from app.core.security import exchange_google_auth_code, fetch_google_user_profile

    access_token = body.access_token
    if body.code:
        token_data = await exchange_google_auth_code(body.code, body.redirect_uri)
        access_token = token_data.get("access_token", "")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'access_token' or 'code' must be provided."
        )

    google_user = await fetch_google_user_profile(access_token)
    user_id = f"google_{google_user.get('sub', '')}"
    email = google_user.get("email", "")
    full_name = google_user.get("name", "")
    avatar_url = google_user.get("picture", "")

    if not user_id or user_id == "google_":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google profile missing user ID."
        )

    users_col = get_users_collection()
    profiles_col = get_profiles_collection()
    now = datetime.now(timezone.utc)

    existing_user = await users_col.find_one({"user_id": user_id})
    if existing_user and existing_user.get("is_banned", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been banned."
        )

    # Issue App tokens
    app_access_token = create_access_token(data={"sub": user_id, "email": email})
    app_refresh_token = create_refresh_token(data={"sub": user_id, "email": email})
    hashed_refresh = hash_token(app_refresh_token)

    # Upsert user
    user_doc = {
        "user_id": user_id,
        "email": email,
        "auth_provider": "google",
        "hashed_refresh_token": hashed_refresh,
        "is_verified": google_user.get("email_verified", True),
        "is_banned": False,
        "role": existing_user.get("role", "user") if existing_user else "user",
        "last_login": now,
    }
    if not existing_user:
        user_doc["created_at"] = now

    await users_col.update_one({"user_id": user_id}, {"$set": user_doc}, upsert=True)

    # Upsert profile
    profile_doc = {
        "user_id": user_id,
        "first_name": full_name.split(" ")[0] if full_name else "",
        "last_name": " ".join(full_name.split(" ")[1:]) if full_name and len(full_name.split(" ")) > 1 else "",
        "avatar_url": avatar_url,
        "updated_at": now,
    }
    await profiles_col.update_one({"user_id": user_id}, {"$set": profile_doc}, upsert=True)

    # Set HTTP-only refresh cookie
    set_refresh_cookie(response, app_refresh_token)

    return AuthResponse(
        access_token=app_access_token,
        token_type="bearer",
        user_id=user_id,
        email=email,
        is_verified=True,
        is_banned=False,
        role=user_doc["role"]
    )

