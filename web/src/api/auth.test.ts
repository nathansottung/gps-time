// Auth UI logic (review GPS-014/017): the client must send state changes as
// POST + application/json + Bearer token, never as GET query strings, and keep
// the token per tab without ever putting it in a URL.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { authHeader, tokenStore } from './auth';
import { ApiError, httpApi } from './client';

function memoryStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, v); },
    removeItem: (k: string) => { m.delete(k); },
    size: () => m.size,
  };
}

interface Call { url: string; init: RequestInit }

function mockFetch(respond: (c: Call) => { status?: number; body: unknown }) {
  const calls: Call[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const c = { url, init };
    calls.push(c);
    const { status = 200, body } = respond(c);
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }));
  return calls;
}

const headersOf = (c: Call) => new Headers(c.init.headers);

afterEach(() => { vi.unstubAllGlobals(); });

describe('tokenStore', () => {
  it('stores, trims, clears', () => {
    const s = memoryStorage();
    const t = tokenStore(s);
    expect(t.get()).toBeNull();
    t.set('  abc  ');
    expect(t.get()).toBe('abc');
    t.set('   ');
    expect(t.get()).toBeNull();
    t.set('x'); t.set(null);
    expect(s.size()).toBe(0);
  });

  it('survives missing or throwing storage', () => {
    expect(tokenStore(null).get()).toBeNull();
    const broken = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); }, removeItem: () => { throw new Error('denied'); } };
    const t = tokenStore(broken);
    expect(() => t.set('abc')).not.toThrow();
    expect(t.get()).toBeNull();
  });

  it('builds the Authorization header only for a real token', () => {
    expect(authHeader('abc')).toEqual({ Authorization: 'Bearer abc' });
    expect(authHeader(' ')).toEqual({});
    expect(authHeader(null)).toEqual({});
  });
});

describe('httpApi state changes', () => {
  it('sends settings as POST + JSON + Bearer, never in the URL', async () => {
    const calls = mockFetch(() => ({ body: { ok: true, location_display: 'hidden' } }));
    const token = tokenStore(memoryStorage());
    token.set('secret-token');
    const api = httpApi('', 8000, token);
    await api.setLocationDisplay('hidden');
    await api.resetSite();
    await api.admin('restart_gpsd');
    expect(calls.map(c => [c.url, c.init.method])).toEqual([
      ['/api/setting', 'POST'], ['/api/setting', 'POST'], ['/api/admin', 'POST'],
    ]);
    for (const c of calls) {
      expect(headersOf(c).get('Content-Type')).toBe('application/json');
      expect(headersOf(c).get('Authorization')).toBe('Bearer secret-token');
      expect(c.url).not.toContain('?');
      expect(c.url).not.toContain('secret-token');
    }
    expect(calls.map(c => JSON.parse(String(c.init.body)))).toEqual([
      { location_display: 'hidden' }, { reset_site: true }, { action: 'restart_gpsd' },
    ]);
  });

  it('sends no Authorization header without a token', async () => {
    const calls = mockFetch(() => ({ body: { ok: true, action: 'flush_logs', detail: '' } }));
    const api = httpApi('', 8000, tokenStore(memoryStorage()));
    await api.admin('flush_logs');
    expect(headersOf(calls[0]).get('Authorization')).toBeNull();
    expect(calls[0].init.body).toBe('{"action":"flush_logs"}');
  });

  it('reports the station reason on 401/403', async () => {
    mockFetch(() => ({ status: 401, body: { ok: false, error: 'admin token required' } }));
    const api = httpApi('', 8000, tokenStore(memoryStorage()));
    const err = await api.admin('reboot').catch(e => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(err.message).toContain('admin token required (HTTP 401)');
  });

  it('checks the token with GET /api/auth (header, not URL)', async () => {
    const calls = mockFetch(() => ({ body: { demo: false, auth_required: true, admin_configured: true, authenticated: true } }));
    const token = tokenStore(memoryStorage());
    token.set('t0k');
    const a = await httpApi('', 8000, token).auth();
    expect(a.authenticated).toBe(true);
    expect(calls[0].url).toBe('/api/auth');
    expect(calls[0].init.method ?? 'GET').toBe('GET');
    expect(headersOf(calls[0]).get('Authorization')).toBe('Bearer t0k');
  });
});
