<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { onMount } from 'svelte';
	import { initClerk } from '$lib/clerk';
	import { authState, verifyWithBackend, logout } from '$lib/auth.svelte';

	let { children } = $props();

	onMount(async () => {
		// Initialize theme from localStorage or default to dark
		const savedTheme = localStorage.getItem('theme');
		if (savedTheme === 'light') {
			document.documentElement.classList.add('light-theme');
		} else {
			document.documentElement.classList.remove('light-theme');
		}

		// Initialize Clerk and listen for auth state updates
		try {
			const clerk = await initClerk();
			if (clerk.user && !authState.isAuthenticated) {
				const ok = await verifyWithBackend();
				if (ok && window.location.pathname === '/') {
					window.location.href = '/dashboard';
				}
			}

			clerk.addListener(async (event: any) => {
				if (event.user && !authState.isAuthenticated) {
					const ok = await verifyWithBackend();
					if (ok && window.location.pathname === '/') {
						window.location.href = '/dashboard';
					}
				} else if (!event.user && authState.isAuthenticated) {
					logout();
				}
			});
		} catch (error) {
			console.warn('Clerk root initialization skipped or blocked by client:', error);
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Real Estate AI Assistant</title>
</svelte:head>

{@render children()}
