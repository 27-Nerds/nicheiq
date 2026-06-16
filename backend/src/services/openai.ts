import OpenAI from 'openai';
import type {
  ChatCompletion,
  ChatCompletionCreateParamsNonStreaming,
  ChatCompletionMessageParam,
} from 'openai/resources/chat/completions';
import { CONFIG } from '../config.js';

/**
 * Shared OpenAI client. Kept module-private on purpose: every chat completion
 * must go through `chatComplete()` so reasoning-model parameter rules are
 * applied uniformly. Do NOT export this — add call sites via `chatComplete`.
 */
const client = new OpenAI({
  apiKey: CONFIG.openaiApiKey,
});

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
  const { model, messages, temperature, maxTokens, responseFormat } = opts;
  const params: ChatCompletionCreateParamsNonStreaming = { model, messages };
  if (responseFormat) params.response_format = responseFormat;

  if (isReasoningModel(model)) {
    if (maxTokens !== undefined) params.max_completion_tokens = maxTokens;
    // 'minimal' is valid for GPT-5 at the API level; the installed SDK's
    // ReasoningEffort union predates it, so cast via `string` to keep TS happy.
    const effort: string = 'minimal';
    params.reasoning_effort = effort as ChatCompletionCreateParamsNonStreaming['reasoning_effort'];
  } else {
    if (temperature !== undefined) params.temperature = temperature;
    if (maxTokens !== undefined) params.max_tokens = maxTokens;
  }

  return client.chat.completions.create(params);
}
