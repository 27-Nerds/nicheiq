import { describe, it, expect, vi } from 'vitest';

vi.mock('../../config.js', () => ({
  CONFIG: { baseUrl: 'http://localhost:3000' },
}));

import { isValidReturnUrl } from '../returnUrl.js';

describe('isValidReturnUrl', () => {
  it('accepts same-origin relative paths (with or without a query string)', () => {
    expect(isValidReturnUrl('/ideas/saas-tools')).toBe(true);
    expect(isValidReturnUrl('/ideas/saas?collection=x')).toBe(true);
    expect(isValidReturnUrl('/')).toBe(true);
  });

  it('rejects protocol-relative, absolute, and off-origin URLs', () => {
    expect(isValidReturnUrl('//evil.com')).toBe(false);
    expect(isValidReturnUrl('https://evil.com/path')).toBe(false);
    expect(isValidReturnUrl('http://evil.com')).toBe(false);
    expect(isValidReturnUrl('javascript:alert(1)')).toBe(false);
  });

  it('rejects backslashes, non-leading-slash, and over-long inputs', () => {
    expect(isValidReturnUrl('/path\\with-backslash')).toBe(false);
    expect(isValidReturnUrl('ideas/no-leading-slash')).toBe(false);
    expect(isValidReturnUrl('/' + 'a'.repeat(600))).toBe(false);
  });

  it('rejects non-string inputs', () => {
    // @ts-expect-error runtime guard test
    expect(isValidReturnUrl(undefined)).toBe(false);
    // @ts-expect-error runtime guard test
    expect(isValidReturnUrl(123)).toBe(false);
  });
});
