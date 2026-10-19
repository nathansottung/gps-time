// Survey reset on the Administration page (POST /api/setting {"reset_site": true}). It discards
// the stored position survey, which may hold weeks of averaged fixes, so the page asks the
// operator to type a word first rather than accepting a single click.
import type { SettingResult, SurveyStats } from '../api/types';

export const RESET_WORD = 'RESET';

/** The typed confirmation: the word itself, any case, surrounding spaces ignored. */
export function resetConfirmed(input: string): boolean {
  return input.trim().toUpperCase() === RESET_WORD;
}

/** What would be lost, from the station's own counts. null stats = UNKNOWN, never "nothing". */
export function surveyLoss(s: SurveyStats | null | undefined): string {
  if (!s) return 'The station has not reported its survey; what would be discarded is UNKNOWN.';
  if (!s.n) return 'The survey is empty: there is nothing to discard.';
  const se = s.se_horiz_m == null ? '' : `, horizontal standard error of the mean ±${s.se_horiz_m.toFixed(2)} m`;
  return `Discards ${s.n.toLocaleString('en-US')} accepted fixes${se}. The survey starts again from the next fresh fix.`;
}

export type ResetOutcome = { variant: 'good' | 'warn' | 'error'; text: string };

export function resetOutcome(r: SettingResult | null, err?: { message: string; status: number | null }): ResetOutcome {
  if (err) {
    if (err.status === null) return { variant: 'warn', text: `No answer from the station (${err.message}). The survey may or may not have been reset; check the accepted-fix count.` };
    return { variant: 'error', text: `Refused: ${err.message}` };
  }
  if (r && r.ok && 'reset_site' in r) return { variant: 'good', text: 'Survey reset. The accepted-fix count starts again from 0.' };
  return { variant: 'error', text: 'The station did not reset the survey.' };
}
