/**
 * lib/auth.svelte.ts
 * ──────────────────
 * Authentication state management and token operations.
 *
 * This module handles:
 *   • Reactive auth state (Svelte 5 $state)
 *   • Verifying Clerk tokens with the backend
 *   • Request de-duplication to prevent race conditions
 *   • Refreshing expired access tokens (via HTTP-only cookie + fallback header)
 *   • Authenticated fetch wrapper with auto-refresh on 401
 *   • Logout flow (Clerk + backend)
 */

import { getClerkToken, getClerk, signOut as clerkSignOut } from "./clerk";

// ── API Base URL ──
const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== "undefined" &&
  !window.location.hostname.includes("localhost") &&
  !window.location.hostname.includes("127.0.0.1")
    ? "https://real-estate-rag-backend.onrender.com"
    : "http://localhost:8010");


// ╭──────────────────────────────────────────────╮
// │   Reactive Auth State (Svelte 5)             │
// ╰──────────────────────────────────────────────╯

export interface AuthUser {
  user_id: string;
  email: string | null;
  first_name?: string | null;
  last_name?: string | null;
  avatar_url?: string | null;
}

/** Current access token — held in memory only. */
let accessToken: string | null = $state(null);

/** Fallback refresh token stored in memory if cookies partitioned. */
let inMemoryRefreshToken: string | null = null;

/** Current authenticated user info. */
let currentUser: AuthUser | null = $state(null);

/** Whether auth is being checked / verified. */
let isLoading: boolean = $state(false);

/** In-flight verification promise to deduplicate concurrent verifyWithBackend calls. */
let inFlightVerification: Promise<boolean> | null = null;

/**
 * Export reactive getters so components can read auth state.
 */
export const authState = {
  get accessToken() { return accessToken; },
  get currentUser() { 
    if (currentUser) return currentUser;
    // Fallback to Clerk's user object directly if backend verification is still in flight
    const clerk = getClerk();
    if (clerk?.user) {
      return {
        user_id: clerk.user.id,
        email: clerk.user.primaryEmailAddress?.emailAddress || null,
        first_name: clerk.user.firstName || null,
        last_name: clerk.user.lastName || null,
        avatar_url: clerk.user.imageUrl || null,
      };
    }
    return null;
  },
  get isAuthenticated() { 
    // True if access token is active OR if user is signed into Clerk
    return (!!accessToken && !!currentUser) || !!getClerk()?.user;
  },
  get isBackendVerified() { return !!accessToken; },
  get isLoading() { return isLoading; },
};


// ╭──────────────────────────────────────────────╮
// │   Verify Clerk Token with Backend            │
// ╰──────────────────────────────────────────────╯

/**
 * Send the Clerk session token to the backend for verification.
 * On success, receives a custom access token + user info.
 * Deduplicates multiple concurrent calls into a single shared Promise.
 */
export async function verifyWithBackend(): Promise<boolean> {
  if (inFlightVerification) {
    return inFlightVerification;
  }

  inFlightVerification = (async () => {
    isLoading = true;

    try {
      const clerkToken = await getClerkToken();

      if (!clerkToken) {
        // If Clerk token isn't ready yet, don't clear state if user is present in Clerk
        const clerk = getClerk();
        if (!clerk?.user) {
          clearAuthState();
        }
        return false;
      }

      // Send Clerk token to backend for verification with retry for Render cold starts
      let response: Response | null = null;
      let attempts = 3;

      while (attempts > 0) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 12000);

          response = await fetch(`${API_BASE}/api/auth/clerk-verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",  // ← Important: sends/receives cookies
            body: JSON.stringify({ token: clerkToken }),
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          if (response.ok || (response.status < 500 && response.status !== 408)) {
            break;
          }
        } catch (networkErr: any) {
          if (attempts === 1) {
            console.warn("Backend auth verification connection error:", networkErr?.message || networkErr);
          }
        }

        attempts--;
        if (attempts > 0) {
          await new Promise((resolve) => setTimeout(resolve, 1500));
        }
      }

      if (!response || !response.ok) {
        console.warn("Backend auth verification response not OK:", response?.status);
        // If backend verification fails temporarily (e.g. backend asleep),
        // keep Clerk user information active in currentUser fallback
        return false;
      }

      const data = await response.json();

      // Store access token in memory
      accessToken = data.access_token;
      if (data.refresh_token) {
        inMemoryRefreshToken = data.refresh_token;
      }

      // Populate user info with Clerk fallbacks
      const clerk = getClerk();
      const clerkUser = clerk?.user;

      currentUser = {
        user_id: data.user_id,
        email: data.email || clerkUser?.primaryEmailAddress?.emailAddress || null,
        first_name: data.first_name || clerkUser?.firstName || null,
        last_name: data.last_name || clerkUser?.lastName || null,
        avatar_url: data.avatar_url || clerkUser?.imageUrl || null,
      };

      return true;

    } catch (error) {
      console.warn("Auth verification error:", error);
      return false;

    } finally {
      isLoading = false;
      inFlightVerification = null;
    }
  })();

  return inFlightVerification;
}


// ╭──────────────────────────────────────────────╮
// │   Refresh Access Token                       │
// ╰──────────────────────────────────────────────╯

/**
 * Request a new access token using the refresh token cookie or header fallback.
 */
export async function refreshAccessToken(): Promise<boolean> {
  try {
    const headers: Record<string, string> = {};
    if (inMemoryRefreshToken) {
      headers["x-refresh-token"] = inMemoryRefreshToken;
    }

    const response = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers,
      credentials: "include",  // ← Sends the HTTP-only cookie
    });

    if (!response.ok) {
      clearAuthState();
      return false;
    }

    const data = await response.json();
    accessToken = data.access_token;
    if (data.refresh_token) {
      inMemoryRefreshToken = data.refresh_token;
    }
    return true;

  } catch (error) {
    console.warn("Token refresh failed:", error);
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
 */
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const fullUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;

  // If we don't have an access token yet but Clerk is signed in, attempt verification first
  if (!accessToken && getClerk()?.user) {
    await verifyWithBackend().catch(() => {});
  }

  // Attach access token
  const headers = new Headers(options.headers || {});
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  if (inMemoryRefreshToken && !headers.has("x-refresh-token")) {
    headers.set("x-refresh-token", inMemoryRefreshToken);
  }

  let response = await fetch(fullUrl, {
    ...options,
    headers,
    credentials: "include",
  });

  // If 401, try refreshing the token and retry once
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();

    if (refreshed && accessToken) {
      const retryHeaders = new Headers(options.headers || {});
      retryHeaders.set("Authorization", `Bearer ${accessToken}`);
      if (inMemoryRefreshToken) {
        retryHeaders.set("x-refresh-token", inMemoryRefreshToken);
      }

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
    const headers: Record<string, string> = {};
    if (inMemoryRefreshToken) {
      headers["x-refresh-token"] = inMemoryRefreshToken;
    }
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      headers,
      credentials: "include",
    });
  } catch (error) {
    console.warn("Backend logout note:", error);
  }

  // Sign out of Clerk
  try {
    await clerkSignOut();
  } catch (error) {
    console.warn("Clerk sign-out note:", error);
  }

  clearAuthState();
}


// ╭──────────────────────────────────────────────╮
// │   Internal Helpers                           │
// ╰──────────────────────────────────────────────╯

function clearAuthState(): void {
  accessToken = null;
  currentUser = null;
  inMemoryRefreshToken = null;
}
