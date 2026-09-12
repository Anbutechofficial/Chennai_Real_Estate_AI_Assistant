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
    const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

    if (!publishableKey) {
      throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY in .env");
    }

    const clerk = new Clerk(publishableKey);
    await clerk.load();

    clerkInstance = clerk;
    return clerk;
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
  const clerk = await initClerk();

  if (!clerk.session) return null;

  try {
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
  const clerk = await initClerk();
  clerk.openSignIn();
}

/**
 * Open Clerk's modal sign-up UI.
 */
export async function signUp(): Promise<void> {
  const clerk = await initClerk();
  clerk.openSignUp();
}

/**
 * Sign the user out of Clerk and clear the session.
 */
export async function signOut(): Promise<void> {
  const clerk = await initClerk();
  await clerk.signOut();
}
