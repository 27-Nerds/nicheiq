import { describe, it, expect } from 'vitest';
import {
  organization,
  website,
  breadcrumbList,
  itemList,
  article,
  faqPage,
  serializeJsonLd,
} from '../jsonld';

describe('organization()', () => {
  it('emits a stable @id used by other entities to reference the brand', () => {
    const org = organization() as Record<string, unknown>;
    expect(org['@id']).toBe('https://nicheiq.dev/#org');
    expect(org['@type']).toBe('Organization');
    expect(org.name).toBe('NicheIQ');
  });
});

describe('website()', () => {
  it('emits a stable @id and references organization via publisher @id', () => {
    const site = website() as Record<string, unknown>;
    expect(site['@id']).toBe('https://nicheiq.dev/#site');
    expect(site.publisher).toEqual({ '@id': 'https://nicheiq.dev/#org' });
  });
});

describe('breadcrumbList()', () => {
  it('sets `item` URL on every position EXCEPT the final one (current page)', () => {
    const bc = breadcrumbList([
      { name: 'Home', url: 'https://nicheiq.dev/' },
      { name: 'Ideas', url: 'https://nicheiq.dev/ideas' },
      { name: 'AI Tools', url: 'https://nicheiq.dev/ideas/ai-tools' },
    ]) as { itemListElement: Array<Record<string, unknown>> };

    expect(bc.itemListElement).toHaveLength(3);
    expect(bc.itemListElement[0].item).toBe('https://nicheiq.dev/');
    expect(bc.itemListElement[1].item).toBe('https://nicheiq.dev/ideas');
    // Final breadcrumb (current page) MUST omit `item` per Google's spec.
    expect('item' in bc.itemListElement[2]).toBe(false);
  });

  it('handles a single-entry breadcrumb correctly (no item field)', () => {
    const bc = breadcrumbList([{ name: 'Only', url: 'https://nicheiq.dev/x' }]) as {
      itemListElement: Array<Record<string, unknown>>;
    };
    expect('item' in bc.itemListElement[0]).toBe(false);
  });

  it('assigns positions starting at 1', () => {
    const bc = breadcrumbList([
      { name: 'A', url: 'https://x/a' },
      { name: 'B', url: 'https://x/b' },
    ]) as { itemListElement: Array<{ position: number }> };
    expect(bc.itemListElement[0].position).toBe(1);
    expect(bc.itemListElement[1].position).toBe(2);
  });
});

describe('itemList()', () => {
  it('omits numberOfItems when not provided', () => {
    const list = itemList([{ name: 'A', url: 'https://x/a' }]) as Record<string, unknown>;
    expect('numberOfItems' in list).toBe(false);
  });

  it('emits numberOfItems when provided', () => {
    const list = itemList([{ name: 'A', url: 'https://x/a' }], { numberOfItems: 42 }) as Record<
      string,
      unknown
    >;
    expect(list.numberOfItems).toBe(42);
  });
});

describe('article()', () => {
  it('defaults image to the brand logo when no image arg is provided', () => {
    const a = article({
      headline: 'Test',
      datePublished: '2026-01-01',
      dateModified: '2026-01-02',
      url: 'https://nicheiq.dev/idea/test',
    }) as Record<string, unknown>;
    expect(a.image).toBe('https://nicheiq.dev/niche-logo-beta.svg');
  });

  it('uses the provided image when supplied', () => {
    const a = article({
      headline: 'Test',
      datePublished: '2026-01-01',
      dateModified: '2026-01-02',
      url: 'https://nicheiq.dev/idea/test',
      image: 'https://nicheiq.dev/og/foo.png',
    }) as Record<string, unknown>;
    expect(a.image).toBe('https://nicheiq.dev/og/foo.png');
  });

  it('publisher references Organization by @id (not inlined)', () => {
    const a = article({
      headline: 'Test',
      datePublished: '2026-01-01',
      dateModified: '2026-01-02',
      url: 'https://nicheiq.dev/idea/test',
    }) as Record<string, unknown>;
    expect(a.publisher).toEqual({ '@id': 'https://nicheiq.dev/#org' });
  });

  it('author is a sub-organization with @id and parentOrganization link', () => {
    const a = article({
      headline: 'Test',
      datePublished: '2026-01-01',
      dateModified: '2026-01-02',
      url: 'https://nicheiq.dev/idea/test',
    }) as { author: Record<string, unknown> };
    expect(a.author['@id']).toBe('https://nicheiq.dev/#research-team');
    expect(a.author.parentOrganization).toEqual({ '@id': 'https://nicheiq.dev/#org' });
    expect(a.author.name).toBe('NicheIQ Research Team');
  });
});

