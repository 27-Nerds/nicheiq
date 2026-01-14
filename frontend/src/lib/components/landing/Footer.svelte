<script lang="ts">
	import { Github, Twitter, Linkedin } from 'lucide-svelte';

	const currentYear = new Date().getFullYear();

	const links = {
		product: [
			{ name: 'Features', href: '#how-it-works' },
			{ name: 'Pricing', href: '#pricing' },
			{ name: 'FAQ', href: '#faq' },
			{ name: 'Sample Report', href: '#sample-report' }
		],
		company: [
			{ name: 'About', href: '#' },
			{ name: 'Blog', href: '#' },
			{ name: 'Contact', href: 'mailto:hello@nicheiq.com' }
		],
		legal: [
			{ name: 'Privacy Policy', href: '#' },
			{ name: 'Terms of Service', href: '#' }
		]
	};

	const social = [
		{ name: 'Twitter', icon: Twitter, href: '#' },
		{ name: 'GitHub', icon: Github, href: '#' },
		{ name: 'LinkedIn', icon: Linkedin, href: '#' }
	];
</script>

<footer class="bg-bg-base border-t border-border">
	<div class="max-w-6xl mx-auto px-6 lg:px-12 py-16">
		<div class="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
			<!-- Brand -->
			<div class="md:col-span-1">
				<a href="/" class="inline-flex items-center gap-3 mb-4 group">
					<div class="w-10 h-10 rounded-lg bg-accent/10 border border-accent/50 flex items-center justify-center group-hover:shadow-glow transition-shadow">
						<span class="text-accent font-display font-bold text-lg">N</span>
					</div>
					<span class="font-display font-bold text-xl text-text-primary">NicheIQ</span>
				</a>
				<p class="text-sm text-text-muted leading-relaxed mb-6">
					AI-powered market research that actually works. Validated data, verified sources, zero
					hallucination.
				</p>

				<!-- Social Links -->
				<div class="flex items-center gap-3">
					{#each social as item}
						<a
							href={item.href}
							class="w-10 h-10 rounded-lg bg-bg-surface border border-border flex items-center justify-center text-text-muted hover:text-accent hover:border-accent/50 transition-all"
							aria-label={item.name}
						>
							<item.icon class="w-5 h-5" />
						</a>
					{/each}
				</div>
			</div>

			<!-- Product Links -->
			<div>
				<h4 class="font-display font-semibold text-text-primary mb-4">Product</h4>
				<ul class="space-y-3">
					{#each links.product as link}
						<li>
							<a
								href={link.href}
								class="text-sm text-text-muted hover:text-accent transition-colors"
							>
								{link.name}
							</a>
						</li>
					{/each}
				</ul>
			</div>

			<!-- Company Links -->
			<div>
				<h4 class="font-display font-semibold text-text-primary mb-4">Company</h4>
				<ul class="space-y-3">
					{#each links.company as link}
						<li>
							<a
								href={link.href}
								class="text-sm text-text-muted hover:text-accent transition-colors"
							>
								{link.name}
							</a>
						</li>
					{/each}
				</ul>
			</div>

			<!-- Legal Links -->
			<div>
				<h4 class="font-display font-semibold text-text-primary mb-4">Legal</h4>
				<ul class="space-y-3">
					{#each links.legal as link}
						<li>
							<a
								href={link.href}
								class="text-sm text-text-muted hover:text-accent transition-colors"
							>
								{link.name}
							</a>
						</li>
					{/each}
				</ul>
			</div>
		</div>

		<!-- Bottom Bar -->
		<div class="pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4">
			<p class="text-sm text-text-muted">
				&copy; {currentYear} NicheIQ. All rights reserved.
			</p>

			<p class="text-sm text-text-muted">
				Built with
				<span class="text-accent font-medium">CrewAI</span>
				+
				<span class="text-accent-light font-medium">Multi-Agent AI</span>
			</p>
		</div>
	</div>
</footer>
