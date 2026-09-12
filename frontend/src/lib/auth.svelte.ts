/**
 * lib/auth.ts
 * ───────────
 * Authentication state management and token operations.
 *
 * This module handles:
 *   • Reactive auth state (Svelte 5 $state)
 *   • Verifying Clerk tokens with the backend
 *   • Refreshing expired access tokens (via HTTP-only cookie)
 *   • Authenticated fetch wrapper with auto-refresh on 401
 *   • Logout flow (Clerk + backend)
 */

import { getClerkToken, signOut as clerkSignOut } from "./clerk";

// ── API Base URL ──
const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined" &&
  !window.location.hostname.includes("localhost") &&
  !window.location.hostname.includes("127.0.0.1")
    ? "https://real-estate-rag-backend.onrender.com"
    : "http://localhost:8000");


// ╭──────────────────────────────────────────────╮
// │   Reactive Auth State (Svelte 5)             │
// ╰──────────────────────────────────────────────╯

interface AuthUser {
  user_id: string;
  email: string | null;
}

/** Current access token — held in memory only (never in localStorage). */
let accessToken: string | null = $state(null);

/** Current authenticated user info. */
let currentUser: AuthUser | null = $state(null);

/** Whether auth is being checked / verified. */
let isLoading: boolean = $state(false);

/**
 * Export reactive getters so components can read auth state.
 *
 * Usage in Svelte components:
 *   import { authState } from '$lib/auth';
 *   {#if authState.isAuthenticated} ... {/if}
 */
export const authState = {
  get accessToken() { return accessToken; },
  get currentUser() { return currentUser; },
  get isAuthenticated() { return !!accessToken && !!currentUser; },
  get isLoading() { return isLoading; },
};


// ╭──────────────────────────────────────────────╮
// │   Verify Clerk Token with Backend            │
// ╰──────────────────────────────────────────────╯

/**
 * Send the Clerk session token to the backend for verification.
 * On success, receives a custom access token + user info.
 * The backend also sets a refresh token in an HTTP-only cookie.
 */
export async function verifyWithBackend(): Promise<boolean> {
  isLoading = true;

  try {
    // Get the Clerk session token
    const clerkToken = await getClerkToken();

    if (!clerkToken) {
      clearAuthState();
      return false;
    }

    // Send Clerk token to backend for verification
    const response = await fetch(`${API_BASE}/api/auth/clerk-verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",  // ← Important: sends/receives cookies
      body: JSON.stringify({ token: clerkToken }),
    });

    if (!response.ok) {
      console.error("Backend auth verification failed:", response.status);
      clearAuthState();
      return false;
    }

    const data = await response.json();

    // Store access token in memory & user info
    accessToken = data.access_token;
    currentUser = {
      user_id: data.user_id,
      email: data.email,
    };

    return true;

  } catch (error) {
    console.error("Auth verification error:", error);
    clearAuthState();
    return false;

  } finally {
    isLoading = false;
  }
}


// ╭──────────────────────────────────────────────╮
// │   Refresh Access Token                       │
// ╰──────────────────────────────────────────────╯

/**
 * Request a new access token using the refresh token cookie.
 * The cookie is sent automatically by the browser.
 */
export async function refreshAccessToken(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",  // ← Sends the HTTP-only cookie
    });

    if (!response.ok) {
      clearAuthState();
      return false;
    }

    const data = await response.json();
    accessToken = data.access_token;
    return true;

  } catch (error) {
    console.error("Token refresh failed:", error);
    clearAuthState();
    return false;
  }
}


// ╭──────────────────────────────────────────────╮
// │   Authenticated Fetch (Auto-Refresh on 401)  │
// ╰──────────────────────────────────────────────╯

/**
 * Wrapper around fetch() that:
 *   1. Attaches the access token as a Bearer header
 *   2. On 401, attempts a silent token refresh and retries once
 *
 * Usage:
 *   const res = await authenticatedFetch('/ask', { method: 'POST', body: ... });
 */
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const fullUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;

  // Attach access token
  const headers = new Headers(options.headers || {});
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  let response = await fetch(fullUrl, {
    ...options,
    headers,
    credentials: "include",
  });

  // If 401, try refreshing the token and retry once
  if (response.status === 401 && accessToken) {
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      const retryHeaders = new Headers(options.headers || {});
      retryHeaders.set("Authorization", `Bearer ${accessToken}`);

      response = await fetch(fullUrl, {
        ...options,
        headers: retryHeaders,
        credentials: "include",
      });
    }
  }

  return response;
}


// ╭──────────────────────────────────────────────╮
// │   Logout                                     │
// ╰──────────────────────────────────────────────╯

/**
 * Full logout flow:
 *   1. Clear backend refresh cookie
 *   2. Sign out of Clerk
 *   3. Clear local auth state
 */
export async function logout(): Promise<void> {
  try {
    // Tell backend to clear the HTTP-only cookie
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch (error) {
    console.error("Backend logout error:", error);
  }

  // Sign out of Clerk
  try {
    await clerkSignOut();
  } catch (error) {
    console.error("Clerk sign-out error:", error);
  }

  clearAuthState();
}


// ╭──────────────────────────────────────────────╮
// │   Internal Helpers                           │
// ╰──────────────────────────────────────────────╯

function clearAuthState(): void {
  accessToken = null;
  currentUser = null;
}