describe('serializeJsonLd()', () => {
  // The closing-script-tag attack: a string containing '</script>' breaks
  // out of the surrounding <script type="application/ld+json"> block. We
  // escape the five characters that can produce that or related vectors.
  it('escapes < as \\u003c (closes the </script> attack)', () => {
    const out = serializeJsonLd({ s: '<script>' });
    expect(out).toContain('\\u003cscript');
    expect(out).not.toContain('<script>');
  });

  it('escapes > as \\u003e', () => {
    const out = serializeJsonLd({ s: 'a>b' });
    expect(out).toContain('a\\u003eb');
  });

  it('escapes & as \\u0026', () => {
    const out = serializeJsonLd({ s: 'a&b' });
    expect(out).toContain('a\\u0026b');
  });

  it('escapes U+2028 (line separator) as \\u2028', () => {
    const out = serializeJsonLd({ s: 'a b' });
    expect(out).toContain('a\\u2028b');
    expect(out).not.toContain(' ');
  });

  it('escapes U+2029 (paragraph separator) as \\u2029', () => {
    const out = serializeJsonLd({ s: 'a b' });
    expect(out).toContain('a\\u2029b');
    expect(out).not.toContain(' ');
  });

  it('produces output that parses back to original (round-trip via JSON.parse)', () => {
    const data = { headline: 'Foo<bar>baz&qux', n: 42 };
    const out = serializeJsonLd(data);
    // JSON.parse decodes \uXXXX escapes back to the original characters.
    expect(JSON.parse(out)).toEqual(data);
  });
});

describe('faqPage()', () => {
  it('emits FAQPage with mainEntity array of Question + acceptedAnswer', () => {
    const items = [
      { q: 'Question 1?', a: 'Answer 1.' },
      { q: 'Question 2?', a: 'Answer 2.' },
    ];
    const fp = faqPage(items) as {
      '@type': string;
      mainEntity: Array<Record<string, unknown>>;
    };
    expect(fp['@type']).toBe('FAQPage');
    expect(fp.mainEntity).toHaveLength(2);
    expect(fp.mainEntity[0]['@type']).toBe('Question');
    expect((fp.mainEntity[0].acceptedAnswer as Record<string, unknown>)['@type']).toBe(
      'Answer',
    );
  });

  // Visible-vs-schema text-identity guarantee — the schema side must NOT
  // transform the FAQ Q/A text. Combined with the structural fact that
  // CategoryFAQ.svelte renders {item.q} and {item.a} directly without any
  // transform, this gives us visible-vs-schema match by construction.
  it('does not transform Q/A text — schema mainEntity strings === input strings', () => {
    const items = [
      { q: 'How long would it take to build an AI tool?', a: 'Estimated 4-6 weeks.' },
      { q: "What's the typical CAC?", a: 'Roughly $35 organic, $90 paid.' },
      { q: 'Where do users discuss this?', a: 'Mostly r/programming and Hacker News.' },
    ];
    const fp = faqPage(items) as {
      mainEntity: Array<{ name: string; acceptedAnswer: { text: string } }>;
    };
    for (let i = 0; i < items.length; i++) {
      expect(fp.mainEntity[i].name).toBe(items[i].q);
      expect(fp.mainEntity[i].acceptedAnswer.text).toBe(items[i].a);
    }
  });

  it('round-trips through serializeJsonLd → JSON.parse without losing Q/A text', () => {
    const items = [
      { q: 'Q with <special> & "chars"?', a: 'Answer with U+2028 line break.' },
      { q: 'Plain question?', a: 'Plain answer.' },
    ];
    const fp = faqPage(items);
    const serialized = serializeJsonLd(fp);
    const decoded = JSON.parse(serialized) as typeof fp;
    expect(decoded).toEqual(fp);
  });
});
