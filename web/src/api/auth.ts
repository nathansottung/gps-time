// Admin token for state-changing requests (docs/api/README.md, "Authentication").
// Kept in sessionStorage: per tab, gone when the tab closes, never in the URL,
// never sent anywhere but this station's own /api. Storage can be missing or
// throw (private mode, tests), so every access is guarded.

const KEY = 'gtp-admin-token';

export interface TokenStore {
  get(): string | null;
  set(token: string | null): void;
}

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export function tokenStore(storage?: StorageLike | null): TokenStore {
  const s = (): StorageLike | null => {
    if (storage !== undefined) return storage;
    try { return typeof sessionStorage !== 'undefined' ? sessionStorage : null; } catch { return null; }
  };
  return {
    get() {
      try { return s()?.getItem(KEY) || null; } catch { return null; }
    },
    set(token) {
      try {
        const t = token?.trim();
        if (t) s()?.setItem(KEY, t); else s()?.removeItem(KEY);
      } catch { /* storage unavailable: the token lives only for this request */ }
    },
  };
}

/** Authorization header for a token, or none. */
export function authHeader(token: string | null | undefined): Record<string, string> {
  const t = token?.trim();
  return t ? { Authorization: `Bearer ${t}` } : {};
}
