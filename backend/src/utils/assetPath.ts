import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Resolve asset file path - handles both absolute (Docker) and relative (dev) paths
 */
export function resolveAssetPath(filePath: string): string {
  if (path.isAbsolute(filePath)) {
    return filePath; // Docker: already absolute
  }
  // Dev: resolve relative to project root (parent of backend/)
  return path.resolve(__dirname, '../../../', filePath);
}
