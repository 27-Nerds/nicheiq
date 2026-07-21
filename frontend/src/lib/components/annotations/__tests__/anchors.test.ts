import { describe, expect, it } from 'vitest';
import {
  annotationAnchorChain,
  annotationAnchorChainAtPoint,
  deepestCommonAnnotationAnchorKey,
  outermostAnnotationAnchor,
  resolveStrokeGeometry,
} from '../anchors';

import { projectAnchoredPoint } from '../anchors';

describe('outermostAnnotationAnchor', () => {
  it('anchors each candidate point to its row across responsive layouts', () => {
    const surface = document.createElement('div');
    surface.innerHTML = `
      <section data-annotation-anchor="research-workbench">
        <div data-annotation-anchor="shortlist-candidates">
          <article data-annotation-anchor="candidate:one"><span id="one">One</span></article>
          <article data-annotation-anchor="candidate:two"><span id="two">Two</span></article>
        </div>
      </section>
    `;

    const one = surface.querySelector('#one');
    const two = surface.querySelector('#two');
    expect(one && outermostAnnotationAnchor(one, surface)?.dataset.annotationAnchor)
      .toBe('candidate:one');
    expect(two && outermostAnnotationAnchor(two, surface)?.dataset.annotationAnchor)
      .toBe('candidate:two');
  });

  it('uses the nearest modal region instead of the changing modal frame', () => {
    const surface = document.createElement('div');
    surface.dataset.annotationAnchor = 'solution-detail';
    surface.innerHTML = `
      <header data-annotation-anchor="solution-header"><span id="title">Title</span></header>
      <main data-annotation-anchor="solution-body:overview"><span id="body">Body</span></main>
    `;

    const title = surface.querySelector('#title');
    const body = surface.querySelector('#body');
    expect(title && outermostAnnotationAnchor(title, surface)?.dataset.annotationAnchor)
      .toBe('solution-header');
    expect(body && outermostAnnotationAnchor(body, surface)?.dataset.annotationAnchor)
      .toBe('solution-body:overview');
  });

  it('ignores the overlay canvas so hit testing can reach page content', () => {
    const surface = document.createElement('div');
    surface.dataset.annotationAnchor = 'solution-detail';
    const canvas = document.createElement('div');
    canvas.className = 'annotation-canvas';
    surface.append(canvas);

    expect(outermostAnnotationAnchor(canvas, surface)).toBeNull();
  });

  it('uses one common list anchor for a gesture spanning candidate rows', () => {
    const surface = document.createElement('div');
    surface.dataset.annotationAnchor = 'research:page';
    surface.innerHTML = `
      <section data-annotation-anchor="research-workbench">
        <div data-annotation-anchor="shortlist-candidates">
          <article data-annotation-anchor="candidate:one"><span id="one">One</span></article>
          <article data-annotation-anchor="candidate:two"><span id="two">Two</span></article>
        </div>
      </section>
    `;

    const chains = ['#one', '#two'].map((selector) =>
      annotationAnchorChain(surface.querySelector(selector)!, surface).map(
        (anchor) => anchor.dataset.annotationAnchor!,
      ),
    );

    expect(chains[0]).toEqual([
      'candidate:one',
      'shortlist-candidates',
      'research-workbench',
      'research:page',
    ]);
    expect(deepestCommonAnnotationAnchorKey(chains)).toBe('shortlist-candidates');
  });

  it('uses the modal root for a gesture spanning its header and body', () => {
    const surface = document.createElement('div');
    surface.dataset.annotationAnchor = 'solution-detail';
    surface.innerHTML = `
      <header data-annotation-anchor="solution-header"><span id="title">Title</span></header>
      <main data-annotation-anchor="solution-body:overview"><span id="body">Body</span></main>
    `;

    const chains = ['#title', '#body'].map((selector) =>
      annotationAnchorChain(surface.querySelector(selector)!, surface).map(
        (anchor) => anchor.dataset.annotationAnchor!,
      ),
    );

    expect(deepestCommonAnnotationAnchorKey(chains)).toBe('solution-detail');
  });
});

describe('annotationAnchorChainAtPoint', () => {
  function rect(left: number, top: number, width: number, height: number): DOMRect {
    return {
      left,
      top,
      width,
      height,
      right: left + width,
      bottom: top + height,
      x: left,
      y: top,
      toJSON: () => ({}),
    };
  }

  it('attaches annotation whitespace to the nearby title instead of the page shell', () => {
    const surface = document.createElement('div');
    surface.dataset.annotationAnchor = 'research:page';
    surface.innerHTML = `
      <header data-annotation-anchor="research-header">
        <div data-annotation-anchor="research-header-copy">
          <h1 data-annotation-anchor="research-header-title">Topic</h1>
        </div>
      </header>
    `;

    const boxes: Record<string, DOMRect> = {
      'research:page': rect(0, 0, 1200, 1800),
      'research-header': rect(80, 50, 1040, 180),
      'research-header-copy': rect(100, 70, 832, 130),
      'research-header-title': rect(100, 90, 620, 52),
    };
    for (const element of surface.querySelectorAll<HTMLElement>('[data-annotation-anchor]')) {
      element.getBoundingClientRect = () => boxes[element.dataset.annotationAnchor!];
    }
    surface.getBoundingClientRect = () => boxes['research:page'];

    expect(annotationAnchorChainAtPoint(surface, { x: 260, y: 62 }).map(
      (element) => element.dataset.annotationAnchor,
    )).toEqual([
      'research-header-title',
      'research-header-copy',
      'research-header',
      'research:page',
    ]);
  });

  it('keeps distant whitespace in the page coordinate frame', () => {
    const surface = document.createElement('div');
    surface.dataset.annotationAnchor = 'research:page';
    surface.innerHTML = '<h1 data-annotation-anchor="research-header-title">Topic</h1>';
    surface.getBoundingClientRect = () => rect(0, 0, 1200, 1800);
    const title = surface.querySelector<HTMLElement>('h1')!;
    title.getBoundingClientRect = () => rect(100, 90, 620, 52);

    expect(annotationAnchorChainAtPoint(surface, { x: 900, y: 900 }).map(
      (element) => element.dataset.annotationAnchor,
    )).toEqual(['research:page']);
  });
});

