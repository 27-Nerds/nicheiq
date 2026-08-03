import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockConfig = vi.hoisted(() => ({
  openaiApiKey: 'sk-openai',
  openrouterApiKey: 'sk-openrouter',
  openrouterBaseUrl: 'https://openrouter.ai/api/v1',
  openrouterSiteUrl: 'https://nicheiq.test',
  openrouterAppName: 'NicheIQ',
}));

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
  CONFIG: mockConfig,
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
    mockConfig.openaiApiKey = 'sk-openai';
    mockConfig.openrouterApiKey = 'sk-openrouter';
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

  it('detects reasoning from the final segment without truncating the OpenRouter model id', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({
      model: 'openrouter/openai/gpt-5-nano',
      messages,
      temperature: 0.7,
      maxTokens: 500,
    });
    const params = createSpy.mock.calls[0][0];
    expect(params.model).toBe('openai/gpt-5-nano');
    expect(constructorCalls[0].baseURL).toBe('https://openrouter.ai/api/v1');
    expect(params.temperature).toBeUndefined();
    expect(params.max_tokens).toBeUndefined();
    expect(params.max_completion_tokens).toBe(500);
    expect(params.reasoning_effort).toBe('minimal');
  });

  it('requires the API key for the provider selected by the model id', async () => {
    const { hasApiKeyForModel } = await freshChatComplete();

    mockConfig.openrouterApiKey = '';
    expect(hasApiKeyForModel('openrouter/openai/gpt-5-mini')).toBe(false);
    expect(hasApiKeyForModel('gpt-5-mini')).toBe(true);

    mockConfig.openrouterApiKey = 'sk-openrouter';
    mockConfig.openaiApiKey = '';
    expect(hasApiKeyForModel('openrouter/openai/gpt-5-mini')).toBe(true);
    expect(hasApiKeyForModel('gpt-5-mini')).toBe(false);
  });

  it('preserves the explicit-none guard for provider-qualified GPT-5 tool calls', async () => {
    const { chatComplete } = await freshChatComplete();

    await expect(chatComplete({
      model: 'openrouter/openai/gpt-5-mini',
      messages,
      tools: [{ type: 'function', function: { name: 'noop', parameters: {} } }],
      reasoningEffort: 'high',
    })).rejects.toThrow('require reasoningEffort="none"');
    expect(createSpy).not.toHaveBeenCalled();
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

  it('normalizes GPT-5 function tools to reasoning_effort none', async () => {
    const { chatCompleteStream } = await freshChatComplete();
    await chatCompleteStream({
      model: 'gpt-5.6-luna',
      messages,
      tools: [{ type: 'function', function: { name: 'noop', parameters: {} } }],
    });

    expect(createSpy.mock.calls[0][0].reasoning_effort).toBe('none');
  });

  it('rejects an explicit reasoning budget for streamed GPT-5 function tools', async () => {
    const { chatCompleteStream } = await freshChatComplete();

    await expect(chatCompleteStream({
      model: 'gpt-5.6-luna',
      messages,
      tools: [{ type: 'function', function: { name: 'noop', parameters: {} } }],
      reasoningEffort: 'minimal',
    })).rejects.toThrow('require reasoningEffort="none"');
    expect(createSpy).not.toHaveBeenCalled();
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

describe('reasoning-model parameters', () => {
  beforeEach(() => createSpy.mockClear());

  it('defaults reasoning_effort to minimal, preserving every existing call site', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({ model: 'gpt-5-mini', messages: [{ role: 'user', content: 'x' }] });
    expect(createSpy.mock.calls[0][0].reasoning_effort).toBe('minimal');
  });

  it('honours an explicit reasoningEffort', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({
      model: 'gpt-5-mini',
      messages: [{ role: 'user', content: 'x' }],
      reasoningEffort: 'high',
    });
    expect(createSpy.mock.calls[0][0].reasoning_effort).toBe('high');
  });

  it('normalizes GPT-5 function tools to reasoning_effort none', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({
      model: 'gpt-5.6-luna',
      messages: [{ role: 'user', content: 'x' }],
      tools: [{ type: 'function', function: { name: 'noop', parameters: {} } }],
    });

    expect(createSpy.mock.calls[0][0].reasoning_effort).toBe('none');
  });

  it('rejects an explicit reasoning budget for unstreamed GPT-5 function tools', async () => {
    const { chatComplete } = await freshChatComplete();

    await expect(chatComplete({
      model: 'gpt-5.6-luna',
      messages: [{ role: 'user', content: 'x' }],
      tools: [{ type: 'function', function: { name: 'noop', parameters: {} } }],
      reasoningEffort: 'high',
    })).rejects.toThrow('require reasoningEffort="none"');
    expect(createSpy).not.toHaveBeenCalled();
  });

  it('passes verbosity only when asked for', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({ model: 'gpt-5-mini', messages: [{ role: 'user', content: 'x' }] });
    expect(createSpy.mock.calls[0][0].verbosity).toBeUndefined();

    createSpy.mockClear();
    await chatComplete({
      model: 'gpt-5-mini',
      messages: [{ role: 'user', content: 'x' }],
      verbosity: 'low',
    });
    expect(createSpy.mock.calls[0][0].verbosity).toBe('low');
  });

  it('still drops temperature and maps the token budget for reasoning models', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({
      model: 'gpt-5-mini',
      messages: [{ role: 'user', content: 'x' }],
      temperature: 0.45,
      maxTokens: 16_000,
      reasoningEffort: 'high',
    });
    const params = createSpy.mock.calls[0][0];
    // gpt-5-mini accepts only temperature=1, so passing one is silently inert.
    expect(params.temperature).toBeUndefined();
    expect(params.max_tokens).toBeUndefined();
    expect(params.max_completion_tokens).toBe(16_000);
  });

  it('ignores both knobs on a non-reasoning model', async () => {
    const { chatComplete } = await freshChatComplete();
    await chatComplete({
      model: 'gpt-4o-mini',
      messages: [{ role: 'user', content: 'x' }],
      temperature: 0.3,
      reasoningEffort: 'high',
      verbosity: 'low',
    });
    const params = createSpy.mock.calls[0][0];
    expect(params.reasoning_effort).toBeUndefined();
    expect(params.verbosity).toBeUndefined();
    expect(params.temperature).toBe(0.3);
  });
});
