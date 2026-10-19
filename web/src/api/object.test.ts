import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, httpApi } from './client';

const reply = (body: unknown) => vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }));

describe('api.object', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('an unparsed query is an answer, not an error', async () => {
    vi.stubGlobal('fetch', reply({ error: 'unparsed' }));
    expect(await httpApi('', 1000, { get: () => null, set: () => {} }).object('zzzz')).toEqual({ error: 'unparsed' });
  });

  it('a real server failure still throws', async () => {
    vi.stubGlobal('fetch', reply({ error: 'boom' }));
    await expect(httpApi('', 1000, { get: () => null, set: () => {} }).object('M31')).rejects.toBeInstanceOf(ApiError);
  });

  it('sends q, date, tz and at; no state-changing method', async () => {
    const f = reply({ available: false, reason: 'x' });
    vi.stubGlobal('fetch', f);
    await httpApi('', 1000, { get: () => null, set: () => {} }).object('M31', { date: '2026-10-19', tz: 'UTC', at: '22:00' });
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit | undefined];
    expect(url).toBe('/api/object?q=M31&date=2026-10-19&tz=UTC&at=22%3A00');
    expect(init?.method ?? 'GET').toBe('GET');
  });
});
