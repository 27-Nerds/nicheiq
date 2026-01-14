import { writable } from 'svelte/store';

interface WaitlistState {
	email: string;
	status: 'idle' | 'loading' | 'success' | 'error';
	error: string;
	count: number;
}

function createWaitlistStore() {
	const { subscribe, set, update } = writable<WaitlistState>({
		email: '',
		status: 'idle',
		error: '',
		count: 847 // Starting count for social proof
	});

	return {
		subscribe,
		setEmail: (email: string) => update((state) => ({ ...state, email })),
		submit: async (email: string) => {
			update((state) => ({ ...state, status: 'loading', error: '' }));

			try {
				// Simulate API call - replace with actual endpoint
				const response = await fetch('/api/waitlist', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ email, timestamp: new Date().toISOString() })
				});

				if (!response.ok) {
					throw new Error('Failed to join waitlist');
				}

				update((state) => ({
					...state,
					status: 'success',
					email: '',
					count: state.count + 1
				}));
			} catch (error) {
				update((state) => ({
					...state,
					status: 'error',
					error: error instanceof Error ? error.message : 'Something went wrong'
				}));
			}
		},
		reset: () =>
			update((state) => ({
				...state,
				status: 'idle',
				error: ''
			}))
	};
}

export const waitlist = createWaitlistStore();
