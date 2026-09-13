import { Clerk } from "@clerk/clerk-js";
import { goto } from "$app/navigation";
import { verifyWithBackend } from "./auth.svelte";

// ── Singleton Clerk Instance ──
let clerkInstance: Clerk | null = null;
let clerkLoadPromise: Promise<Clerk> | null = null;

export const CLERK_PUBLISHABLE_KEY =
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ||
  "pk_test_Y29oZXJlbnQtZWVsLTk2MzguY2xlcmsuYWNjb3VudHMuZGV2JA";

export const CLERK_HOSTED_URL = "https://coherent-eel-9638.accounts.dev";

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
      const publishableKey = CLERK_PUBLISHABLE_KEY;

      if (!publishableKey) {
        throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY");
      }

      const clerk = new Clerk(publishableKey);
      await clerk.load();

      clerkInstance = clerk;
      return clerk;
    } catch (error) {
      clerkLoadPromise = null; // Allow retry on subsequent calls
      console.warn("Clerk initialization error (may be blocked by ad-blocker or offline):", error);
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
    console.warn("Failed to get Clerk session token:", error);
    return null;
  }
}

/**
 * Open Clerk's modal sign-in UI, or fallback gracefully to hosted redirect.
 */
export async function signIn(): Promise<void> {
  if (typeof window === "undefined") return;

  const returnTarget = `${window.location.origin}/dashboard`;
  const hostedSignInUrl = `${CLERK_HOSTED_URL}/sign-in?redirect_url=${encodeURIComponent(returnTarget)}`;

  try {
    const clerk = await initClerk();

    // If user is already signed in to Clerk, bypass modal and verify / enter dashboard
    if (clerk.user || clerk.session) {
      await verifyWithBackend().catch(() => {});
      if (window.location.pathname !== "/dashboard") {
        await goto("/dashboard");
      }
      return;
    }

    // Attempt modal sign-in using Clerk JS v5 properties
    try {
      clerk.openSignIn({
        fallbackRedirectUrl: "/dashboard",
        signUpFallbackRedirectUrl: "/dashboard",
      });
      return;
    } catch (modalErr: any) {
      console.warn("Clerk modal sign-in failed, checking error type:", modalErr);

      // If already signed in, Clerk raises cannot_render_single_session_enabled
      if (
        modalErr?.message?.includes("already signed in") ||
        modalErr?.code === "cannot_render_single_session_enabled"
      ) {
        await verifyWithBackend().catch(() => {});
        if (window.location.pathname !== "/dashboard") {
          await goto("/dashboard");
        }
        return;
      }

      // Try Clerk's redirectToSignIn helper with v5 redirectUrl
      try {
        await clerk.redirectToSignIn({ redirectUrl: returnTarget });
        return;
      } catch (redirectErr) {
        console.warn("clerk.redirectToSignIn also failed:", redirectErr);
      }
    }
  } catch (initErr) {
    console.warn("Clerk SDK unavailable (likely blocked by browser ad-blocker), falling back to hosted sign-in:", initErr);
  }

  // Graceful fallback for ad-blockers / script blockers: direct top-level navigation to hosted Clerk portal
  window.location.href = hostedSignInUrl;
}

/**
 * Open Clerk's modal sign-up UI, or fallback gracefully to hosted redirect.
 */
export async function signUp(): Promise<void> {
  if (typeof window === "undefined") return;

  const returnTarget = `${window.location.origin}/dashboard`;
  const hostedSignUpUrl = `${CLERK_HOSTED_URL}/sign-up?redirect_url=${encodeURIComponent(returnTarget)}`;

  try {
    const clerk = await initClerk();

    // If user is already signed in to Clerk, bypass modal and go to dashboard
    if (clerk.user || clerk.session) {
      await verifyWithBackend().catch(() => {});
      if (window.location.pathname !== "/dashboard") {
        await goto("/dashboard");
      }
      return;
    }

    // Attempt modal sign-up using Clerk JS v5 properties
    try {
      clerk.openSignUp({
        fallbackRedirectUrl: "/dashboard",
        signInFallbackRedirectUrl: "/dashboard",
      });
      return;
    } catch (modalErr: any) {
      console.warn("Clerk modal sign-up failed, checking error type:", modalErr);

      if (
        modalErr?.message?.includes("already signed in") ||
        modalErr?.code === "cannot_render_single_session_enabled"
      ) {
        await verifyWithBackend().catch(() => {});
        if (window.location.pathname !== "/dashboard") {
          await goto("/dashboard");
        }
        return;
      }

      // Try Clerk's redirectToSignUp helper with v5 redirectUrl
      try {
        await clerk.redirectToSignUp({ redirectUrl: returnTarget });
        return;
      } catch (redirectErr) {
        console.warn("clerk.redirectToSignUp also failed:", redirectErr);
      }
    }
  } catch (initErr) {
    console.warn("Clerk SDK unavailable (likely blocked by browser ad-blocker), falling back to hosted sign-up:", initErr);
  }

  // Graceful fallback for ad-blockers / script blockers: direct top-level navigation to hosted Clerk portal
  window.location.href = hostedSignUpUrl;
}

/**
 * Sign the user out of Clerk and clear the session.
 */
export async function signOut(): Promise<void> {
  try {
    const clerk = await initClerk();
    await clerk.signOut();
  } catch (error) {
    console.warn("Clerk sign-out failed:", error);
  }
}
