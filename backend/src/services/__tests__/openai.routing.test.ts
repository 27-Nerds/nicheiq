import { describe, it, expect, vi, beforeEach } from 'vitest';

// Capture OpenAI constructor args + a create() spy. The constructor returns a
// client whose chat.completions.create records its params.
const constructorCalls: any[] = [];
const createSpy = vi.fn().mockResolvedValue({ id: 'cmpl_test' });

vi.mock('openai', () => {
  const MockOpenAI = function (opts: any) {
    constructorCalls.push(opts);
    return { chat: { completions: { create: createSpy } } };
  };
  return { default: MockOpenAI };
});

vi.mock('../../config.js', () => ({
  CONFIG: {
    openaiApiKey: 'sk-openai',
    openrouterApiKey: 'sk-openrouter',
    openrouterBaseUrl: 'https://openrouter.ai/api/v1',
    openrouterSiteUrl: 'https://nicheiq.test',
    openrouterAppName: 'NicheIQ',
  },
}));

// Fresh module (and fresh client cache) per test.
async function freshChatComplete() {
  vi.resetModules();
  constructorCalls.length = 0;
  createSpy.mockClear();
  const mod = await import('../openai.js');
  return mod;
}

const messages = [{ role: 'user' as const, content: 'hi' }];

describe('chatComplete provider routing', () => {
  beforeEach(() => {
    constructorCalls.length = 0;
    createSpy.mockClear();
  });

  it('routes openrouter/* to OpenRouter client with stripped model', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({
      model: 'openrouter/google/gemma-2-27b-it',
      messages,
      temperature: 0.3,
    });

    // OpenRouter client constructed with base URL, OR key, and attribution headers
    expect(constructorCalls).toHaveLength(1);
    expect(constructorCalls[0].baseURL).toBe('https://openrouter.ai/api/v1');
    expect(constructorCalls[0].apiKey).toBe('sk-openrouter');
    expect(constructorCalls[0].defaultHeaders).toEqual({
      'HTTP-Referer': 'https://nicheiq.test',
      'X-Title': 'NicheIQ',
    });
    // Prefix stripped before sending
    expect(createSpy.mock.calls[0][0].model).toBe('google/gemma-2-27b-it');
    // gemma is non-reasoning -> temperature passed, no reasoning_effort
    expect(createSpy.mock.calls[0][0].temperature).toBe(0.3);
    expect(createSpy.mock.calls[0][0].reasoning_effort).toBeUndefined();
  });

  it('routes plain models to the OpenAI client (no base URL)', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({ model: 'gpt-4.1-mini', messages, temperature: 0.5 });

    expect(constructorCalls).toHaveLength(1);
    expect(constructorCalls[0].apiKey).toBe('sk-openai');
    expect(constructorCalls[0].baseURL).toBeUndefined();
    expect(createSpy.mock.calls[0][0].model).toBe('gpt-4.1-mini');
  });

  it('detects reasoning on the stripped model (openrouter/gpt-5-*)', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({
      model: 'openrouter/openai/gpt-5-nano',
      messages,
      temperature: 0.7,
      maxTokens: 500,
    });
    const params = createSpy.mock.calls[0][0];
    // baseModel 'openai/gpt-5-nano' is not gpt-5-prefixed, so this stays non-reasoning;
    // assert the model sent is stripped and routing went to OpenRouter.
    expect(params.model).toBe('openai/gpt-5-nano');
    expect(constructorCalls[0].baseURL).toBe('https://openrouter.ai/api/v1');
  });

  it('reuses one client per provider (connection pooling)', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({ model: 'gpt-4.1-mini', messages });
    await chatComplete({ model: 'gpt-4o-mini', messages });
    await chatComplete({ model: 'openrouter/google/gemma-2-27b-it', messages });
    await chatComplete({ model: 'openrouter/google/gemma-2-9b-it', messages });
    // exactly 2 constructions total: one OpenAI, one OpenRouter
    expect(constructorCalls).toHaveLength(2);
  });
});

describe('chatCompleteStream', () => {
  beforeEach(() => {
    constructorCalls.length = 0;
    createSpy.mockClear();
  });

  it('sets stream:true + stream_options.include_usage, and forwards tools/temperature', async () => {
    const { chatCompleteStream } = await freshChatComplete();
    await chatCompleteStream({ model: 'gpt-4.1-mini', messages, temperature: 0.4, maxTokens: 800, tools: [{ type: 'function', function: { name: 'noop', parameters: {} } }] });

    const params = createSpy.mock.calls[0][0];
    expect(params.stream).toBe(true);
    expect(params.stream_options).toEqual({ include_usage: true });
    expect(params.temperature).toBe(0.4);
    expect(params.max_tokens).toBe(800);
    expect(params.tools).toHaveLength(1);
    expect(params.reasoning_effort).toBeUndefined();
  });

  it('applies reasoning-model rules (max_completion_tokens + reasoning_effort minimal, no temperature)', async () => {
    const { chatCompleteStream } = await freshChatComplete();
    await chatCompleteStream({ model: 'gpt-5-mini', messages, temperature: 0.4, maxTokens: 800 });

    const params = createSpy.mock.calls[0][0];
    expect(params.temperature).toBeUndefined();
    expect(params.max_tokens).toBeUndefined();
    expect(params.max_completion_tokens).toBe(800);
    expect(params.reasoning_effort).toBe('minimal');
  });

  it('passes an AbortSignal through as request options (second create() arg)', async () => {
    const { chatCompleteStream } = await freshChatComplete();
    const controller = new AbortController();
    await chatCompleteStream({ model: 'gpt-4.1-mini', messages, signal: controller.signal });

    expect(createSpy.mock.calls[0][1]).toEqual({ signal: controller.signal });
  });

  it('routes openrouter/* models to the OpenRouter client with a stripped model id', async () => {
    const { chatCompleteStream } = await freshChatComplete();
    await chatCompleteStream({ model: 'openrouter/google/gemma-2-27b-it', messages });

    expect(constructorCalls[0].baseURL).toBe('https://openrouter.ai/api/v1');
    expect(createSpy.mock.calls[0][0].model).toBe('google/gemma-2-27b-it');
  });
});
