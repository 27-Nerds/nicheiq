import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { writeFile, readFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';

const DATA_DIR = './data';
const WAITLIST_FILE = join(DATA_DIR, 'waitlist.json');

interface WaitlistEntry {
	email: string;
	timestamp: string;
	source?: string;
}

async function ensureDataDir() {
	if (!existsSync(DATA_DIR)) {
		await mkdir(DATA_DIR, { recursive: true });
	}
}

async function getWaitlist(): Promise<WaitlistEntry[]> {
	try {
		await ensureDataDir();
		if (!existsSync(WAITLIST_FILE)) {
			return [];
		}
		const data = await readFile(WAITLIST_FILE, 'utf-8');
		return JSON.parse(data);
	} catch {
		return [];
	}
}

async function saveWaitlist(entries: WaitlistEntry[]) {
	await ensureDataDir();
	await writeFile(WAITLIST_FILE, JSON.stringify(entries, null, 2));
}

export const POST: RequestHandler = async ({ request }) => {
	try {
		const { email, timestamp, source } = await request.json();

		// Validate email
		if (!email || typeof email !== 'string') {
			return json({ error: 'Email is required' }, { status: 400 });
		}

		const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		if (!emailRegex.test(email)) {
			return json({ error: 'Invalid email format' }, { status: 400 });
		}

		// Get existing waitlist
		const waitlist = await getWaitlist();

		// Check if email already exists
		if (waitlist.some((entry) => entry.email.toLowerCase() === email.toLowerCase())) {
			return json({ error: 'Email already registered' }, { status: 409 });
		}

		// Add new entry
		const newEntry: WaitlistEntry = {
			email: email.toLowerCase(),
			timestamp: timestamp || new Date().toISOString(),
			source
		};

		waitlist.push(newEntry);
		await saveWaitlist(waitlist);

		return json({
			success: true,
			message: 'Successfully joined the waitlist!',
			count: waitlist.length
		});
	} catch (error) {
		console.error('Waitlist error:', error);
		return json({ error: 'Failed to join waitlist' }, { status: 500 });
	}
};

export const GET: RequestHandler = async () => {
	const waitlist = await getWaitlist();
	return json({ count: waitlist.length });
};
