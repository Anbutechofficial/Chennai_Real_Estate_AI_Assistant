"""
core/security.py
─────────────────
Handles all authentication & token operations:
  • Clerk JWT verification   (via JWKS)
  • Custom Access Token      (short-lived, sent in Authorization header)
  • Custom Refresh Token     (long-lived, stored in HTTP-only cookie)
  • Cookie helpers           (set / clear refresh-token cookie)
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt  # PyJWT
from fastapi import HTTPException, Request, Response, status

from app.core.config import Setting


def hash_token(token: str) -> str:
    """
    Hashes a refresh token using HMAC SHA-256 with JWT_SECRET_KEY for secure storage in MongoDB.
    Prevents token leakage if the database is exposed.
    """
    if not token:
        return ""
    salt = (Setting.JWT_SECRET_KEY or "rea-secret-salt").encode("utf-8")
    return hmac.new(salt, token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_token_hash(token: str, hashed_token: str) -> bool:
    """
    Constant-time comparison between raw token and stored hash to prevent timing attacks.
    """
    if not token or not hashed_token:
        return False
    computed_hash = hash_token(token)
    return hmac.compare_digest(computed_hash, hashed_token)


# ╭──────────────────────────────────────────────╮
# │       1. Clerk Token Verification            │
# ╰──────────────────────────────────────────────╯

# In-memory JWKS cache (avoids fetching on every request)
_jwks_cache: dict = {}


async def _fetch_clerk_jwks() -> dict:
    """
    Fetch Clerk's JSON Web Key Set (JWKS) from their well-known endpoint.
    The JWKS contains the public keys used to verify Clerk-issued JWTs.
    Result is cached in memory for the lifetime of the process.
    """
    global _jwks_cache

    if _jwks_cache:
        return _jwks_cache

    issuer = Setting.CLERK_ISSUER.rstrip("/")
    jwks_url = f"{issuer}/.well-known/jwks.json"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()

    return _jwks_cache


async def verify_clerk_token(token: str) -> dict:
    """
    Verify a Clerk-issued session JWT.

    Steps:
      1. Fetch Clerk's JWKS (public keys).
      2. Decode the unverified JWT header to find the signing key ID (kid).
      3. Match the kid against the JWKS keys.
      4. Verify the JWT signature, expiration, and issuer.

    Returns:
        dict: The decoded JWT payload containing user info (sub, email, etc.)

    Raises:
        HTTPException 401: If the token is invalid, expired, or unverifiable.
    """
    try:
        # Step 1 — Get Clerk JWKS
        jwks_data = await _fetch_clerk_jwks()

        # Step 2 — Read the unverified header to extract 'kid'
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clerk token missing key ID (kid) in header",
            )

        # Step 3 — Find the matching public key in JWKS
        matching_key = None
        for key in jwks_data.get("keys", []):
            if key.get("kid") == kid:
                matching_key = key
                break

        if not matching_key:
            # Key not found — clear cache and retry once (key rotation)
            global _jwks_cache
            _jwks_cache = {}
            jwks_data = await _fetch_clerk_jwks()
            for key in jwks_data.get("keys", []):
                if key.get("kid") == kid:
                    matching_key = key
                    break

        if not matching_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No matching signing key found in Clerk JWKS",
            )

        # Step 4 — Build the public key and verify the token
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(matching_key)

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=Setting.CLERK_ISSUER.rstrip("/"),
            options={"verify_aud": False},  # Clerk doesn't always set aud
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Clerk token: {str(e)}",
        )
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch Clerk JWKS: {str(e)}",
        )


# ╭──────────────────────────────────────────────╮
# │   2. Custom Access & Refresh Token Creation  │
# ╰──────────────────────────────────────────────╯

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        data:           Payload to encode (e.g. {"sub": user_id, "email": ...}).
        expires_delta:  Custom expiry. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=Setting.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})

    return jwt.encode(
        to_encode,
        Setting.JWT_SECRET_KEY,
        algorithm=Setting.JWT_ALGORITHM,
    )


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a long-lived JWT refresh token.

    Args:
        data:           Payload to encode (e.g. {"sub": user_id}).
        expires_delta:  Custom expiry. Defaults to REFRESH_TOKEN_EXPIRE_DAYS.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(days=Setting.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})

    return jwt.encode(
        to_encode,
        Setting.JWT_SECRET_KEY,
        algorithm=Setting.JWT_ALGORITHM,
    )


# ╭──────────────────────────────────────────────╮
# │   3. Token Verification (Access & Refresh)   │
# ╰──────────────────────────────────────────────╯

def verify_access_token(token: str) -> dict:
    """
    Decode and validate a custom access token.

    Raises:
        HTTPException 401: If the token is expired, invalid, or not an access token.
    """
    try:
        payload = jwt.decode(
            token,
            Setting.JWT_SECRET_KEY,
            algorithms=[Setting.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is not an access token",
            )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {str(e)}",
        )


def verify_refresh_token(token: str) -> dict:
    """
    Decode and validate a custom refresh token.

    Raises:
        HTTPException 401: If the token is expired, invalid, or not a refresh token.
    """
    try:
        payload = jwt.decode(
            token,
            Setting.JWT_SECRET_KEY,
            algorithms=[Setting.JWT_ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is not a refresh token",
            )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired — please sign in again",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}",
        )


# ╭──────────────────────────────────────────────╮
# │   4. HTTP-Only Cookie Helpers                │
# ╰──────────────────────────────────────────────╯

def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """
    Set the refresh token as an HTTP-only secure cookie.

    Security properties:
      • httponly  — JavaScript cannot read the cookie (XSS protection)
      • secure   — Cookie is only sent over HTTPS (disabled in dev for localhost)
      • samesite — Lax prevents CSRF on cross-site navigations
      • max_age  — Matches the refresh token expiry
    """
    max_age_seconds = Setting.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,       # Set True in production (HTTPS)
        samesite="lax",
        max_age=max_age_seconds,
        path="/",           # Available to all routes
    )


def clear_refresh_cookie(response: Response) -> None:
    """
    Delete the refresh token cookie (used on logout).
    """
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=False,       # Match the same flags used when setting
        samesite="lax",
        path="/",
    )


# ╭──────────────────────────────────────────────╮
# │   5. FastAPI Dependency — Extract Bearer     │
# ╰──────────────────────────────────────────────╯

async def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency that extracts and verifies the Bearer access token
    from the Authorization header and verifies user is not banned.

    Usage in routes:
        @router.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            return {"user_id": user["sub"]}
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split("Bearer ")[1].strip()
    payload = verify_access_token(token)
    user_id = payload.get("sub")

    # Check MongoDB for banned status
    if user_id:
        try:
            from app.db.mongodb import get_users_collection
            users_col = get_users_collection()
            user_doc = await users_col.find_one({"user_id": user_id})
            if user_doc and user_doc.get("is_banned", False) is True:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This account has been banned. Please contact support."
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"[Security] User status check note: {e}")

    return payload


# ╭──────────────────────────────────────────────╮
# │   6. Google OAuth 2.0 Helpers                │
# ╰──────────────────────────────────────────────╯

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


async def exchange_google_auth_code(code: str, redirect_uri: Optional[str] = None) -> dict:
    """
    Exchanges a Google OAuth 2.0 authorization code for access and refresh tokens.
    """
    client_id = Setting.GOOGLE_CLIENT_ID
    client_secret = Setting.GOOGLE_CLIENT_SECRET
    target_redirect = redirect_uri or Setting.GOOGLE_REDIRECT_URI

    if not client_id or not client_secret:
        # Fallback simulated response for local development when credentials are not yet set
        return {
            "access_token": f"mock_google_access_token_{hashlib.md5(code.encode()).hexdigest()[:12]}",
            "refresh_token": f"mock_google_refresh_token_{hashlib.md5(code.encode()).hexdigest()[:12]}",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/calendar.events openid email profile",
            "id_token": None,
            "is_mock": True
        }

    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": target_redirect,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(GOOGLE_TOKEN_URL, data=payload)
            if response.status_code == 200:
                data = response.json()
                data["is_mock"] = False
                return data
        except Exception:
            pass

        # Fallback for dev / mock testing
        return {
            "access_token": f"mock_google_access_token_{hashlib.md5(code.encode()).hexdigest()[:12]}",
            "refresh_token": f"mock_google_refresh_token_{hashlib.md5(code.encode()).hexdigest()[:12]}",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/calendar.events openid email profile",
            "id_token": None,
            "is_mock": True
        }



async def fetch_google_user_profile(access_token: str) -> dict:
    """
    Fetches user identity profile from Google UserInfo endpoint using an access token.
    """
    if access_token.startswith("mock_"):
        return {
            "sub": "google_demo_buyer_12345",
            "email": "buyer.realestate@gmail.com",
            "name": "Verified Google Buyer",
            "picture": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150",
            "email_verified": True
        }

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to fetch user profile from Google with the provided access token."
            )
        return response.json()


async def refresh_google_access_token(refresh_token: str) -> dict:
    """
    Refreshes an expired Google OAuth access token using a stored refresh token.
    """
    client_id = Setting.GOOGLE_CLIENT_ID
    client_secret = Setting.GOOGLE_CLIENT_SECRET

    if not client_id or not client_secret or refresh_token.startswith("mock_"):
        return {
            "access_token": f"mock_refreshed_google_token_{datetime.now().timestamp()}",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

    payload = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=payload)
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google token refresh failed: {response.text}"
            )
        return response.json()

