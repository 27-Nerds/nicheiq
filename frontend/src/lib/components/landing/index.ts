// UI Components (still referenced via barrel imports elsewhere)
export { default as Button } from './ui/Button.svelte';
export { default as Card } from './ui/Card.svelte';
export { default as Badge } from './ui/Badge.svelte';
export { default as Input } from './ui/Input.svelte';
export { default as Accordion } from './ui/Accordion.svelte';

// Landing section components are imported by path directly from
// `(public)/+layout.svelte` and `(public)/+page.svelte`. Not re-exported here
// to keep tree-shaking explicit and to discourage accidental imports from
// non-public routes.
