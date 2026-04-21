import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// OUTPUT_DIR should be absolute in prod (docker-compose sets /app/output).
// Relative values are resolved against process.cwd().
export function getOutputBaseDir(): string {
  const envDir = process.env.OUTPUT_DIR;
  if (envDir && envDir.length > 0) {
    return path.resolve(envDir);
  }
  return path.resolve(__dirname, '../../../output');
}

export function getAllowedAssetRoot(): string {
  return path.dirname(getOutputBaseDir());
}

export function resolveAssetPath(filePath: string): string {
  if (!filePath) {
    throw new Error('resolveAssetPath: empty path');
  }

  const segments = filePath.split(/[/\\]/);
  if (segments.some(s => s === '..')) {
    throw new Error('resolveAssetPath: parent traversal not allowed');
  }

  if (path.isAbsolute(filePath)) {
    return path.resolve(filePath);
  }

  return path.resolve(getAllowedAssetRoot(), filePath);
}
