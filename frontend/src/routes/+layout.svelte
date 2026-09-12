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
				await verifyWithBackend();
			}

			clerk.addListener((event: any) => {
				if (event.user && !authState.isAuthenticated) {
					verifyWithBackend();
				} else if (!event.user && authState.isAuthenticated) {
					logout();
				}
			});
		} catch (error) {
			console.error('Clerk root initialization failed:', error);
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Real Estate AI Assistant</title>
</svelte:head>

{@render children()}
