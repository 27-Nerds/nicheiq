import OpenAI from 'openai';
import type {
  ChatCompletion,
  ChatCompletionChunk,
  ChatCompletionCreateParamsNonStreaming,
  ChatCompletionCreateParamsStreaming,
  ChatCompletionMessageParam,
  ChatCompletionTool,
  ChatCompletionToolChoiceOption,
} from 'openai/resources/chat/completions';
import type { Stream } from 'openai/streaming';
import { CONFIG } from '../config.js';

/**
 * Provider clients, cached as module singletons so connection pooling /
 * keep-alive is preserved (do NOT construct a client per request). Kept
 * module-private on purpose: every chat completion must go through
 * `chatComplete()` so reasoning-model parameter rules are applied uniformly.
 */
const OPENROUTER_PREFIX = 'openrouter/';

type Provider = 'openai' | 'openrouter';
const clientCache = new Map<Provider, OpenAI>();

function getClient(provider: Provider): OpenAI {
  let c = clientCache.get(provider);
  if (!c) {
    if (provider === 'openrouter') {
      const defaultHeaders: Record<string, string> = {};
      if (CONFIG.openrouterSiteUrl) defaultHeaders['HTTP-Referer'] = CONFIG.openrouterSiteUrl;
      if (CONFIG.openrouterAppName) defaultHeaders['X-Title'] = CONFIG.openrouterAppName;
      c = new OpenAI({
        apiKey: CONFIG.openrouterApiKey,
        baseURL: CONFIG.openrouterBaseUrl,
        ...(Object.keys(defaultHeaders).length ? { defaultHeaders } : {}),
      });
    } else {
      c = new OpenAI({ apiKey: CONFIG.openaiApiKey });
    }
    clientCache.set(provider, c);
  }
  return c;
}

/**
 * GPT-5 series and o1/o3/o4 reasoning models reject `temperature` != 1 (hard
 * 400) and require `max_completion_tokens` instead of `max_tokens`. Mirror of
 * the Python helper in src/nicheiq/utils/llm_service.py:is_reasoning_model.
 */
export function isReasoningModel(model: string): boolean {
  const m = model.toLowerCase();
  return (
    m.startsWith('gpt-5') ||
    m.startsWith('o1') ||
    m.startsWith('o3') ||
    m.startsWith('o4')
  );
}

export interface ChatCompleteOpts {
  model: string;
  messages: ChatCompletionMessageParam[];
  temperature?: number;
  /** Output budget. Mapped to max_completion_tokens for reasoning models. */
  maxTokens?: number;
  responseFormat?: ChatCompletionCreateParamsNonStreaming['response_format'];
  /**
   * Reasoning budget for GPT-5/o-series. Defaults to `'minimal'` — the value every
   * caller got implicitly before this was configurable — so behaviour is unchanged
   * unless a caller opts in. OpenAI's own default is `'medium'`, and their guide warns
   * `'minimal'` is for latency-sensitive work and should be avoided for multi-step
   * planning; raise it for constraint-heavy generations.
   * Ignored by non-reasoning models.
   */
  reasoningEffort?: 'minimal' | 'low' | 'medium' | 'high';
  /** GPT-5 output-length knob (`low | medium | high`, API default `medium`). */
  verbosity?: 'low' | 'medium' | 'high';
  /** Chat agent tools (v1.1) — the unstreamed tool-resolution rounds in chat.ts's
   *  multi-round loop call this (not chatCompleteStream) so the full tool_calls array
   *  is available in one shot, without delta reassembly. */
  tools?: ChatCompletionTool[];
  toolChoice?: ChatCompletionToolChoiceOption;
  /** Abort the upstream request (e.g. on client disconnect mid tool-loop). */
  signal?: AbortSignal;
}

/**
 * Single entry point for chat completions.
 *
 * For reasoning models it: omits `temperature` (only the default of 1 is
 * accepted), maps `maxTokens` -> `max_completion_tokens` (the SDK honors this
 * directly — there is no CrewAI/LiteLLM layer here), and forces
 * `reasoning_effort: 'minimal'` so hidden reasoning tokens don't consume the
 * output budget and starve the visible JSON.
 *
 * Non-reasoning models pass `temperature`/`max_tokens` through unchanged.
 */
