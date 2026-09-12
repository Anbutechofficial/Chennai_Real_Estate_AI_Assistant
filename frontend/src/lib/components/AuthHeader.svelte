<!--
  AuthHeader.svelte
  ─────────────────
  Authentication UI component displayed in the header.
  Shows Sign In / Sign Up buttons when logged out,
  and user email + logout when logged in.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { initClerk, signIn, signUp, signOut as clerkSignOut } from '$lib/clerk';
  import { authState, verifyWithBackend, logout } from '$lib/auth.svelte';
  import { LogIn, LogOut, UserCircle, Loader } from '@lucide/svelte';

  let clerkReady = $state(false);
  let showUserMenu = $state(false);

  onMount(async () => {
    try {
      const clerk = await initClerk();

      // If user is already signed in via Clerk, verify with backend
      if (clerk.user) {
        await verifyWithBackend();
      }

      // Listen for Clerk auth state changes
      clerk.addListener(async (event: any) => {
        if (event.user && !authState.isAuthenticated) {
          // User signed in via Clerk modal or redirect
          const ok = await verifyWithBackend();
          if (ok && window.location.pathname === '/') {
            window.location.href = '/dashboard';
          }
        } else if (!event.user && authState.isAuthenticated) {
          // User signed out
          logout();
        }
      });
    } catch (error) {
      console.warn('Clerk initialization failed:', error);
    } finally {
      clerkReady = true;
    }
  });

  function handleSignIn() {
    signIn();
  }

  function handleSignUp() {
    signUp();
  }

  async function handleLogout() {
    showUserMenu = false;
    await logout();
  }

  function toggleUserMenu() {
    showUserMenu = !showUserMenu;
  }

  // Close menu when clicking outside
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.user-menu-container')) {
      showUserMenu = false;
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="auth-header" id="auth-header">
  {#if authState.isLoading || !clerkReady}
    <!-- Loading state -->
    <div class="auth-loading">
      <Loader size={18} class="spin-icon" />
    </div>

  {:else if authState.isAuthenticated && authState.currentUser}
    <!-- Logged-in state -->
    <div class="user-menu-container">
      <button
        class="user-avatar-btn"
        onclick={toggleUserMenu}
        aria-label="User menu"
        id="user-menu-toggle"
      >
        <UserCircle size={22} />
        <span class="user-email">
          {authState.currentUser.email || 'User'}
        </span>
      </button>

      {#if showUserMenu}
        <div class="user-dropdown glass-panel animate-fade-in" id="user-dropdown">
          <div class="dropdown-header">
            <UserCircle size={20} />
            <div class="dropdown-user-info">
              <span class="dropdown-email">{authState.currentUser.email || 'User'}</span>
              <span class="dropdown-id">ID: {authState.currentUser.user_id.slice(0, 12)}...</span>
            </div>
          </div>
          <hr class="dropdown-divider" />
          <button class="dropdown-item logout-btn" onclick={handleLogout} id="logout-button">
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      {/if}
    </div>

  {:else}
    <!-- Logged-out state -->
    <div class="auth-buttons">
      <button class="btn-sign-in" onclick={handleSignIn} id="sign-in-button">
        <LogIn size={16} />
        <span>Sign In</span>
      </button>
      <button class="btn-sign-up" onclick={handleSignUp} id="sign-up-button">
        <span>Sign Up</span>
      </button>
    </div>
  {/if}
</div>

<style>
  .auth-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* ── Loading ── */
  .auth-loading {
    display: flex;
    align-items: center;
    padding: 0 0.5rem;
  }

  :global(.spin-icon) {
    animation: spin 1s linear infinite;
    color: var(--text-muted);
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  /* ── Auth Buttons (Logged Out) ── */
  .auth-buttons {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .btn-sign-in {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 16px;
    min-height: 36px;
    border: 1px solid rgba(89, 255, 0, 0.35);
    border-radius: 8px;
    background: rgba(89, 255, 0, 0.05);
    color: #f8fafc;
    font-family: var(--font-display);
    font-weight: 500;
    font-size: 0.85rem;
    cursor: pointer;
    transition:
      background-color var(--transition-fast),
      border-color var(--transition-fast),
      color var(--transition-fast),
      transform var(--transition-fast),
      box-shadow var(--transition-fast);
  }

  .btn-sign-in:hover {
    background: rgba(89, 255, 0, 0.15);
    border-color: var(--color-accent);
    color: var(--color-accent);
    transform: translateY(-1px);
    box-shadow: 0 0 12px rgba(89, 255, 0, 0.2);
  }

  .btn-sign-up {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 16px;
    min-height: 36px;
    border: none;
    border-radius: 8px;
    background: var(--color-primary);
    color: #060913;
    font-family: var(--font-display);
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    transition:
      background-color var(--transition-fast),
      transform var(--transition-fast),
      box-shadow var(--transition-fast);
    box-shadow: 0 2px 8px rgba(89, 255, 0, 0.2);
  }

  .btn-sign-up:hover {
    background: var(--color-primary-hover);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(89, 255, 0, 0.35);
  }

  /* ── User Avatar Button (Logged In) ── */
  .user-menu-container {
    position: relative;
  }

  .user-avatar-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    min-height: 36px;
    border: 1px solid rgba(89, 255, 0, 0.35);
    border-radius: 99px;
    background: rgba(89, 255, 0, 0.05);
    color: #f8fafc;
    font-family: var(--font-display);
    font-weight: 500;
    font-size: 0.82rem;
    cursor: pointer;
    transition:
      background-color var(--transition-fast),
      border-color var(--transition-fast),
      color var(--transition-fast),
      box-shadow var(--transition-fast);
  }

  .user-avatar-btn:hover {
    background: rgba(89, 255, 0, 0.15);
    border-color: var(--color-accent);
    color: var(--color-accent);
    box-shadow: 0 0 12px rgba(89, 255, 0, 0.2);
  }

  .user-email {
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: inherit;
  }

  /* ── Dropdown ── */
  .user-dropdown {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    min-width: 240px;
    padding: 0.75rem;
    z-index: 100;
    border-radius: 12px;
  }

  .dropdown-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0.5rem;
    color: var(--text-primary);
  }

  .dropdown-user-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow: hidden;
  }

  .dropdown-email {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .dropdown-id {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-family: monospace;
  }

  .dropdown-divider {
    border: none;
    border-top: 1px solid var(--border-light);
    margin: 0.5rem 0;
  }

  .dropdown-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 10px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--text-secondary);
    font-family: var(--font-body);
    font-size: 0.82rem;
    cursor: pointer;
    transition:
      background-color var(--transition-fast),
      color var(--transition-fast);
  }

  .dropdown-item:hover {
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-primary);
  }

  .logout-btn:hover {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.08);
  }

  /* ── Mobile ── */
  @media (max-width: 640px) {
    .user-email {
      display: none;
    }

    .btn-sign-in span,
    .btn-sign-up span {
      display: none;
    }

    .btn-sign-in,
    .btn-sign-up {
      padding: 7px 10px;
    }
  }
</style>
