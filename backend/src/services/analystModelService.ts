import { CONFIG } from '../config.js';
import { prisma } from './db.js';

export const ANALYST_MODEL_SETTING_KEY = 'analyst_chat_model';

export interface AnalystModelPricing {
  input: number;
  output: number;
  cacheWrite?: number;
  cacheRead?: number;
}

export interface AnalystModelOption {
  id: string;
  pricing: AnalystModelPricing;
}

export interface AnalystTokenUsage {
  inputTokens: number;
  outputTokens: number;
  cacheWriteTokens: number;
  cacheReadTokens: number;
}

/**
 * Models intentionally exposed to administrators. Keeping the allowlist and price
 * metadata together prevents selecting a model whose chat cost cannot be accounted.
 * Prices are USD per one million tokens.
 */
export const ANALYST_MODEL_OPTIONS: readonly AnalystModelOption[] = [
  {
    id: 'gpt-5.6-luna',
    pricing: { input: 0.2, output: 1.2, cacheWrite: 0.25, cacheRead: 0.02 },
  },
  { id: 'gpt-5-mini', pricing: { input: 0.25, output: 2.0, cacheRead: 0.025 } },
  { id: 'gpt-5-nano', pricing: { input: 0.05, output: 0.4, cacheRead: 0.005 } },
  { id: 'gpt-5', pricing: { input: 1.25, output: 10.0, cacheRead: 0.125 } },
  { id: 'gpt-4.1-mini', pricing: { input: 0.4, output: 1.6, cacheRead: 0.1 } },
  { id: 'gpt-4.1-nano', pricing: { input: 0.1, output: 0.4, cacheRead: 0.025 } },
  { id: 'gpt-4o-mini', pricing: { input: 0.15, output: 0.6 } },
] as const;

const MODEL_BY_ID = new Map(ANALYST_MODEL_OPTIONS.map((option) => [option.id, option]));

export function isSupportedAnalystModel(value: string): boolean {
  return MODEL_BY_ID.has(value);
}

export function getDefaultAnalystModel(): string {
  return CONFIG.chatModel || 'gpt-5-mini';
}

/** Resolve once per top-level analyst operation. Callers must pass the returned model
 * through every round so an admin update cannot switch a response midway through. */
export async function resolveAnalystModel(): Promise<string> {
  try {
    // Some isolated route tests intentionally provide only the Prisma delegates used
    // by that route. Treat an absent settings delegate exactly like no override.
    if (!prisma.appSettings?.findUnique) return getDefaultAnalystModel();
    const setting = await prisma.appSettings.findUnique({
      where: { key: ANALYST_MODEL_SETTING_KEY },
      select: { value: true },
    });
    if (!setting) return getDefaultAnalystModel();
    if (isSupportedAnalystModel(setting.value)) return setting.value;
    console.warn(
      `[analystModel] Ignoring unsupported persisted model "${setting.value}"; ` +
      `using deployment default "${getDefaultAnalystModel()}"`,
    );
  } catch (error) {
    console.error('[analystModel] Failed to resolve model setting; using deployment default:', error);
  }
  return getDefaultAnalystModel();
}

function asNonNegativeNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0;
}

/** Normalize OpenAI/OpenRouter-compatible usage without guessing cache activity. */
export function normalizeAnalystUsage(usage: unknown): AnalystTokenUsage {
  const raw = (usage ?? {}) as Record<string, unknown>;
  const details = (raw.prompt_tokens_details ?? raw.input_tokens_details ?? {}) as Record<string, unknown>;
  const totalInput = asNonNegativeNumber(raw.prompt_tokens ?? raw.input_tokens);
  const outputTokens = asNonNegativeNumber(raw.completion_tokens ?? raw.output_tokens);
  const cacheReadTokens = asNonNegativeNumber(
    details.cached_tokens ?? raw.cache_read_input_tokens ?? raw.cache_read_tokens,
  );
  const cacheWriteTokens = asNonNegativeNumber(
    details.cache_write_tokens ?? raw.cache_creation_input_tokens ?? raw.cache_write_tokens,
  );
  return {
    inputTokens: Math.max(0, totalInput - cacheReadTokens - cacheWriteTokens),
    outputTokens,
    cacheWriteTokens,
    cacheReadTokens,
  };
}

export function addAnalystUsage(target: AnalystTokenUsage, usage: AnalystTokenUsage): void {
  target.inputTokens += usage.inputTokens;
  target.outputTokens += usage.outputTokens;
  target.cacheWriteTokens += usage.cacheWriteTokens;
  target.cacheReadTokens += usage.cacheReadTokens;
}

export function estimateAnalystCostUsd(model: string, usage: AnalystTokenUsage): number {
  const separator = model.lastIndexOf('/');
  const baseModel = separator >= 0 ? model.slice(separator + 1) : model;
  const pricing = MODEL_BY_ID.get(baseModel)?.pricing ?? MODEL_BY_ID.get('gpt-5-mini')!.pricing;
  return (
    usage.inputTokens * pricing.input +
    usage.outputTokens * pricing.output +
    usage.cacheWriteTokens * (pricing.cacheWrite ?? pricing.input) +
    usage.cacheReadTokens * (pricing.cacheRead ?? pricing.input)
  ) / 1_000_000;
}

export function emptyAnalystUsage(): AnalystTokenUsage {
  return { inputTokens: 0, outputTokens: 0, cacheWriteTokens: 0, cacheReadTokens: 0 };
}
