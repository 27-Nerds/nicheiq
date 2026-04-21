import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import path from 'path';
import { resolveAssetPath, getOutputBaseDir, getAllowedAssetRoot } from '../assetPath.js';

const ORIGINAL_OUTPUT_DIR = process.env.OUTPUT_DIR;

describe('assetPath helpers', () => {
  beforeEach(() => {
    delete process.env.OUTPUT_DIR;
  });

  afterEach(() => {
    if (ORIGINAL_OUTPUT_DIR === undefined) {
      delete process.env.OUTPUT_DIR;
    } else {
      process.env.OUTPUT_DIR = ORIGINAL_OUTPUT_DIR;
    }
  });

  describe('getOutputBaseDir', () => {
    it('returns absolute OUTPUT_DIR when set', () => {
      process.env.OUTPUT_DIR = '/app/output';
      expect(getOutputBaseDir()).toBe('/app/output');
    });

    it('strips trailing slash from OUTPUT_DIR', () => {
      process.env.OUTPUT_DIR = '/app/output/';
      expect(getOutputBaseDir()).toBe('/app/output');
    });

    it('treats empty OUTPUT_DIR as unset', () => {
      process.env.OUTPUT_DIR = '';
      expect(getOutputBaseDir().endsWith(`${path.sep}output`)).toBe(true);
    });

    it('falls back to project-root output/ when unset', () => {
      const base = getOutputBaseDir();
      expect(base.endsWith(`${path.sep}nicheiq${path.sep}output`)).toBe(true);
    });
  });

  describe('getAllowedAssetRoot', () => {
    it('returns /app when OUTPUT_DIR=/app/output', () => {
      process.env.OUTPUT_DIR = '/app/output';
      expect(getAllowedAssetRoot()).toBe('/app');
    });

    it('returns project root when OUTPUT_DIR is unset', () => {
      const root = getAllowedAssetRoot();
      expect(root.endsWith(`${path.sep}nicheiq`)).toBe(true);
    });
  });

  describe('resolveAssetPath', () => {
    it('passes absolute path through (normalized)', () => {
      const abs = '/app/output/checkpoints/preview_report_abc.json';
      expect(resolveAssetPath(abs)).toBe(abs);
    });

    it('passes absolute path through regardless of OUTPUT_DIR', () => {
      process.env.OUTPUT_DIR = '/app/output';
      const abs = '/tmp/some/file.json';
      expect(resolveAssetPath(abs)).toBe(abs);
    });

    it('resolves relative path against /app when OUTPUT_DIR=/app/output (Docker)', () => {
      process.env.OUTPUT_DIR = '/app/output';
      const result = resolveAssetPath('output/checkpoints/preview_report_abc.json');
      expect(result).toBe('/app/output/checkpoints/preview_report_abc.json');
    });

    it('resolves relative path against project root when OUTPUT_DIR unset (dev)', () => {
      const result = resolveAssetPath('output/checkpoints/preview_report_abc.json');
      expect(result.endsWith(`${path.sep}nicheiq${path.sep}output${path.sep}checkpoints${path.sep}preview_report_abc.json`)).toBe(true);
      expect(result.startsWith(`${path.sep}output${path.sep}`)).toBe(false);
    });

    it('handles trailing slash in OUTPUT_DIR without producing double slash', () => {
      process.env.OUTPUT_DIR = '/app/output/';
      const result = resolveAssetPath('output/checkpoints/preview_report_abc.json');
      expect(result).toBe('/app/output/checkpoints/preview_report_abc.json');
    });

    it('rejects relative path with .. segments', () => {
      expect(() => resolveAssetPath('output/../etc/passwd')).toThrow(/parent traversal/);
    });

    it('rejects absolute path with .. segments', () => {
      expect(() => resolveAssetPath('/app/output/../../etc/passwd')).toThrow(/parent traversal/);
    });

    it('rejects empty string', () => {
      expect(() => resolveAssetPath('')).toThrow(/empty path/);
    });

    it('rejects path with .. in middle segment', () => {
      expect(() => resolveAssetPath('output/checkpoints/../../../etc/passwd')).toThrow(/parent traversal/);
    });

    it('accepts path with .. as part of a filename (not a segment)', () => {
      process.env.OUTPUT_DIR = '/app/output';
      const result = resolveAssetPath('output/file..json');
      expect(result).toBe('/app/output/file..json');
    });
  });
});
