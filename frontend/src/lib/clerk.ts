/**
 * lib/clerk.ts
 * ────────────
 * Clerk SDK initialization and helper functions.
 *
 * This module handles:
 *   • Loading the Clerk JavaScript SDK in the browser
 *   • Providing functions to get the current session token
 *   • Sign-in, sign-up, and sign-out helpers (modal or redirect)
 */

import { Clerk } from "@clerk/clerk-js";

// ── Singleton Clerk Instance ──
let clerkInstance: Clerk | null = null;
let clerkLoadPromise: Promise<Clerk> | null = null;

/**
 * Initialize the Clerk SDK.
 * Safe to call multiple times — returns the same instance.
 */
export async function initClerk(): Promise<Clerk> {
  if (typeof window === "undefined") {
    throw new Error("Clerk can only be initialized in the browser");
  }

  // Return existing instance if already loaded
  if (clerkInstance) return clerkInstance;
  if (clerkLoadPromise) return clerkLoadPromise;

  clerkLoadPromise = (async () => {
    try {
      const publishableKey =
        import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ||
        "pk_test_Y29oZXJlbnQtZWVsLTk2MzguY2xlcmsuYWNjb3VudHMuZGV2JA";

      if (!publishableKey) {
        throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY");
      }

      const clerk = new Clerk(publishableKey);
      await clerk.load();

      clerkInstance = clerk;
      return clerk;
    } catch (error) {
      clerkLoadPromise = null; // Allow retry on subsequent click
      console.error("Clerk initialization error:", error);
      throw error;
    }
  })();

  return clerkLoadPromise;
}

/**
 * Get the current Clerk instance (must be initialized first).
 */
export function getClerk(): Clerk | null {
  return clerkInstance;
}

/**
 * Get the current session JWT token from Clerk.
 * Returns null if the user is not signed in.
 */
export async function getClerkToken(): Promise<string | null> {
  try {
    const clerk = await initClerk();

    if (!clerk.session) return null;

    const token = await clerk.session.getToken();
    return token;
  } catch (error) {
    console.error("Failed to get Clerk session token:", error);
    return null;
  }
}

/**
 * Open Clerk's modal sign-in UI.
 */
export async function signIn(): Promise<void> {
  try {
    const clerk = await initClerk();
    clerk.openSignIn();
  } catch (error) {
    console.error("Sign-in modal failed to open:", error);
    alert("Unable to open Sign In modal. Please disable any ad-blockers and ensure you have an active internet connection.");
  }
}

/**
 * Open Clerk's modal sign-up UI.
 */
export async function signUp(): Promise<void> {
  try {
    const clerk = await initClerk();
    clerk.openSignUp();
  } catch (error) {
    console.error("Sign-up modal failed to open:", error);
    alert("Unable to open Sign Up modal. Please disable any ad-blockers and ensure you have an active internet connection.");
  }
}

/**
 * Sign the user out of Clerk and clear the session.
 */
export async function signOut(): Promise<void> {
  try {
    const clerk = await initClerk();
    await clerk.signOut();
  } catch (error) {
    console.error("Clerk sign-out failed:", error);
  }
}

