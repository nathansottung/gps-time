// The page shown, kept in the URL hash (#timing, #admin, …) so a reload or a bookmark
// returns to it. Client-side only: the station serves index.html for /app/ either way.

export const PAGE_IDS = [
  'overview', 'timing', 'pps', 'gnss', 'sun', 'network', 'radio', 'aviation',
  'distributed', 'data', 'configure', 'admin',
] as const;
export type PageId = typeof PAGE_IDS[number];

/** The page named by a location hash; unknown or empty → the Overview. */
export function pageFromHash(hash: string): PageId {
  const id = hash.replace(/^#\/?/, '').split(/[?&/]/)[0].toLowerCase();
  return (PAGE_IDS as readonly string[]).includes(id) ? id as PageId : 'overview';
}

export function hashFor(page: string): string {
  return page === 'overview' ? '' : `#${page}`;
}