describe('projectAnchoredPoint', () => {
  it('keeps the same relative position when the destination layout is wider', () => {
    expect(projectAnchoredPoint(
      [0.5, 0.25],
      { left: 120, top: 80, width: 640, height: 240 },
      { left: 20, top: 30 },
    )).toEqual([420, 110]);
  });

  it('projects each axis independently when responsive reflow changes aspect ratio', () => {
    expect(projectAnchoredPoint(
      [0.5, 0.25],
      { left: 120, top: 80, width: 200, height: 320 },
      { left: 20, top: 30 },
      { left: 10, top: 5 },
    )).toEqual([190, 125]);
  });

  it('tracks both axes when the shared view renders the semantic region larger', () => {
    expect(projectAnchoredPoint(
      [0.5, 0.25],
      { left: 120, top: 80, width: 800, height: 320 },
      { left: 20, top: 30 },
      { left: 0, top: 0 },
      { width: 640, height: 240 },
    )).toEqual([500, 130]);
  });

  it('tracks responsive reflow when an anchor becomes narrower and taller', () => {
    expect(projectAnchoredPoint(
      [0.5, 0.25],
      { left: 120, top: 80, width: 320, height: 300 },
      { left: 20, top: 30 },
      { left: 0, top: 0 },
      { width: 640, height: 240 },
    )).toEqual([260, 125]);
  });
});

describe('resolveStrokeGeometry', () => {
  it('keeps a cross-candidate line in one shared list coordinate frame', () => {
    const geometry = resolveStrokeGeometry(
      [[0.1, 0.2], [0.2, 0.4]],
      [
        [
          { key: 'candidate:one', x: 0.4, y: 0.5, width: 600, height: 120 },
          { key: 'shortlist-candidates', x: 0.4, y: 0.2, width: 900, height: 600 },
          { key: 'research:page', x: 0.5, y: 0.4, width: 1200, height: 1800 },
        ],
        [
          { key: 'candidate:two', x: 0.3, y: 0.25, width: 600, height: 140 },
          { key: 'shortlist-candidates', x: 0.3, y: 0.55, width: 900, height: 600 },
          { key: 'research:page', x: 0.45, y: 0.52, width: 1200, height: 1800 },
        ],
      ],
    );

    expect(geometry).toEqual({
      points: [[0.4, 0.2], [0.3, 0.55]],
      anchor: { key: 'shortlist-candidates', width: 900, height: 600 },
    });
  });

  it('uses the header frame when a stroke crosses title text and whitespace', () => {
    const geometry = resolveStrokeGeometry(
      [[0.2, 0.1], [0.4, 0.2]],
      [
        [
          { key: 'research-header-title', x: 0.2, y: 0.5, width: 720, height: 52 },
          { key: 'research-header-copy', x: 0.2, y: 0.2, width: 832, height: 110 },
          { key: 'research-header', x: 0.2, y: 0.15, width: 832, height: 140 },
        ],
        [
          { key: 'research-header', x: 0.4, y: 0.6, width: 832, height: 140 },
        ],
      ],
    );

    expect(geometry).toEqual({
      points: [[0.2, 0.15], [0.4, 0.6]],
      anchor: { key: 'research-header', width: 832, height: 140 },
    });
  });

  it('uses the overlay root for a gesture spanning modal regions', () => {
    const geometry = resolveStrokeGeometry(
      [[0.1, 0.1], [0.2, 0.4]],
      [
        [
          { key: 'solution-header', x: 0.2, y: 0.4, width: 900, height: 180 },
          { key: 'solution-detail', x: 0.2, y: 0.1, width: 1000, height: 800 },
        ],
        [
          { key: 'solution-body:overview', x: 0.3, y: 0.2, width: 900, height: 500 },
          { key: 'solution-detail', x: 0.3, y: 0.5, width: 1000, height: 800 },
        ],
      ],
    );

    expect(geometry).toEqual({
      points: [[0.2, 0.1], [0.3, 0.5]],
      anchor: { key: 'solution-detail', width: 1000, height: 800 },
    });
  });

  it('uses one compact anchor for a gesture inside the same content region', () => {
    const geometry = resolveStrokeGeometry(
      [[0.1, 0.2], [0.2, 0.3]],
      [
        [{ key: 'research-header-title', x: 0.1, y: 0.2, width: 720, height: 52 }],
        [{ key: 'research-header-title', x: 0.2, y: 0.3, width: 720, height: 52 }],
      ],
    );

    expect(geometry).toEqual({
      points: [[0.1, 0.2], [0.2, 0.3]],
      anchor: { key: 'research-header-title', width: 720, height: 52 },
    });
  });
});
