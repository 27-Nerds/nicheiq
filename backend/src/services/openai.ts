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

function usesOpenRouter(model: string): boolean {
  return model.toLowerCase().startsWith(OPENROUTER_PREFIX);
}

function capabilityModelId(model: string): string {
  const normalized = model.toLowerCase();
  const finalSeparator = normalized.lastIndexOf('/');
  return finalSeparator >= 0 ? normalized.slice(finalSeparator + 1) : normalized;
}

export function hasApiKeyForModel(model: string): boolean {
  return Boolean(usesOpenRouter(model) ? CONFIG.openrouterApiKey : CONFIG.openaiApiKey);
}

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
  const m = capabilityModelId(model);
  return (
    m.startsWith('gpt-5') ||
    m.startsWith('o1') ||
    m.startsWith('o3') ||
    m.startsWith('o4')
  );
}

type ReasoningEffort = 'none' | 'minimal' | 'low' | 'medium' | 'high';

/**
 * Chat Completions rejects GPT-5 function tools when reasoning is enabled. Keep
 * that provider constraint in this shared boundary so streamed and unstreamed
 * callers cannot drift apart:
 *
 * - an omitted effort is normalized to `none` when tools are present;
 * - an explicit non-`none` effort is rejected before making a paid API call.
 */
function chatCompletionsReasoningEffort(
  model: string,
  tools: ChatCompletionTool[] | undefined,
  requested: ReasoningEffort | undefined,
): ReasoningEffort {
  const hasFunctionTools = Boolean(tools?.length);
  if (capabilityModelId(model).startsWith('gpt-5') && hasFunctionTools) {
    if (requested !== undefined && requested !== 'none') {
      throw new Error(
        'GPT-5 function tools on Chat Completions require reasoningEffort="none"',
      );
    }
    return 'none';
  }
  return requested ?? 'minimal';
}

export interface ChatCompleteOpts {
  model: string;
  messages: ChatCompletionMessageParam[];
  temperature?: number;
  /** Output budget. Mapped to max_completion_tokens for reasoning models. */
  maxTokens?: number;
  responseFormat?: ChatCompletionCreateParamsNonStreaming['response_format'];
  /**
   * Reasoning budget for GPT-5/o-series. Defaults to `'minimal'` for tool-free
   * requests. GPT-5 function-tool calls are normalized to `'none'`, because Chat
   * Completions rejects tools with enabled reasoning.
   * Ignored by non-reasoning models.
   */
  reasoningEffort?: ReasoningEffort;
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
 * `reasoning_effort: 'minimal'` for tool-free calls, or `'none'` for GPT-5
 * function-tool calls, so Chat Completions never receives an invalid pairing.
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
  const isOpenRouter = usesOpenRouter(model);
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
    // The installed SDK's ReasoningEffort union predates some supported values,
    // so cast at the final transport boundary.
    const effort = chatCompletionsReasoningEffort(baseModel, tools, reasoningEffort);
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
  /** See ChatCompleteOpts.reasoningEffort. GPT-5 tool calls require `none`. */
  reasoningEffort?: ReasoningEffort;
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
  const {
    model, messages, temperature, maxTokens, tools, toolChoice, signal, reasoningEffort,
  } = opts;

  const isOpenRouter = usesOpenRouter(model);
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
    const effort = chatCompletionsReasoningEffort(baseModel, tools, reasoningEffort);
    params.reasoning_effort = effort as ChatCompletionCreateParamsStreaming['reasoning_effort'];
  } else {
    if (temperature !== undefined) params.temperature = temperature;
    if (maxTokens !== undefined) params.max_tokens = maxTokens;
  }

  return clientForCall.chat.completions.create(params, signal ? { signal } : undefined);
}