export async function chatComplete(opts: ChatCompleteOpts): Promise<ChatCompletion> {
  const {
    model, messages, temperature, maxTokens, responseFormat, tools, toolChoice, signal,
    reasoningEffort, verbosity,
  } = opts;

  // Route by 'openrouter/' prefix. Strip the prefix FIRST so both the model sent
  // to the API and the reasoning-model detection use the bare id.
  const isOpenRouter = model.toLowerCase().startsWith(OPENROUTER_PREFIX);
  const baseModel = isOpenRouter ? model.slice(OPENROUTER_PREFIX.length) : model;
  const clientForCall = getClient(isOpenRouter ? 'openrouter' : 'openai');

  const params: ChatCompletionCreateParamsNonStreaming = { model: baseModel, messages };
  if (responseFormat) params.response_format = responseFormat;
  if (tools) params.tools = tools;
  if (toolChoice) params.tool_choice = toolChoice;

  if (isReasoningModel(baseModel)) {
    // NOTE: max_completion_tokens covers reasoning tokens as well as visible output, so
    // a caller raising reasoningEffort must raise this budget too or risk truncation.
    if (maxTokens !== undefined) params.max_completion_tokens = maxTokens;
    // 'minimal' is valid for GPT-5 at the API level; the installed SDK's
    // ReasoningEffort union predates it, so cast via `string` to keep TS happy.
    const effort: string = reasoningEffort ?? 'minimal';
    params.reasoning_effort = effort as ChatCompletionCreateParamsNonStreaming['reasoning_effort'];
    if (verbosity) {
      (params as unknown as Record<string, unknown>).verbosity = verbosity;
    }
  } else {
    if (temperature !== undefined) params.temperature = temperature;
    if (maxTokens !== undefined) params.max_tokens = maxTokens;
  }

  return clientForCall.chat.completions.create(params, signal ? { signal } : undefined);
}

export interface ChatCompleteStreamOpts {
  model: string;
  messages: ChatCompletionMessageParam[];
  temperature?: number;
  /** Output budget. Mapped to max_completion_tokens for reasoning models. */
  maxTokens?: number;
  tools?: ChatCompletionTool[];
  toolChoice?: ChatCompletionToolChoiceOption;
  /** Abort the upstream request (e.g. on client disconnect). */
  signal?: AbortSignal;
}

/**
 * Streaming entry point for the guided-chat feature (backend/src/routes/chat.ts).
 * Mirrors `chatComplete()`'s reasoning-model handling but adds `stream: true` +
 * `stream_options: { include_usage: true }` so the final chunk carries token usage
 * for cost tracking, and threads through `tools`/`toolChoice` for the
 * `propose_modification` tool. Left as a separate function (rather than adding a
 * `stream` flag to `chatComplete`) so the well-tested non-streaming path stays
 * untouched.
 */
export async function chatCompleteStream(
  opts: ChatCompleteStreamOpts
): Promise<Stream<ChatCompletionChunk>> {
  const { model, messages, temperature, maxTokens, tools, toolChoice, signal } = opts;

  const isOpenRouter = model.toLowerCase().startsWith(OPENROUTER_PREFIX);
  const baseModel = isOpenRouter ? model.slice(OPENROUTER_PREFIX.length) : model;
  const clientForCall = getClient(isOpenRouter ? 'openrouter' : 'openai');

  const params: ChatCompletionCreateParamsStreaming = {
    model: baseModel,
    messages,
    stream: true,
    stream_options: { include_usage: true },
  };
  if (tools) params.tools = tools;
  if (toolChoice) params.tool_choice = toolChoice;

  if (isReasoningModel(baseModel)) {
    if (maxTokens !== undefined) params.max_completion_tokens = maxTokens;
    const effort: string = 'minimal';
    params.reasoning_effort = effort as ChatCompletionCreateParamsStreaming['reasoning_effort'];
  } else {
    if (temperature !== undefined) params.temperature = temperature;
    if (maxTokens !== undefined) params.max_tokens = maxTokens;
  }

  return clientForCall.chat.completions.create(params, signal ? { signal } : undefined);
}
