import { describe, expect, it } from 'vitest';

import {
  catalogIdeaDeliveryFormat,
  catalogIdeaFormat,
  toIdeaPreview,
} from '../catalogService.js';

describe('catalogIdeaFormat()', () => {
  it('prefers delivery_format while leaving project_type as a fallback', () => {
    expect(
      catalogIdeaFormat({ delivery_format: 'browser-extension', project_type: 'saas' }),
    ).toBe('browser-extension');
    expect(catalogIdeaFormat({ project_type: 'marketplace' })).toBe('marketplace');
  });

  it('normalizes the public format slug and keeps the legacy default', () => {
    expect(catalogIdeaFormat({ delivery_format: ' Mobile App ' })).toBe('mobile-app');
    expect(catalogIdeaFormat({ delivery_format: '', project_type: 'other' })).toBe('other');
    expect(catalogIdeaFormat({ delivery_format: {}, project_type: 'directory' })).toBe('directory');
    expect(catalogIdeaFormat({})).toBe('saas');
  });
});

describe('catalog delivery-format provenance', () => {
  it('accepts exactly the closed 12-value vocabulary', () => {
    const formats = [
      'web-app', 'mobile-app', 'desktop-app', 'browser-extension', 'platform-plugin', 'api',
      'bot-assistant', 'data-product', 'report', 'service', 'physical-product', 'other',
    ];
    expect(formats.map((delivery_format) => catalogIdeaDeliveryFormat({ delivery_format }))).toEqual(
      formats,
    );
  });

  it('normalizes only an explicit delivery_format', () => {
    expect(catalogIdeaDeliveryFormat({ delivery_format: ' Browser Extension ' })).toBe(
      'browser-extension',
    );
    expect(catalogIdeaDeliveryFormat({ project_type: 'saas' })).toBeNull();
    expect(catalogIdeaDeliveryFormat({ delivery_format: {}, project_type: 'saas' })).toBeNull();
    expect(catalogIdeaDeliveryFormat({ delivery_format: 'saas' })).toBeNull();
    expect(catalogIdeaDeliveryFormat({ delivery_format: 'interactive kiosk' })).toBeNull();
    expect(catalogIdeaDeliveryFormat({ delivery_format: 'MOBILE_APP' })).toBe('mobile-app');
  });

  it('does not manufacture a public delivery format for a real legacy row', () => {
    expect(
      toIdeaPreview({ format: 'saas', projectType: 'saas', deliveryFormat: null }),
    ).toMatchObject({
      format: 'saas',
      project_type: 'saas',
      delivery_format: null,
    });
  });

  it('serializes the explicit delivery surface for a current row', () => {
    expect(
      toIdeaPreview({
        format: 'browser-extension',
        projectType: 'saas',
        deliveryFormat: 'browser-extension',
      }),
    ).toMatchObject({
      format: 'browser-extension',
      project_type: 'saas',
      delivery_format: 'browser-extension',
    });
  });
});
