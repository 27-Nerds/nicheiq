import type { TokenPackage } from '$lib/types/billing';

interface CreditTopUpContext {
  balance: number;
  required: number;
  stageName: string;
}

let _open = $state(false);
let _context = $state<CreditTopUpContext | null>(null);
let _cachedPackages = $state<TokenPackage[] | null>(null);

export const creditTopUp = {
  get open() { return _open; },
  set open(v: boolean) {
    _open = v;
    if (!v) _context = null;
  },
  get context() { return _context; },
  get cachedPackages() { return _cachedPackages; },
  set cachedPackages(v: TokenPackage[] | null) { _cachedPackages = v; },
  show(ctx: CreditTopUpContext) {
    _context = ctx;
    _open = true;
  },
};
