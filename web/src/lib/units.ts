// Display helpers for scientific quantities (see guidelines/Guidelines.md,
// "Scientific terminology conventions").

const SUPERSCRIPT: Record<string, string> = {
  '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
  '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
};

/**
 * Format a dimensionless value in scientific notation with a Unicode minus
 * and superscript exponent: -1.24e-9 -> "−1.24 × 10⁻⁹".
 * Used for fractional frequency offset Δf/f (never ppm/ppb alone).
 */
export function fmtSci(x: number, significant = 3): string {
  if (!Number.isFinite(x)) return '—';
  if (x === 0) return '0';
  let exp = Math.floor(Math.log10(Math.abs(x)));
  let mant = Number((x / 10 ** exp).toPrecision(significant));
  if (Math.abs(mant) >= 10) { mant /= 10; exp += 1; }   // rounding carried into the next decade
  const sign = mant < 0 ? '−' : '';
  const body = Math.abs(mant).toString();
  if (exp === 0) return sign + body;
  const sup = String(exp).split('').map(c => SUPERSCRIPT[c]).join('');
  return `${sign}${body} × 10${sup}`;
}
