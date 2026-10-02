// Copy/download helpers for the diagnostic snapshot. Local only: nothing is
// sent anywhere; the text never leaves the browser except via the user's
// clipboard or a file they save.

/**
 * Copy text to the clipboard. The async Clipboard API needs a secure context
 * (https or localhost); a station on plain http over the LAN is not one, so
 * fall back to a hidden textarea + execCommand('copy').
 */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (window.isSecureContext && navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* fall through */ }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

/** Save text as a UTF-8 .txt file (Blob URL; no network). */
export function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** gps-time-diagnostics-20261002T031455Z.txt */
export function snapshotFilename(now = new Date()): string {
  return `gps-time-diagnostics-${now.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')}.txt`;
}
