import { afterEach, describe, expect, it, vi } from 'vitest';
import { streamChat, type ChatStreamEvent } from '../api';

const encoder = new TextEncoder();

function streamResponse(chunks: string[]): Response {
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    }),
    { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
  );
}

describe('streamChat terminal delivery', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('parses a final done event even when the stream closes without a blank-line delimiter', async () => {
    const done: ChatStreamEvent = {
      type: 'done',
      message: {
        id: 'assistant-1',
        role: 'assistant',
        content: 'Recovered from the final decoder buffer.',
        patchJson: null,
        createdAt: '2026-07-14T00:00:00.000Z',
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      streamResponse([`data: ${JSON.stringify(done)}`]),
    );
    vi.stubGlobal('fetch', fetchMock);
    const events: ChatStreamEvent[] = [];

    await streamChat('job-1', 'show evidence', { onEvent: (event) => events.push(event) });

    expect(events).toEqual([done]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('recovers the persisted answer from history when the terminal SSE event is lost', async () => {
    const tool: ChatStreamEvent = { type: 'tool', label: 'Checked evidence for "Storage risk"' };
    const history = {
      messages: [
        {
          id: 'user-1',
          gateStage: 5,
          role: 'user',
          content: 'show evidence',
          createdAt: '2026-07-14T00:00:00.000Z',
        },
        {
          id: 'assistant-1',
          gateStage: 5,
          role: 'assistant',
          content: 'The stored evidence answer.',
          patchJson: null,
          toolCallsJson: [{ name: 'get_pain_evidence', args: {}, label: tool.label }],
          suggestionsJson: null,
          createdAt: '2026-07-14T00:00:01.000Z',
        },
      ],
      usedTurns: 1,
      maxTurns: 30,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(streamResponse([`data: ${JSON.stringify(tool)}\n\n`]))
      .mockResolvedValueOnce(new Response(JSON.stringify(history), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }));
    vi.stubGlobal('fetch', fetchMock);
    const events: ChatStreamEvent[] = [];

    await streamChat('job-1', 'show evidence', { onEvent: (event) => events.push(event) });

    expect(events[0]).toEqual(tool);
    expect(events[1]).toMatchObject({
      type: 'done',
      userMessageId: 'user-1',
      message: { id: 'assistant-1', content: 'The stored evidence answer.' },
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/jobs/job-1/chat/history');
  });
});
