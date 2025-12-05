#!/usr/bin/env node

/**
 * NicheIQ Report Viewer - Add Report CLI
 *
 * Usage: node scripts/add-report.js <path-to-report.json>
 *
 * This script:
 * 1. Reads a NicheIQ report JSON file
 * 2. Generates a URL-friendly slug from the solution name
 * 3. Copies the report to src/lib/reports/{slug}.json
 * 4. Updates the reports index for the home page
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const REPORTS_DIR = join(__dirname, '..', 'src', 'lib', 'reports');

function slugify(text) {
	return text
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/(^-|-$)/g, '')
		.slice(0, 50);
}

function formatDate(dateStr) {
	try {
		const date = new Date(dateStr);
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	} catch {
		return dateStr || 'Unknown';
	}
}

function main() {
	const args = process.argv.slice(2);

	if (args.length === 0) {
		console.log(`
NicheIQ Report Viewer - Add Report CLI

Usage:
  node scripts/add-report.js <path-to-report.json>

Example:
  node scripts/add-report.js ../output/final_report_20251204_170429.json

This will:
  1. Read the report JSON file
  2. Generate a slug from the solution name
  3. Copy to src/lib/reports/{slug}.json
  4. Make it available at /reports/{slug}
`);
		process.exit(0);
	}

	const inputPath = args[0];

	// Check if input file exists
	if (!existsSync(inputPath)) {
		console.error(`Error: File not found: ${inputPath}`);
		process.exit(1);
	}

	// Read the report
	console.log(`Reading report from: ${inputPath}`);
	let report;
	try {
		const content = readFileSync(inputPath, 'utf-8');
		report = JSON.parse(content);
	} catch (error) {
		console.error(`Error reading JSON file: ${error.message}`);
		process.exit(1);
	}

	// Extract key info
	const solutionName = report.selected_solution_name || report.executive_dashboard?.recommended_solution_snapshot?.name || 'unknown';
	const niche = report.niche || 'Unknown niche';
	const generatedAt = report.generated_at || new Date().toISOString();

	// Generate slug
	const slug = slugify(solutionName);
	console.log(`Generated slug: ${slug}`);

	// Ensure reports directory exists
	if (!existsSync(REPORTS_DIR)) {
		mkdirSync(REPORTS_DIR, { recursive: true });
		console.log(`Created directory: ${REPORTS_DIR}`);
	}

	// Write report file
	const outputPath = join(REPORTS_DIR, `${slug}.json`);
	writeFileSync(outputPath, JSON.stringify(report, null, 2));
	console.log(`Saved report to: ${outputPath}`);

	// Summary
	console.log(`
✅ Report added successfully!

Solution: ${solutionName}
Niche: ${niche.slice(0, 80)}...
Generated: ${formatDate(generatedAt)}

View at: http://localhost:5173/reports/${slug}

To start the dev server:
  npm run dev
`);
}

main();
